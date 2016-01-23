"""Types related to project requirement providers."""
from __future__ import absolute_import

from abc import ABCMeta, abstractmethod

from project.internal.metaclass import with_metaclass


class ProviderRegistry(object):
    """Allows looking up providers that can fulfill requirements."""

    def find_by_env_var(self, requirement, env_var):
        """Look up a provider for the given requirement which needs the given env_var.

        Args:
            requirement (Requirement): the requirement we want to provide
            env_var (str): name of the environment variable the requirement wants

        Returns:
            list of Provider
        """
        return [EnvVarProvider()]

    def find_by_service(self, requirement, service):
        """Look up a provider for the given requirement by service name.

        Args:
            requirement (Requirement): the requirement we want to provide
            service (str): conventional name of the service the requirement wants

        Returns:
            list of Provider
        """
        # future goal will be to un-hardcode this of course
        if service == 'redis':
            from .providers.redis import DefaultRedisProvider
            return [DefaultRedisProvider()]
        else:
            return []


class Provider(with_metaclass(ABCMeta)):
    """Instances can take some action to meet a Requirement."""

    @property
    @abstractmethod
    def title(self):
        """Human-friendly title of the provider."""
        pass  # pragma: no cover

    @abstractmethod
    def provide(self, requirement, environ):
        """Execute the provider, fulfilling the requirement.

        The implementation should read and modify the passed-in
        ``environ`` rather than accessing the OS environment
        directly.

        Args:
            requirement (Requirement): requirement we want to meet
            environ (dict): dict from str to str, representing environment variables

        """
        pass  # pragma: no cover


class EnvVarProvider(Provider):
    """Meets a requirement for an env var by letting people set it manually."""

    @property
    def title(self):
        """Override superclass with our title."""
        return "Manually set environment variable"

    def provide(self, requirement, environ):
        """Override superclass to do nothing (future: read env var from saved state)."""
        # future: we should be able to read the env var from
        # project state. For now, assume someone set it
        # when launching the app.
        pass
