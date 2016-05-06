# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Conda environment providers."""
from __future__ import absolute_import, print_function

import os

from anaconda_project.internal.simple_status import SimpleStatus
from anaconda_project.conda_manager import new_conda_manager, CondaManagerError
from anaconda_project.plugins.provider import EnvVarProvider
from anaconda_project.provide import PROVIDE_MODE_CHECK


class CondaEnvProvider(EnvVarProvider):
    """Provides a Conda environment."""

    def __init__(self):
        """Override to create our CondaManager."""
        super(CondaEnvProvider, self).__init__()
        self._conda = new_conda_manager()

    def read_config(self, requirement, environ, local_state_file, overrides):
        """Override superclass to add a choice to create a project-scoped environment."""
        assert 'PROJECT_DIR' in environ
        project_dir = environ['PROJECT_DIR']

        if overrides.conda_environment_name is not None:
            # short-circuit this whole party
            env = requirement.environments.get(overrides.conda_environment_name)
            config = dict(source='project', env_name=overrides.conda_environment_name, value=env.path(project_dir))
            return config

        config = super(CondaEnvProvider, self).read_config(requirement, environ, local_state_file, overrides)

        assert 'source' in config

        # we don't support a default here because it would
        # need a hardcoded path which the project.yml author
        # would have no way of providing. Fortunately there's
        # no syntax in project.yml that should result in setting
        # a default.
        assert config['source'] != 'default'

        if config['source'] == 'environ':
            # we have a setting (off by default) for whether to
            # use the conda env we were in prior to
            # preparation. By default we always use a
            # project-scoped one.
            if not local_state_file.get_value('inherit_environment', default=False):
                config['source'] = 'project'
        elif config['source'] == 'unset':
            # if nothing is selected, default to project mode
            # because we don't have a radio button in the UI for
            # "do nothing" right now
            config['source'] = 'project'

        # be sure we don't get confused by alternate ways to spell the path
        if 'value' in config:
            config['value'] = os.path.normpath(config['value'])

        config['env_name'] = requirement.default_environment_name

        if 'value' in config:
            for env in requirement.environments.values():
                if config['value'] == env.path(project_dir):
                    config['env_name'] = env.name
                    if config['source'] == 'variables':
                        config['source'] = 'project'
        elif config['source'] == 'project':
            env = requirement.environments.get(config['env_name'])
            config['value'] = env.path(project_dir)

        # print("read_config " + repr(config))

        return config

    def set_config_values_as_strings(self, requirement, environ, local_state_file, overrides, values):
        """Override superclass to support 'project' source option."""
        super(CondaEnvProvider, self).set_config_values_as_strings(requirement, environ, local_state_file, overrides,
                                                                   values)

        # We have to clear out the user override or it will
        # never stop overriding the user's new choice, if they
        # have changed to another env.
        overrides.conda_environment_name = None

        if 'source' in values:
            if values['source'] == 'project':
                project_dir = environ['PROJECT_DIR']
                name = values['env_name']
                for env in requirement.environments.values():
                    if env.name == name:
                        prefix = env.path(project_dir)
                        local_state_file.set_value(['variables', requirement.env_var], prefix)
            elif values['source'] == 'environ':
                # if user chose 'environ' explicitly, we need to set the inherit_environment flag
                local_state_file.set_value('inherit_environment', True)

    def config_html(self, requirement, environ, local_state_file, status):
        """Override superclass to provide the extra option to create one of our configured environments."""
        # print("config_html with config " + repr(status.analysis.config))
        environ_value = environ.get(requirement.env_var, None)
        project_dir = environ['PROJECT_DIR']
        options_html = ('<div><label><input type="radio" name="source" ' +
                        'value="project"/>Use project-specific environment: <select name="env_name">')
        environ_value_is_project_specific = False
        for env in requirement.environments.values():
            html = ('<option value="%s">%s</option>\n' % (env.name, env.name))
            if env.path(project_dir) == environ_value:
                environ_value_is_project_specific = True
            options_html = options_html + html

        options_html = options_html + "</select></div>\n"

        if environ_value is not None and not environ_value_is_project_specific:
            options_html = options_html + """
            <div>
              <label><input type="radio" name="source" value="environ"/>Keep value '{from_environ}'</label>
            </div>
            """.format(from_environ=environ_value)

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

        # we want to ignore the existing env var unless inherit_environment=True
        # read_config should have already arranged this
        if not context.local_state_file.get_value('inherit_environment', default=False):
            assert context.status.analysis.config['source'] != 'environ'

        # set the env var (but not PATH, etc. to fully activate, that's done below)
        super_result = super(CondaEnvProvider, self).provide(requirement, context)

        project_dir = context.environ['PROJECT_DIR']

        if context.status.analysis.config['source'] == 'environ':
            prefix = context.environ.get(requirement.env_var, None)
        else:
            prefix = None

        if prefix is None:
            # use the default environment
            env_name = context.status.analysis.config.get('env_name', requirement.default_environment_name)
            env = requirement.environments.get(env_name)
            assert env is not None
            prefix = env.path(project_dir)

        assert prefix is not None

        if context.mode != PROVIDE_MODE_CHECK:
            # we update the environment in both prod and dev mode

            env_spec = None
            for env in requirement.environments.values():
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

    def unprovide(self, requirement, environ, local_state_file, requirement_status=None):
        """Override superclass to delete project-scoped envs directory."""
        # TODO
        return SimpleStatus(success=True, description=("Not cleaning up environments."))
