# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Conda-env-related requirements."""
from __future__ import absolute_import, print_function

from os.path import join

from anaconda_project.requirements_registry.requirement import EnvVarRequirement, RequirementStatus
from anaconda_project.conda_manager import new_conda_manager, CondaManagerError
from anaconda_project.internal import conda_api


class CondaEnvRequirement(EnvVarRequirement):
    """A requirement for CONDA_PREFIX to point to a conda env."""

    _provider_class_name = 'CondaEnvProvider'

    def __init__(self, registry, env_specs=None, env_var=None):
        """Extend superclass to default to CONDA_PREFIX and carry environment information.

        Args:
            registry (RequirementsRegistry): plugin registry
            env_specs (dict): dict from env name to ``CondaEnvironment``
        """
        if env_var is None:
            env_var = conda_api.conda_prefix_variable()

        super(CondaEnvRequirement, self).__init__(registry=registry, env_var=env_var)
        self.env_specs = env_specs
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
        if 'value' in config and config['source'] in ('variables', 'project', 'inherited', 'environ'):
            prefix = config['value']

        assert prefix is not None

        env_name = config.get('env_name', None)
        if env_name is not None:
            environment_spec = self.env_specs[env_name]

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
        else:
            return (True, "Using Conda environment %s." % prefix)

    def check_status(self, environ, local_state_file, default_env_spec_name, overrides, latest_provide_result=None):
        """Override superclass to get our status."""
        return self._create_status_from_analysis(environ,
                                                 local_state_file,
                                                 default_env_spec_name,
                                                 overrides=overrides,
                                                 provider_class_name=self._provider_class_name,
                                                 status_getter=self._status_from_analysis,
                                                 latest_provide_result=latest_provide_result)


class CondaBootstrapEnvRequirement(CondaEnvRequirement):
    """A requirement for CONDA_PREFIX to point to a conda env."""

    _provider_class_name = 'CondaBootstrapEnvProvider'

    def __init__(self, registry, env_specs=None):
        """Extend superclass to default to CONDA_PREFIX and carry environment information.

        Args:
            registry (RequirementsRegistry): plugin registry
            env_specs (dict): dict from env name to ``CondaEnvironment``
        """
        super(CondaBootstrapEnvRequirement, self).__init__(registry=registry, env_var="BOOTSTRAP_ENV_PREFIX")
        self.env_specs = env_specs
        self._conda = new_conda_manager()

    @property
    def description(self):
        """Override superclass to provide our description."""
        return "The project needs a Conda bootstrap environment containing all required packages."

    @property
    def title(self):
        """Override superclass to provide our title."""
        return "Anaconda-project bootstrap environment"

    def _status_from_analysis(self, environ, local_state_file, analysis):
        config = analysis.config

        assert 'source' in config

        # we expect the bootstrap env to not be the env running the cmd
        assert config['source'] in ['unset', 'environ', 'project']

        env_name = 'bootstrap-env'
        prefix = join(environ['PROJECT_DIR'], 'envs', env_name)

        if config['source'] == 'environ':
            assert config['value'] == prefix

        environment_spec = self.env_specs[env_name]

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
        else:
            return (True, "Using Conda environment %s." % prefix)

    def _create_status_from_analysis(self, environ, local_state_file, default_env_spec_name, overrides,
                                     latest_provide_result, provider_class_name, status_getter):
        provider = self.registry.find_provider_by_class_name(provider_class_name)
        analysis = provider.analyze(self, environ, local_state_file, default_env_spec_name, overrides)
        (has_been_provided, status_description) = status_getter(environ, local_state_file, analysis)

        # hardcode bootstrap env name since it's a very especial case
        env_spec_name = 'bootstrap-env'

        return RequirementStatus(self,
                                 has_been_provided=has_been_provided,
                                 status_description=status_description,
                                 provider=provider,
                                 analysis=analysis,
                                 latest_provide_result=latest_provide_result,
                                 env_spec_name=env_spec_name)
