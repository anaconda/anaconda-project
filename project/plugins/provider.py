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
    def read_config(self, local_state_file, requirement):
        """Read a config dict from the local state file for the given requirement."""
        pass  # pragma: no cover

    def set_config_value_from_string(self, local_state_file, requirement, name, value_string):
        """Set a config value in the state file (should not save the file)."""
        pass  # silently ignore unknown config values

    def config_html(self, requirement):
        """Get an HTML string for configuring the provider.

        The HTML string must contain a single <form> tag. Any
        <input>, <textarea>, and <select> elements should have
        their name attribute set to match the dict keys used in
        ``read_config()``'s result.  The <form> should not have a
        submit button, since it will be merged with other
        forms. The initial state of all the form fields will be
        auto-populated from the values in ``read_config()``.  When
        the form is submitted, any changes made by the user will
        be set back using ``set_config_value_from_string()``.

        This is simple to use, but for now not very flexible; if you need
        more flexibility let us know and we can figure out what API
        to add in future versions.

        Returns:
            An HTML string or None if there's nothing to configure.

        """
        return None

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

    def read_config(self, local_state_file, requirement):
        """Override superclass to read env var value."""
        config = dict()
        value = local_state_file.get_value("variables", requirement.env_var, default=None)
        if value is not None:
            config['value'] = value
        return config

    def set_config_value_from_string(self, local_state_file, requirement, name, value_string):
        """Override superclass to set env var value."""
        if name == "value":
            local_state_file.set_value("variables", requirement.env_var, value_string)

    def config_html(self, requirement):
        """Override superclass to provide our config html."""
        return """
<form>
  <label>Value: <input type="text" name="value"/></label>
</form>
"""

    def provide(self, requirement, context):
        """Override superclass to use configured env var (or already-set env var)."""
        # We prefer the values in this order:
        #  - value set in project-local state overrides everything
        #    (otherwise the UI for configuring the value would end
        #    up ignored)
        #  - then anything already set in the environment wins, so you
        #    can override on the command line like `FOO=bar myapp`
        #  - then the project.yml default value
        if 'value' in context.config:
            # .anaconda/project-local.yml
            #
            # variables:
            #   REDIS_URL: "redis://example.com:1234"
            context.environ[requirement.env_var] = context.config['value']
        elif requirement.env_var in context.environ:
            # nothing to do here
            pass
        elif 'default' in requirement.options:
            # project.yml
            #
            # runtime:
            #   REDIS_URL:
            #     default: "redis://example.com:1234"
            context.environ[requirement.env_var] = requirement.options['default']
        else:
            pass
