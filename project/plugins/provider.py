"""Types related to project requirement providers."""
from __future__ import absolute_import

from abc import ABCMeta, abstractmethod
from copy import deepcopy
import errno
import os

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
            from .providers.redis import DefaultRedisProvider, ProjectScopedRedisProvider
            return [DefaultRedisProvider(), ProjectScopedRedisProvider()]
        else:
            return []


class ProvideContext(object):
    """A context passed to ``Provider.provide()`` representing state that can be modified."""

    def __init__(self, environ, local_state_file, config):
        """Create a ProvideContext.

        Args:
            environ (dict): environment variables to be read and modified
            local_state_file (LocalStateFile): to store any created state
            config (dict): configuration for the provider
        """
        self.environ = environ
        self._local_state_file = local_state_file
        self._logs = []
        self._errors = []
        # defensive copy so we don't modify what was passed in
        self._config = deepcopy(config)

    def ensure_work_directory(self, relative_name):
        """Create a project-scoped work directory with the given name.

        Args:
            relative_name (str): name to distinguish this dir from other work directories
        """
        path = os.path.join(os.path.dirname(self._local_state_file.filename), "run", relative_name)
        try:
            os.makedirs(path)
        except IOError as e:
            if e.errno != errno.EEXIST:
                raise e
        return path

    def transform_service_run_state(self, service_name, func):
        """Run a function which takes and potentially modifies the state of a service.

        If the function modifies the state it's given, the new state will be saved
        and passed in next time.

        Args:
            service_name (str): the name of the service, should be
                specific enough to uniquely identify the provider
            func (function): function to run, passing it the current state

        Returns:
            Whatever ``func`` returns.
        """
        old_state = self._local_state_file.get_service_run_state(service_name)
        modified = deepcopy(old_state)
        result = func(modified)
        if modified != old_state:
            self._local_state_file.set_service_run_state(service_name, modified)
            self._local_state_file.save()
        return result

    def append_log(self, message):
        """Add extra log information that may help debug errors."""
        self._logs.append(message)

    def append_error(self, error):
        """Add a fatal error message (that blocked the provide() from succeeding)."""
        self._errors.append(error)

    @property
    def errors(self):
        """Get any fatal errors that occurred during provide()."""
        return self._errors

    @property
    def logs(self):
        """Get any debug logs that occurred during provide()."""
        return self._logs

    @property
    def config(self):
        """Get the configuration dict for the provider."""
        return self._config


class Provider(with_metaclass(ABCMeta)):
    """A Provider can take some action to meet a Requirement."""

    @property
    @abstractmethod
    def title(self):
        """Human-friendly title of the provider."""
        pass  # pragma: no cover

    @property
    def config_key(self):
        """When we store config for this provider, we use this as the key."""
        return self.__class__.__name__

    @abstractmethod
    def provide(self, requirement, context):
        """Execute the provider, fulfilling the requirement.

        The implementation should read and modify the passed-in
        ``environ`` rather than accessing the OS environment
        directly.

        Args:
            requirement (Requirement): requirement we want to meet
            context (ProvideContext): context containing project state

        """
        pass  # pragma: no cover


class EnvVarProvider(Provider):
    """Meets a requirement for an env var by letting people set it manually."""

    @property
    def title(self):
        """Override superclass with our title."""
        return "Manually set environment variable"

    def provide(self, requirement, context):
        """Override superclass to do nothing (future: read env var from saved state)."""
        # future: we should be able to read the env var from
        # project state. For now, assume someone set it
        # when launching the app.
        pass
