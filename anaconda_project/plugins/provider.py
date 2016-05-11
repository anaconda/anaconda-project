# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Types related to project requirement providers."""
from __future__ import absolute_import

from abc import ABCMeta, abstractmethod
from copy import deepcopy
import os
import shutil
import subprocess

from anaconda_project.internal.metaclass import with_metaclass
from anaconda_project.internal.makedirs import makedirs_ok_if_exists
from anaconda_project.internal.crypto import encrypt_string, decrypt_string
from anaconda_project.internal.simple_status import SimpleStatus

# py27/py3 compatibility
try:  # pragma: no cover
    basestring  # pragma: no cover
except NameError:  # pragma: no cover
    basestring = str  # pragma: no cover


def _service_directory(local_state_file, relative_name):
    return os.path.join(os.path.dirname(local_state_file.filename), "services", relative_name)


class ProvideContext(object):
    """A context passed to ``Provider.provide()`` representing state that can be modified."""

    def __init__(self, environ, local_state_file, status, mode):
        """Create a ProvideContext.

        Args:
            environ (dict): environment variables to be read and modified
            local_state_file (LocalStateFile): to store any created state
            status (RequirementStatus): current status
            mode (str): one of PROVIDE_MODE_PRODUCTION, PROVIDE_MODE_DEVELOPMENT, PROVIDE_MODE_CHECK
        """
        self.environ = environ
        self._local_state_file = local_state_file
        self._status = status
        self._mode = mode

    def ensure_service_directory(self, relative_name):
        """Create a directory in PROJECT_DIR/services with the given name.

        The name should be unique to the ServiceRequirement creating the directory,
        so usually the requirement's env var.

        Args:
            relative_name (str): name to distinguish this dir from other service directories
        """
        path = _service_directory(self._local_state_file, relative_name)
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

    @property
    def status(self):
        """Get the current ``RequirementStatus``."""
        return self._status

    @property
    def local_state_file(self):
        """Get the LocalStateFile."""
        return self._local_state_file

    @property
    def mode(self):
        """Get flavor of provide.

        Value should be ``PROVIDE_MODE_DEVELOPMENT``, ``PROVIDE_MODE_PRODUCTION``, or ``PROVIDE_MODE_CHECK``.
        """
        return self._mode


def shutdown_service_run_state(local_state_file, service_name):
    """Run any shutdown commands from the local state file for the given service.

    Also remove the shutdown commands from the file.

    Args:
        local_state_file (LocalStateFile): local state
        service_name (str): the name of the service, usually a
            variable name, should be specific enough to uniquely
            identify the provider

    Returns:
        a `Status` instance potentially containing errors
    """
    run_states = local_state_file.get_all_service_run_states()
    if service_name not in run_states:
        return SimpleStatus(success=True, description=("Nothing to do to shut down %s." % service_name))

    errors = []
    state = run_states[service_name]
    if 'shutdown_commands' in state:
        commands = state['shutdown_commands']
        for command in commands:
            code = subprocess.call(command)
            if code != 0:
                errors.append("Shutting down %s, command %s failed with code %d." % (service_name, repr(command), code))
    # clear out the run state once we try to shut it down
    local_state_file.set_service_run_state(service_name, dict())
    local_state_file.save()

    if errors:
        return SimpleStatus(success=False,
                            description=("Shutdown commands failed for %s." % service_name),
                            errors=errors)
    else:
        return SimpleStatus(success=True, description=("Successfully shut down %s." % service_name))


def delete_service_directory(local_state_file, relative_name):
    """Delete a directory in PROJECT_DIR/services with the given name.

    The name should be unique to the ServiceRequirement creating the directory,
    so usually the requirement's env var.

    IF this fails, it does so silently (returns no errors).

    Args:
        relative_name (str): name to distinguish this dir from other service directories

    Returns:
        None
    """
    path = _service_directory(local_state_file, relative_name)
    try:
        shutil.rmtree(path=path)
    except OSError:
        pass
    # also delete the services directory itself, if it's now empty
    try:
        # this fails on non-empty dir
        os.rmdir(os.path.dirname(path))
    except OSError:
        pass


