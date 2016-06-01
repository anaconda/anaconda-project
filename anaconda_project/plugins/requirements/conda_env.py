# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Conda-env-related requirements."""
from __future__ import absolute_import, print_function

import platform

from anaconda_project.plugins.requirement import EnvVarRequirement
from anaconda_project.conda_manager import new_conda_manager, CondaManagerError


class CondaEnvRequirement(EnvVarRequirement):
    """A requirement for CONDA_ENV_PATH (or CONDA_DEFAULT_ENV on Windows) to point to a conda env."""

    def __init__(self, registry, environments=None, default_environment_name='default'):
        """Extend superclass to default to CONDA_ENV_PATH and carry environment information.

        Args:
            registry (PluginRegistry): plugin registry
            environments (dict): dict from env name to ``CondaEnvironment``
            default_environment_name (str): name of env to use by default
        """
        if platform.system() == 'Windows':
            # On Windows, activate.bat never sets CONDA_ENV_PATH but
            # sets CONDA_DEFAULT_ENV to the full path to the environment.
            env_var = "CONDA_DEFAULT_ENV"
        else:
            # On Unix, activate script sets CONDA_ENV_PATH to the full
            # path, and sets CONDA_DEFAULT_ENV to either just the env
            # name or the full path.
            env_var = "CONDA_ENV_PATH"
        super(CondaEnvRequirement, self).__init__(registry=registry, env_var=env_var)
        self.environments = environments
        self.default_environment_name = default_environment_name
        self._conda = new_conda_manager()

    @property
    def title(self):
        """Override superclass to provide our title."""
        return "A Conda environment"

    @property
    def description(self):
        """Override superclass to provide our description."""
        return "The project needs a Conda environment containing all required packages."

    @property
    def ignore_patterns(self):
        """Override superclass with our ignore patterns."""
        return set(['/envs/'])

    def _status_from_analysis(self, environ, local_state_file, analysis):
        config = analysis.config

        assert 'source' in config
        assert config['source'] != 'default'
        assert config['source'] != 'unset'

        prefix = None
        if 'value' in config and (config['source'] == 'variables' or config['source'] == 'project'):
            prefix = config['value']
        elif config['source'] == 'environ' and local_state_file.get_value('inherit_environment', default=False):
            prefix = environ.get(self.env_var, None)

        # At present we change 'unset' to 'project' and then use the default env,
        # so prefix of None should not be possible.
        # if prefix is None: return (False, "A Conda environment hasn't been chosen for this project.")
        assert prefix is not None

        env_name = config.get('env_name', None)
        if env_name is not None:
            environment_spec = self.environments[env_name]

            try:
                deviations = self._conda.find_environment_deviations(prefix, environment_spec)
                if not deviations.ok:
                    return (False, deviations.summary)

            except CondaManagerError as e:
                return (False, str(e))

        current_env_setting = environ.get(self.env_var, None)

        if current_env_setting is None:
            # this is our vaguest / least-descriptionful message so only if we didn't do better above
            return (False, "%s is not set." % self.env_var)
        elif current_env_setting != prefix:
            return (False, ("%s is set to %s instead of %s." % (self.env_var, current_env_setting, prefix)))
        else:
            return (True, "Using Conda environment %s." % prefix)

    def check_status(self, environ, local_state_file, overrides, latest_provide_result=None):
        """Override superclass to get our status."""
        return self._create_status_from_analysis(environ,
                                                 local_state_file,
                                                 overrides=overrides,
                                                 provider_class_name='CondaEnvProvider',
                                                 status_getter=self._status_from_analysis,
                                                 latest_provide_result=latest_provide_result)
