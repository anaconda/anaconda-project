# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Conda environment providers."""
from __future__ import absolute_import, print_function

import os
import shutil

from anaconda_project.internal import conda_api
from anaconda_project.internal.simple_status import SimpleStatus
from anaconda_project.conda_manager import new_conda_manager, CondaManagerError
from anaconda_project.requirements_registry.provider import EnvVarProvider
from anaconda_project.provide import PROVIDE_MODE_CHECK


def _remove_env_path(env_path, project_dir):
    """Also used by project_ops.py to delete environment files."""
    if not os.path.isdir(env_path):
        return SimpleStatus(success=True,
                            description=("Nothing to clean up for environment '%s'." % os.path.basename(env_path)))
    if not env_path.startswith(project_dir + os.sep):
        return SimpleStatus(success=True,
                            description=("Current environment is not in %s, no need to delete it." % project_dir))
    try:
        shutil.rmtree(env_path)
        return SimpleStatus(success=True, description=("Deleted environment files in %s." % env_path))
    except Exception as e:
        problem = "Failed to remove environment files in {}: {}.".format(env_path, str(e))
        return SimpleStatus(success=False, description=problem)


class CondaEnvProvider(EnvVarProvider):
    """Provides a Conda environment."""
    def __init__(self):
        """Override to create our CondaManager."""
        super(CondaEnvProvider, self).__init__()

    def missing_env_vars_to_configure(self, requirement, environ, local_state_file):
        """Override superclass to not require ourselves."""
        return ()

    def missing_env_vars_to_provide(self, requirement, environ, local_state_file):
        """Override superclass to not require ourselves."""
        return self.missing_env_vars_to_configure(requirement, environ, local_state_file)

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

        # for non-bootstrap environments we do not support a default because
        # it would need a hardcoded path which the anaconda-project.yml author
        # would have no way of providing. Fortunately there's no syntax in
        # anaconda-project.yml that should result in setting a default.
        if default_env_spec_name == 'bootstrap-env':
            assert config['source'] != 'default'

        if config['source'] == 'unset':
            # if nothing is selected, default to project mode
            # because we don't have a radio button in the UI for
            # "do nothing" right now.
            config['source'] = 'project'

        # if we're supposed to inherit the environment, we don't want to look at
        # anything else. This should always get rid of 'environ' source.
        if local_state_file.get_value('inherit_environment', default=False) and overrides.inherited_env is not None:
            config['source'] = 'inherited'
            config['value'] = overrides.inherited_env

        # convert 'environ' to 'project' when needed... this would
        # happen if you keep the default 'project' choice, so
        # there's nothing in anaconda-project-local.yml
        if config['source'] == 'environ':
            environ_value = config['value']
            project_dir = environ['PROJECT_DIR']
            environ_value_is_project_specific = False
            for env in requirement.env_specs.values():
                if env.path(project_dir) == environ_value:
                    environ_value_is_project_specific = True
            assert environ_value_is_project_specific
            config['source'] = 'project'

        # we should have changed 'environ' to the specific source; since for conda envs
        # we ignore the initial environ value, we always have to track our value in
        assert config['source'] != 'environ'

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

        assert 'env_name' in config

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
                # the superclass should have unset this so we inherit instead of using it
                assert local_state_file.get_value(['variables', requirement.env_var]) is None
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

    def provide(self, requirement, context):
        """Override superclass to create or update our environment."""
        assert 'PATH' in context.environ

        conda = new_conda_manager(context.frontend)

        # set from the inherited vale if necessary
        if context.status.analysis.config['source'] == 'inherited':
            context.environ[requirement.env_var] = context.status.analysis.config['value']

        # set the env var (but not PATH, etc. to fully activate, that's done below)
        super_result = super(CondaEnvProvider, self).provide(requirement, context)

        project_dir = context.environ['PROJECT_DIR']

        env_name = context.status.analysis.config.get('env_name', context.default_env_spec_name)
        env_spec = requirement.env_specs.get(env_name)

        if env_name == 'bootstrap-env':
            # The bootstrap environment is always stored in the project directory
            # TODO: have this respect ANACONDA_PROJECT_ENVS_PATH
            prefix = os.path.join(project_dir, 'envs', 'bootstrap-env')
        elif context.status.analysis.config['source'] == 'inherited':
            prefix = context.environ.get(requirement.env_var, None)
            inherited = True
        else:
            prefix = None
            inherited = False

        if prefix is None:
            # use the default environment
            prefix = env_spec.path(project_dir)

        assert prefix is not None

        # if the value has changed, choose the matching env spec
        # (something feels wrong here; should this be in read_config?
        # or not at all?)
        for env in requirement.env_specs.values():
            if env.path(project_dir) == prefix:
                env_spec = env
                break

        if context.mode != PROVIDE_MODE_CHECK:
            # we update the environment in both prod and dev mode
            # TODO if not creating a named env, we could use the
            # shared packages, but for now we leave it alone
            assert env_spec is not None

            deviations = conda.find_environment_deviations(prefix, env_spec)

            readonly_policy = os.environ.get('ANACONDA_PROJECT_READONLY_ENVS_POLICY', 'fail').lower()

            if deviations.unfixable and readonly_policy in ('clone', 'replace'):
                # scan for writable path
                destination = env_spec.path(project_dir, reset=True, force_writable=True)
                if destination != prefix:
                    if readonly_policy == 'replace':
                        print('Replacing the readonly environment {}'.format(prefix))
                        deviations = conda.find_environment_deviations(destination, env_spec)
                    else:
                        print('Cloning the readonly environment {}'.format(prefix))
                        conda_api.clone(destination,
                                        prefix,
                                        stdout_callback=context.frontend.partial_info,
                                        stderr_callback=context.frontend.partial_error)
                    prefix = destination

            try:
                conda.fix_environment_deviations(prefix, env_spec, create=(not inherited))
            except CondaManagerError as e:
                return super_result.copy_with_additions(errors=[str(e)])

        conda_api.environ_set_prefix(context.environ, prefix, varname=requirement.env_var)

        path = context.environ.get("PATH", "")

        context.environ["PATH"] = conda_api.set_conda_env_in_path(path, prefix)
        # Some stuff can only be done when a shell is launched:
        #  - we can't set PS1 because it shouldn't be exported.
        #  - we can't run conda activate scripts because they are sourced.
        # We can do these in the output of our activate command, but not here.

        return super_result

    def unprovide(self, requirement, environ, local_state_file, overrides, requirement_status=None):
        """Override superclass to delete project-scoped envs directory."""
        config = self.read_config(
            requirement,
            environ,
            local_state_file,
            # future: pass in this default_env_spec_name
            default_env_spec_name='default',
            overrides=overrides)

        env_path = config.get('value', None)
        assert env_path is not None
        return _remove_env_path(env_path, environ['PROJECT_DIR'])
