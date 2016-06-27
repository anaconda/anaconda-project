# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Conda environment providers."""
from __future__ import absolute_import, print_function

import os
import shutil

from anaconda_project.internal.simple_status import SimpleStatus
from anaconda_project.conda_manager import new_conda_manager, CondaManagerError
from anaconda_project.plugins.provider import EnvVarProvider
from anaconda_project.provide import PROVIDE_MODE_CHECK


def _remove_env_path(env_path):
    """Also used by project_ops.py to delete environment files."""
    if os.path.exists(env_path):
        try:
            shutil.rmtree(env_path)
            return SimpleStatus(success=True, description=("Deleted environment files in %s." % env_path))
        except Exception as e:
            problem = "Failed to remove environment files in {}: {}.".format(env_path, str(e))
            return SimpleStatus(success=False, description=problem)
    else:
        return SimpleStatus(success=True,
                            description=("Nothing to clean up for environment '%s'." % os.path.basename(env_path)))


class CondaEnvProvider(EnvVarProvider):
    """Provides a Conda environment."""

    def __init__(self):
        """Override to create our CondaManager."""
        super(CondaEnvProvider, self).__init__()
        self._conda = new_conda_manager()

    def read_config(self, requirement, environ, local_state_file, default_env_spec_name, overrides):
        """Override superclass to add a choice to create a project-scoped environment."""
        assert 'PROJECT_DIR' in environ
        project_dir = environ['PROJECT_DIR']

        if overrides.env_spec_name is not None:
            # short-circuit this whole party
            env = requirement.env_specs.get(overrides.env_spec_name)
            # future: it should be possible to override the env spec without using the
            # default-created project-scoped env.
            config = dict(source='project', env_name=overrides.env_spec_name, value=env.path(project_dir))
            return config

        config = super(CondaEnvProvider, self).read_config(requirement, environ, local_state_file,
                                                           default_env_spec_name, overrides)

        assert 'source' in config

        # we don't support a default here because it would
        # need a hardcoded path which the project.yml author
        # would have no way of providing. Fortunately there's
        # no syntax in project.yml that should result in setting
        # a default.
        assert config['source'] != 'default'

        if config['source'] == 'unset':
            if local_state_file.get_value('inherit_environment', default=False) and overrides.inherited_env is not None:
                config['source'] = 'inherited'
                config['value'] = overrides.inherited_env
            else:
                # if nothing is selected, default to project mode
                # because we don't have a radio button in the UI for
                # "do nothing" right now.
                config['source'] = 'project'

        # be sure we don't get confused by alternate ways to spell the path
        if 'value' in config:
            config['value'] = os.path.normpath(config['value'])

        config['env_name'] = default_env_spec_name

        if 'value' in config:
            for env in requirement.env_specs.values():
                if config['value'] == env.path(project_dir):
                    config['env_name'] = env.name
                    if config['source'] == 'variables':
                        config['source'] = 'project'
        elif config['source'] == 'project':
            env = requirement.env_specs.get(config['env_name'])
            config['value'] = env.path(project_dir)

        # print("read_config " + repr(config))

        return config

    def set_config_values_as_strings(self, requirement, environ, local_state_file, default_env_spec_name, overrides,
                                     values):
        """Override superclass to support 'project' source option."""
        super(CondaEnvProvider, self).set_config_values_as_strings(requirement, environ, local_state_file,
                                                                   default_env_spec_name, overrides, values)

        # We have to clear out the user override or it will
        # never stop overriding the user's new choice, if they
        # have changed to another env.
        overrides.env_spec_name = None

        if 'source' in values:
            if values['source'] == 'inherited':
                local_state_file.set_value('inherit_environment', True)
            else:
                # don't write this out if it wasn't in there anyway
                if local_state_file.get_value('inherit_environment') is not None:
                    local_state_file.set_value('inherit_environment', False)

            if values['source'] == 'project':
                project_dir = environ['PROJECT_DIR']
                name = values['env_name']
                for env in requirement.env_specs.values():
                    if env.name == name:
                        prefix = env.path(project_dir)
                        local_state_file.set_value(['variables', requirement.env_var], prefix)

    def config_html(self, requirement, environ, local_state_file, overrides, status):
        """Override superclass to provide the extra option to create one of our configured env_specs."""
        # print("config_html with config " + repr(status.analysis.config))
        environ_value = environ.get(requirement.env_var, None)
        project_dir = environ['PROJECT_DIR']
        options_html = ('<div><label><input type="radio" name="source" ' +
                        'value="project"/>Use project-specific environment: <select name="env_name">')
        environ_value_is_project_specific = False
        inherited_value_is_project_specific = False
        for env in requirement.env_specs.values():
            html = ('<option value="%s">%s</option>\n' % (env.name, env.name))
            if env.path(project_dir) == environ_value:
                environ_value_is_project_specific = True
            if env.path(project_dir) == overrides.inherited_env:
                inherited_value_is_project_specific = True
            options_html = options_html + html

        options_html = options_html + "</select></div>\n"

        if environ_value is not None and not environ_value_is_project_specific:
            options_html = options_html + """
            <div>
              <label><input type="radio" name="source" value="environ"/>Keep value '{from_environ}'</label>
            </div>
            """.format(from_environ=environ_value)

        if environ_value != overrides.inherited_env and \
           overrides.inherited_env is not None and \
           not inherited_value_is_project_specific:
            options_html = options_html + """
            <div>
              <label><input type="radio" name="source" value="inherited"/>Inherit environment '{from_inherited}'</label>
            </div>
            """.format(from_inherited=overrides.inherited_env)

        options_html = options_html + """
            <div>
              <label><input type="radio" name="source" value="variables"/>Use this %s instead:
                     <input type="text" name="value"/></label>
            </div>
            """ % (requirement.env_var)

        return """
<form>
  %s
</form>
""" % (options_html)

    def provide(self, requirement, context):
        """Override superclass to create or update our environment."""
        assert 'PATH' in context.environ

        # set from the inherited vale if necessary
        if context.status.analysis.config['source'] == 'inherited':
            context.environ[requirement.env_var] = context.status.analysis.config['value']

        # set the env var (but not PATH, etc. to fully activate, that's done below)
        super_result = super(CondaEnvProvider, self).provide(requirement, context)

        project_dir = context.environ['PROJECT_DIR']

        if context.status.analysis.config['source'] in ('environ', 'inherited'):
            prefix = context.environ.get(requirement.env_var, None)
        else:
            prefix = None

        if prefix is None:
            # use the default environment
            env_name = context.status.analysis.config.get('env_name', context.default_env_spec_name)
            env = requirement.env_specs.get(env_name)
            assert env is not None
            prefix = env.path(project_dir)

        assert prefix is not None

        if context.mode != PROVIDE_MODE_CHECK:
            # we update the environment in both prod and dev mode

            env_spec = None
            for env in requirement.env_specs.values():
                if env.path(project_dir) == prefix:
                    env_spec = env
                    break

            # TODO if not creating a named env, we could use the
            # shared dependencies, but for now we leave it alone
            if env_spec is not None:
                try:
                    self._conda.fix_environment_deviations(prefix, env_spec)
                except CondaManagerError as e:
                    return super_result.copy_with_additions(errors=[str(e)])

        context.environ[requirement.env_var] = prefix
        if requirement.env_var != "CONDA_DEFAULT_ENV":
            # This only matters on Unix, on Windows
            # requirement.env_var is CONDA_DEFAULT_ENV already.
            # future: if the prefix is a (globally, not
            # project-scoped) named environment this should be set
            # to the name
            context.environ["CONDA_DEFAULT_ENV"] = prefix
        path = context.environ.get("PATH", "")

        import anaconda_project.internal.conda_api as conda_api
        context.environ["PATH"] = conda_api.set_conda_env_in_path(path, prefix)
        # Some stuff can only be done when a shell is launched:
        #  - we can't set PS1 because it shouldn't be exported.
        #  - we can't run conda activate scripts because they are sourced.
        # We can do these in the output of our activate command, but not here.

        return super_result

    def unprovide(self, requirement, environ, local_state_file, overrides, requirement_status=None):
        """Override superclass to delete project-scoped envs directory."""
        config = self.read_config(requirement,
                                  environ,
                                  local_state_file,
                                  # future: pass in this default_env_spec_name
                                  default_env_spec_name='default',
                                  overrides=overrides)

        env_path = config.get('value', None)
        assert env_path is not None
        project_dir = environ['PROJECT_DIR']
        if not env_path.startswith(project_dir):
            return SimpleStatus(success=True,
                                description=("Current environment is not in %s, no need to delete it." % project_dir))

        return _remove_env_path(env_path)