class ProviderAnalysis(object):
    """A Provider's preflight check snapshotting the state prior to ``provide()``.

    Instances of this class are immutable, and are usually created as part of a
    ``RequirementStatus``.
    """

    def __init__(self, config, missing_env_vars_to_configure, missing_env_vars_to_provide):
        """Create a ProviderAnalysis."""
        self._config = deepcopy(config)  # defensive copy so we don't modify the original
        self._missing_env_vars_to_configure = missing_env_vars_to_configure
        self._missing_env_vars_to_provide = missing_env_vars_to_provide

    @property
    def config(self):
        """Get the configuration dict from the time of analysis."""
        return self._config

    @property
    def missing_env_vars_to_configure(self):
        """Get the env vars we were missing in order to configure, from the time of analysis."""
        return self._missing_env_vars_to_configure

    @property
    def missing_env_vars_to_provide(self):
        """Get the env vars we were missing in order to provide, from the time of analysis."""
        return self._missing_env_vars_to_provide


class ProvideResult(object):
    """A Provider's results from the ``provide()`` call.

    Instances of this class are immutable, and are returned from ``provide()``.
    """

    def __init__(self, errors=None, logs=None):
        """Create a ProvideResult."""
        if errors is None:
            errors = []
        if logs is None:
            logs = []
        self._errors = errors
        self._logs = logs

    def copy_with_additions(self, errors=None, logs=None):
        """Copy this result, appending additional errors and logs."""
        if errors is None:
            errors = []
        if logs is None:
            logs = []
        if len(errors) == 0 and len(logs) == 0:
            # we don't have to actually copy since we are immutable
            return self
        else:
            return ProvideResult(errors=(self._errors + errors), logs=(self._logs + logs))

    @property
    def errors(self):
        """Get any fatal errors that occurred during provide() preventing success."""
        return self._errors

    @property
    def logs(self):
        """Get any debug logs that occurred during provide()."""
        return self._logs

    @classmethod
    def empty(cls):
        """Get an empty ProvideResult (currently a singleton since these are immutable)."""
        return _emptyProvideResult

# get this via ProvideResult.empty()
_emptyProvideResult = ProvideResult()


