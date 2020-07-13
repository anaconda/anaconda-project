# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Redis-related requirements."""

from anaconda_project.requirements_registry.requirements.service import ServiceRequirement
# don't "import from" network_util or we can't monkeypatch it in tests
import anaconda_project.requirements_registry.network_util as network_util


class RedisRequirement(ServiceRequirement):
    """A requirement for REDIS_URL (or another specified env var) to point to a running Redis."""
    @property
    def description(self):
        """Override superclass to supply our description."""
        return self._description("A running Redis server, located by a redis: URL set as %s." % (self.env_var))

    def _why_not_provided(self, environ):
        url = self._get_value_of_env_var(environ)
        if url is None:
            return self._unset_message()
        split = network_util.urlparse.urlsplit(url)
        if split.scheme != 'redis':
            return "{env_var} value '{url}' does not have 'redis:' scheme.".format(env_var=self.env_var, url=url)
        port = 6379
        if split.port is not None:
            port = split.port
        if network_util.can_connect_to_socket(split.hostname, port):
            return None
        else:
            return "Cannot connect to Redis at {url}.".format(url=url)

    def check_status(self, environ, local_state_file, default_env_spec_name, overrides, latest_provide_result=None):
        """Override superclass to get our status."""
        why_not_provided = self._why_not_provided(environ)

        has_been_provided = why_not_provided is None
        if has_been_provided:
            status_description = ("Using Redis server at %s" % self._get_value_of_env_var(environ))
        else:
            status_description = why_not_provided

        return self._create_status(environ,
                                   local_state_file,
                                   default_env_spec_name,
                                   overrides=overrides,
                                   has_been_provided=has_been_provided,
                                   status_description=status_description,
                                   provider_class_name='RedisProvider',
                                   latest_provide_result=latest_provide_result)
