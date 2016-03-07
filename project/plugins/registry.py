"""The plugin registry (used to locate plugins)."""
from __future__ import absolute_import, print_function


class PluginRegistry(object):
    """Allows creating Requirement and Provider instances."""

    def find_requirement_by_env_var(self, env_var, options):
        """Create a requirement instance given an environment variable name.

        Args:
            env_var (str): environment variable name
            options (dict): options from the project file for this requirement

        Returns:
            instance of Requirement
        """
        # future goal will be to un-hardcode this
        if env_var == 'REDIS_URL':
            from .requirements.redis import RedisRequirement
            return RedisRequirement(registry=self, env_var=env_var, options=options)
        elif env_var == 'CONDA_ENV_PATH':
            from .requirements.conda_env import CondaEnvRequirement
            return CondaEnvRequirement(registry=self, env_var=env_var, options=options)
        elif env_var == 'ANACONDA_MASTER_PASSWORD':
            from .requirements.master_password import MasterPasswordRequirement
            return MasterPasswordRequirement(registry=self, options=options)
        else:
            from .requirement import EnvVarRequirement
            return EnvVarRequirement(registry=self, env_var=env_var, options=options)

    def find_provider_by_class_name(self, class_name):
        """Look up a provider by class name.

        Args:
            class_name (str): name of the provider class

        Returns:
            an instance of the passed-in class name or None if not found
        """
        # future goal will be to un-hardcode this of course
        if class_name == 'CondaEnvProvider':
            from .providers.conda_env import CondaEnvProvider
            return CondaEnvProvider()
        elif class_name == 'MasterPasswordProvider':
            from .providers.master_password import MasterPasswordProvider
            return MasterPasswordProvider()
        elif class_name == 'RedisProvider':
            from .providers.redis import RedisProvider
            return RedisProvider()
        elif class_name == 'EnvVarProvider':
            from .provider import EnvVarProvider
            return EnvVarProvider()
        else:
            return None