class Provider(with_metaclass(ABCMeta)):
    """A Provider can take some action to meet a Requirement."""

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
    def read_config(self, requirement, environ, local_state_file, overrides):
        """Read a config dict from the local state file for the given requirement.

        Args:
            requirement (Requirement): the requirement we're providing
            environ (dict): current environment variables
            local_state_file (LocalStateFile): file to read from
            overrides (UserConfigOverrides): user-supplied forced config
        """
        pass  # pragma: no cover

    def set_config_values_as_strings(self, requirement, environ, local_state_file, overrides, values):
        """Set some config values in the state file (should not save the file).

        Args:
            requirement (Requirement): the requirement we're providing
            environ (dict): current environment variables
            local_state_file (LocalStateFile): file to save to
            overrides (UserConfigOverrides): if any values in here change, delete the override
            values (dict): dict from string to string
        """
        pass  # silently ignore unknown config values

    def config_html(self, requirement, environ, local_state_file, status):
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

        Args:
            requirement (Requirement): the requirement we're providing
            environ (dict): current environment variables
            local_state_file (LocalStateFile): file to save to
            status (RequirementStatus): last-computed status

        Returns:
            An HTML string or None if there's nothing to configure.

        """
        return None

    def analyze(self, requirement, environ, local_state_file, overrides):
        """Analyze whether and how we'll be able to provide the requirement.

        This is used to show the situation in the UI, and also to
        consolidate all IO-type work in one place (inside
        Requirement.check_status()).

        Returns:
          A ``ProviderAnalysis`` instance.
        """
        config = self.read_config(requirement, environ, local_state_file, overrides)
        missing_to_configure = self.missing_env_vars_to_configure(requirement, environ, local_state_file)
        missing_to_provide = self.missing_env_vars_to_provide(requirement, environ, local_state_file)
        return ProviderAnalysis(config=config,
                                missing_env_vars_to_configure=missing_to_configure,
                                missing_env_vars_to_provide=missing_to_provide)

    @abstractmethod
    def provide(self, requirement, context):
        """Execute the provider, fulfilling the requirement.

        The implementation should read and modify the passed-in
        ``environ`` rather than accessing the OS environment
        directly.

        Args:
            requirement (Requirement): requirement we want to meet
            context (ProvideContext): context containing project state

        Returns:
            a ``ProvideResult`` instance

        """
        pass  # pragma: no cover

    @abstractmethod
    def unprovide(self, requirement, environ, local_state_file, requirement_status=None):
        """Undo the provide, cleaning up any files or processes we created.

        The requirement may still be met after this, if our providing wasn't
        really needed.

        Args:
            requirement (Requirement): requirement we want to de-provide
            environ (dict): current env vars, often from a previous prepare
            local_state_file (LocalStateFile): the local state
            requirement_status (RequirementStatus or None): requirement status if available

        Returns:
            a `Status` instance describing the (non)success of the unprovision
        """
        pass  # pragma: no cover


class EnvVarProvider(Provider):
    """Meets a requirement for an env var by letting people set it manually."""

    def _local_state_override(self, requirement, local_state_file):
        return local_state_file.get_value(["variables", requirement.env_var], default=None)

    def _disabled_local_state_override(self, requirement, local_state_file):
        return local_state_file.get_value(["disabled_variables", requirement.env_var], default=None)

    def _key_from_value(cls, value):
        if isinstance(value, dict) and 'key' in value:
            return value['key']
        else:
            return None

    def _possibly_decrypted_value(self, requirement, context, value, errors, logs):
        assert value is not None  # if it's None caller couldn't detect errors
        key = self._key_from_value(value)
        if key is not None:
            assert 'encrypted' in value  # we were supposed to validate this on project load
            if key not in context.environ:
                errors.append("Master password %s is not set so can't get value of %s." % (key, requirement.env_var))
                return None
            value = decrypt_string(value['encrypted'], context.environ[key])
        assert isinstance(value, basestring)  # should have validated this on project load
        return value

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

    def read_config(self, requirement, environ, local_state_file, overrides):
        """Override superclass to read env var value."""
        config = dict()
        value = self._local_state_override(requirement, local_state_file)
        disabled_value = self._disabled_local_state_override(requirement, local_state_file)
        was_disabled = value is None and disabled_value is not None
        if was_disabled:
            value = disabled_value
        key = self._key_from_value(value)

        if value is not None:
            if key is not None:
                # TODO: we need to deal with missing 'encrypted'
                # or with a bad password in some way
                encrypted = value['encrypted']
                value = decrypt_string(encrypted, environ[key])
            config['value'] = value

        if value is not None and not was_disabled:
            source = 'variables'
        elif requirement.env_var in environ:
            source = 'environ'
        elif 'default' in requirement.options:
            source = 'default'
        else:
            source = 'unset'
        config['source'] = source
        return config

    def set_config_values_as_strings(self, requirement, environ, local_state_file, overrides, values):
        """Override superclass to set env var value."""
        override_path = ["variables", requirement.env_var]
        disabled_path = ["disabled_variables", requirement.env_var]

        # we set override_path only if the source is variables,
        # otherwise the value goes in disabled_variables. If we
        # don't have a source that means the only option we
        # presented was to set the local override, so default to
        # 'variables'
        overriding = (values.get('source', 'variables') == 'variables')

        # If there's an existing override value and the source is not 'variables',
        # we need to be sure to move the existing to disabled_variables.
        # Also, we save values['value'] from the web form in local_state_file,
        # even if we aren't using it as the source right now.

        local_override_value = self._local_state_override(requirement, local_state_file)
        if local_override_value is None:
            local_override_value = self._disabled_local_state_override(requirement, local_state_file)

        value_string = values.get('value', local_override_value)

        if value_string is not None:
            if value_string == '':
                # the reason empty string unsets is that otherwise there's no easy
                # way to unset from a web form
                local_state_file.unset_value(override_path)
                local_state_file.unset_value(disabled_path)
            else:
                key = self._key_from_value(local_override_value)
                if key is None and requirement.encrypted:
                    key = 'ANACONDA_MASTER_PASSWORD'

                if key is not None:
                    value = dict(key=key, encrypted=encrypt_string(value_string, environ[key]))
                else:
                    value = value_string

                if overriding:
                    local_state_file.set_value(override_path, value)
                    local_state_file.unset_value(disabled_path)
                else:
                    local_state_file.set_value(disabled_path, value)
                    local_state_file.unset_value(override_path)

    def _extra_source_options_html(self, requirement, environ, local_state_file, status):
        """Override this in a subtype to add choices to the config HTML.

        Choices should be radio inputs with name="source"
        """
        return ""

    def config_html(self, requirement, environ, local_state_file, status):
        """Override superclass to provide our config html."""
        if status.requirement.encrypted:
            input_type = 'password'
        else:
            input_type = 'text'

        extra_html = self._extra_source_options_html(requirement, environ, local_state_file, status)

        choices_html = extra_html

        if requirement.env_var in environ:
            choices_html = choices_html + """
            <div>
              <label><input type="radio" name="source" value="environ"/>Keep value '{from_environ}'</label>
            </div>
            <div>
              <label><input type="radio" name="source" value="variables"/>Use this value instead:
                     <input type="{input_type}" name="value"/></label>
            </div>
            """.format(from_environ=environ[requirement.env_var],
                       input_type=input_type)
        else:
            if 'default' in requirement.options:
                choices_html = choices_html + """
                <div>
                  <label><input type="radio" name="source" value="default"/>Keep default '{from_default}'</label>
                </div>
                <div>
                  <label><input type="radio" name="source" value="variables"/>Use this value instead:
                         <input type="{input_type}" name="value"/></label>
                </div>
                """.format(input_type=input_type,
                           from_default=requirement.options['default'])
            else:
                choices_html = choices_html + """
                <div>
                  <label><input type="radio" name="source" value="variables"/>Use this value:
                         <input type="{input_type}" name="value"/></label>
                </div>
                """.format(input_type=input_type)

        # print(("%s: choices_html=\n" % self.__class__.__name__) + choices_html)

        return """
