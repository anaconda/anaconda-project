"""Conda-env-related requirements."""
from __future__ import absolute_import, print_function

import os

from project.plugins.requirement import EnvVarRequirement
import project.internal.conda_api as conda_api


class CondaEnvRequirement(EnvVarRequirement):
    """A requirement for CONDA_ENV_PATH (or another specified env var) to point to a conda env."""

    def __init__(self,
                 registry,
                 env_var="CONDA_ENV_PATH",
                 options=None,
                 environments=None,
                 default_environment_name='default'):
        """Extend superclass to default to CONDA_ENV_PATH and carry environment information.

        Args:
            registry (PluginRegistry): plugin registry
            env_var (str): env var name
            options (dict): options from the config
            environments (dict): dict from env name to ``CondaEnvironment``
            default_environment_name (str): name of env to use by default
        """
        super(CondaEnvRequirement, self).__init__(registry=registry, env_var=env_var, options=options)
        self.environments = environments
        self.default_environment_name = default_environment_name

    @property
    def title(self):
        """Override superclass to provide our title."""
        return "A Conda environment"

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

        if not os.path.isdir(os.path.join(prefix, 'conda-meta')):
            return (False, "'%s' doesn't look like it contains a Conda environment yet." % (prefix))

        env_name = config.get('env_name', None)
        if env_name is not None:
            environment_spec = self.environments[env_name]

            if len(environment_spec.dependencies) > 0:
                try:
                    installed = conda_api.installed(prefix)
                except conda_api.CondaError as e:
                    return (False, "Conda failed while listing installed packages in %s: %s" % (prefix, str(e)))

                missing = set()

                # TODO: we don't verify that the environment contains the right versions
                # https://github.com/Anaconda-Server/anaconda-project/issues/77
                for name in environment_spec.conda_package_names_set:
                    if name not in installed:
                        missing.add(name)

                if len(missing) > 0:
                    sorted = list(missing)
                    sorted.sort()
                    return (False, "Conda environment is missing packages: %s" % (", ".join(sorted)))

        if environ.get(self.env_var, None) is None:
            # this is our vaguest / least-helpful message so only if we didn't do better above
            return (False, "%s is not set." % self.env_var)
        else:
            return (True, "Using Conda environment %s." % prefix)

    def check_status(self, environ, local_state_file):
        """Override superclass to get our status."""
        return self._create_status_from_analysis(environ,
                                                 local_state_file,
                                                 provider_class_name='CondaEnvProvider',
                                                 status_getter=self._status_from_analysis)
