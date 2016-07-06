# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""The plugin registry (used to locate plugins)."""
from __future__ import absolute_import, print_function

from collections import namedtuple

ServiceType = namedtuple('ServiceType', ['name', 'default_variable', 'description'])


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
        from .requirement import EnvVarRequirement
        return EnvVarRequirement(registry=self, env_var=env_var, options=options)

    def find_requirement_by_service_type(self, service_type, env_var, options):
        """Create a requirement instance given a service type.

        Args:
            service_type (str): name of the service type
            env_var (str): environment variable name
            options (dict): options from the project file for this requirement

        Returns:
            instance of ServiceRequirement
        """
        if 'type' not in options or options['type'] != service_type:
            options = options.copy()
            options['type'] = service_type

        # future goal will be to un-hardcode this
        if service_type == 'redis':
            from .requirements.redis import RedisRequirement
            return RedisRequirement(registry=self, env_var=env_var, options=options)
        else:
            return None

    def list_service_types(self):
        """List known service types.

        Returns:
           iterable of ``ServiceType`` named tuples with (name,default_variable,description)
        """
        return [ServiceType(name='redis', default_variable='REDIS_URL', description='A Redis server')]

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
        elif class_name == 'RedisProvider':
            from .providers.redis import RedisProvider
            return RedisProvider()
        elif class_name == 'EnvVarProvider':
            from .provider import EnvVarProvider
            return EnvVarProvider()
        elif class_name == 'DownloadProvider':
            from .providers.download import DownloadProvider
            return DownloadProvider()
        else:
            return None