<form>
  %s
</form>
""" % (choices_html)

    def provide(self, requirement, context):
        """Override superclass to use configured env var (or already-set env var)."""
        errors = []
        logs = []

        # We prefer the values in this order:
        #  - value set in project-local state overrides everything
        #    (otherwise the UI for configuring the value would end
        #    up ignored)
        #  - then anything already set in the environment wins, so you
        #    can override on the command line like `FOO=bar myapp`
        #  - then the project.yml default value
        local_state_override = self._local_state_override(requirement, context.local_state_file)
        if local_state_override is not None:
            # project-local.yml
            #
            # variables:
            #   REDIS_URL: "redis://example.com:1234"
            local_state_override = self._possibly_decrypted_value(requirement, context, local_state_override, errors,
                                                                  logs)
            if local_state_override is not None:
                context.environ[requirement.env_var] = local_state_override
        elif requirement.env_var in context.environ:
            # nothing to do here
            pass
        elif 'default' in requirement.options:
            # project.yml
            #
            # variables:
            #   REDIS_URL:
            #     default: "redis://example.com:1234"
            value = requirement.options['default']
            if value is not None:
                value = self._possibly_decrypted_value(requirement, context, value, errors, logs)
            if value is not None:
                context.environ[requirement.env_var] = value
        else:
            pass

        return ProvideResult.empty().copy_with_additions(errors, logs)

    def unprovide(self, requirement, environ, local_state_file, requirement_status=None):
        """Override superclass to return success always."""
        return SimpleStatus(success=True, description=("Nothing to clean up for %s." % requirement.env_var))
