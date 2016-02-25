"""Types related to project requirement providers."""
from __future__ import absolute_import

from abc import ABCMeta, abstractmethod
from copy import deepcopy
import os

from project.internal.metaclass import with_metaclass
from project.internal.makedirs import makedirs_ok_if_exists
from project.internal.crypto import encrypt_string, decrypt_string


class ProviderConfigContext(object):
    """A context passed to config-related methods on Provider."""

    def __init__(self, environ, local_state_file, requirement):
        """Construct a ProviderConfigContext."""
        self.environ = environ
        self.local_state_file = local_state_file
        self.requirement = requirement


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
        makedirs_ok_if_exists(path)
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

    def missing_env_vars_to_configure(self, requirement, environ, local_state_file):
        """Get a list of unset environment variable names that must be set before configuring this provider.

        Args:
            requirement (Requirement): requirement instance we are providing for
            environ (dict): current environment variable dict
            local_state_file (LocalStateFile): local state file
        """
        return ()

    def missing_env_vars_to_provide(self, requirement, environ, local_state_file):
        """Get a list of unset environment variable names that must be set before calling provide().

        Args:
            requirement (Requirement): requirement instance we are providing for
            environ (dict): current environment variable dict
            local_state_file (LocalStateFile): local state file
        """
        return ()

    @abstractmethod
    def read_config(self, context):
        """Read a config dict from the local state file for the given requirement."""
        pass  # pragma: no cover

    def set_config_values_as_strings(self, context, values):
        """Set some config values in the state file (should not save the file).

        Args:
            context (ProviderConfigContext): context
            values (dict): dict from string to string
        """
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
        be set back using ``set_config_values_as_strings()``.

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

    def _local_state_override(self, requirement, local_state_file):
        return local_state_file.get_value(["variables", requirement.env_var], default=None)

    def _key_from_value(cls, value):
        if isinstance(value, dict) and 'key' in value:
            return value['key']
        else:
            return None

    def missing_env_vars_to_configure(self, requirement, environ, local_state_file):
        """Override superclass to require encryption key variable if this env var is encrypted."""
        # we need the master password to either read from local
        # state file, or save a new value to the local state file,
        # but we do NOT need it if the env var is already set
        # (which is likely to happen in a production-server-type
        # deployment)
        local_override = self._local_state_override(requirement, local_state_file)
        local_override_key = self._key_from_value(local_override)
        if local_override_key is not None:
            if local_override_key not in environ:
                return (local_override_key, )
            else:
                return ()
        elif requirement.encrypted and requirement.env_var not in environ:
            # default key - we'll need this to save the encrypted value
            return ('ANACONDA_MASTER_PASSWORD', )
        else:
            return ()

    def missing_env_vars_to_provide(self, requirement, environ, local_state_file):
        """Override superclass to require encryption key variable if this env var is encrypted."""
        local_override = self._local_state_override(requirement, local_state_file)
        local_override_key = self._key_from_value(local_override)
        if local_override_key is not None:
            if local_override_key not in environ:
                return (local_override_key, )
            else:
                return ()
        elif requirement.env_var in environ:
            # nothing to decrypt
            return ()
        else:
            default_key = self._key_from_value(requirement.options.get('default', None))
            if default_key is not None:
                return (default_key, )
            else:
                return ()

    def read_config(self, context):
        """Override superclass to read env var value."""
        config = dict()
        value = self._local_state_override(context.requirement, context.local_state_file)
        key = self._key_from_value(value)
        if value is not None:
            if key is not None:
                # TODO: we need to deal with missing 'encrypted'
                # or with a bad password in some way
                encrypted = value['encrypted']
                value = decrypt_string(encrypted, context.environ[key])
            config['value'] = value
        return config

    def set_config_values_as_strings(self, context, values):
        """Override superclass to set env var value."""
        if 'value' in values:

            value_string = values['value']

            local_override_value = self._local_state_override(context.requirement, context.local_state_file)

            key = self._key_from_value(local_override_value)
            if key is None and context.requirement.encrypted:
                key = 'ANACONDA_MASTER_PASSWORD'

            if key is not None:
                value = dict(key=key, encrypted=encrypt_string(value_string, context.environ[key]))
            else:
                value = value_string
            context.local_state_file.set_value(["variables", context.requirement.env_var], value)

    def config_html(self, requirement):
        """Override superclass to provide our config html."""
        if requirement.encrypted:
            input_type = 'password'
        else:
            input_type = 'text'
        return """
<form>
  <label>Value: <input type="{input_type}" name="value"/></label>
</form>
""".format(input_type=input_type)

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
            value = requirement.options['default']
            default_key = self._key_from_value(value)
            if default_key is not None:
                if 'encrypted' not in value:
                    context.append_error("No 'encrypted' field in the default value of %s" % (requirement.env_var))
                    return
                value = decrypt_string(value['encrypted'], context.environ[default_key])
            if isinstance(value, dict) or isinstance(value, list):
                context.append_error("Value of '%s' should be a string not %r" % (requirement.env_var, value))
            else:
                value = str(value)  # convert number, bool, null to a string
                context.environ[requirement.env_var] = value
        else:
            pass
