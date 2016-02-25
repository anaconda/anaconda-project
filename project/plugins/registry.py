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
        elif env_var == 'CONDA_DEFAULT_ENV':
            from .requirements.conda_env import CondaEnvRequirement
            return CondaEnvRequirement(registry=self, env_var=env_var, options=options)
        elif env_var == 'ANACONDA_MASTER_PASSWORD':
            from .requirements.master_password import MasterPasswordRequirement
            return MasterPasswordRequirement(registry=self, options=options)
        else:
            from .requirement import EnvVarRequirement
            return EnvVarRequirement(registry=self, env_var=env_var, options=options)

    def find_providers_by_env_var(self, requirement, env_var):
        """Look up providers for the given requirement which needs the given env_var.

        Args:
            requirement (Requirement): the requirement we want to provide
            env_var (str): name of the environment variable the requirement wants

        Returns:
            list of Provider
        """
        from .provider import EnvVarProvider
        return [EnvVarProvider()]

    def find_providers_by_service(self, requirement, service):
        """Look up providers for the given requirement by service name.

        Args:
            requirement (Requirement): the requirement we want to provide
            service (str): conventional name of the service the requirement wants

        Returns:
            list of Provider
        """
        # future goal will be to un-hardcode this of course
        if service == 'redis':
            from .providers.redis import DefaultRedisProvider, ProjectScopedRedisProvider
            return [DefaultRedisProvider(), ProjectScopedRedisProvider()]
        else:
            return []

    def find_provider_by_class_name(self, class_name):
        """Look up a provider by class name.

        Args:
            class_name (str): name of the provider class

        Returns:
            an instance of the passed-in class name or None if not found
        """
        # future goal will be to un-hardcode this of course
        if class_name == 'ProjectScopedCondaEnvProvider':
            from .providers.conda_env import ProjectScopedCondaEnvProvider
            return ProjectScopedCondaEnvProvider()
        elif class_name == 'MasterPasswordProvider':
            from .providers.master_password import MasterPasswordProvider
            return MasterPasswordProvider()
        else:
            return None
