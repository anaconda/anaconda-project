# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Types related to project requirements."""
from __future__ import absolute_import

from abc import ABCMeta, abstractmethod
from copy import deepcopy

from anaconda_project.internal.metaclass import with_metaclass
from anaconda_project.internal.py2_compat import is_string
from anaconda_project.status import Status


class UserConfigOverrides(object):
    """Class containing user-forced configuration for the prepare process."""
    def __init__(self, inherited_env=None, env_spec_name=None):
        """Construct a set of user overrides for the prepare process."""
        self._inherited_env = inherited_env
        self._env_spec_name = env_spec_name

    @property
    def env_spec_name(self):
        """The user-specified name of the conda environment spec to use, or None if not specified."""
        return self._env_spec_name

    @property
    def inherited_env(self):
        """The environment we started with before we ran the prepare process."""
        return self._inherited_env

    @env_spec_name.setter
    def env_spec_name(self, value):
        """Change the conda environment name override."""
        self._env_spec_name = value


class RequirementStatus(Status):
    """Class describing the status of a requirement.

    Values of this class are immutable; to get updated status, you
    would call ``recheck()`` to get a new status.

    """
    def __init__(self, requirement, has_been_provided, status_description, provider, analysis, latest_provide_result,
                 env_spec_name):
        """Construct an abstract RequirementStatus."""
        self._requirement = requirement
        self._has_been_provided = has_been_provided
        self._status_description = status_description
        self._provider = provider
        self._analysis = analysis
        self._latest_provide_result = latest_provide_result
        self._env_spec_name = env_spec_name

    def __repr__(self):
        """Repr of the status."""
        return "RequirementStatus(%r,%r,%r)" % (self.has_been_provided, self.status_description, self.requirement)

    def __bool__(self):
        """True if the requirement is met."""
        return self.has_been_provided

    def __nonzero__(self):
        """True if the requirement is met."""
        return self.__bool__()  # pragma: no cover (py2 only)

    @property
    def requirement(self):
        """Get the requirement we are the status of."""
        return self._requirement

    @property
    def has_been_provided(self):
        """Get True if the requirement has been met."""
        return self._has_been_provided

    @property
    def status_description(self):
        """Get a description of how the requirement has been met (or why it hasn't been)."""
        return self._status_description

    @property
    def provider(self):
        """Get the provider for this requirement."""
        return self._provider

    @property
    def analysis(self):
        """Get the provider's analysis of the status."""
        return self._analysis

    @property
    def latest_provide_result(self):
        """Get the latest ``ProvideResult`` or None if we haven't provided yet."""
        return self._latest_provide_result

    @property
    def errors(self):
        """Get error logs relevant to the status, from either checking status or attempting to provide it."""
        if self.latest_provide_result is None:
            return []
        else:
            return self.latest_provide_result.errors

    @property
    def env_spec_name(self):
        """Get the env spec name used to meet the requirement, None if not a ``CondaEnvRequirement``."""
        return self._env_spec_name

    def recheck(self, environ, local_state_file, default_env_spec_name, overrides=None, latest_provide_result=None):
        """Get a new ``RequirementStatus`` reflecting the current state.

        This calls ``Requirement.check_status()`` which can do network and filesystem IO,
        so be cautious about where you call it.
        """
        if latest_provide_result is None:
            latest_provide_result = self._latest_provide_result
        return self.requirement.check_status(environ, local_state_file, default_env_spec_name, overrides,
                                             latest_provide_result)


class Requirement(with_metaclass(ABCMeta)):
    """Describes a requirement of the project (from the project config).

    Note that this is not specifically a package requirement;
    this class is more general, it can be a requirement for any
    condition at all (that a service is running, that a file
    exists, or even that a package is intalled - anything you can
    think of).

    """
    def __init__(self, registry, options):
        """Construct a Requirement.

        Args:
            registry (RequirementsRegistry): the plugin registry we came from
            options (dict): dict of requirement options from the project config
        """
        self.registry = registry

        if options is None:
            self.options = dict()
        else:
            self.options = deepcopy(options)
            # always convert the default to a string (it's allowed to be a number
            # in the config file, but env vars have to be strings), unless
            # it's a dict because we use a dict for encrypted defaults
            if 'default' in self.options and not (is_string(self.options['default'])
                                                  or isinstance(self.options['default'], dict)):
                self.options['default'] = str(self.options['default'])

    @property
    @abstractmethod
    def title(self):
        """Human-readable short name of the requirement."""
        pass  # pragma: no cover

    def _description(self, default):
        """Use this in subclasses to implement the description property."""
        if 'description' in self.options:
            return self.options['description']
        else:
            return default

    @property
    @abstractmethod
    def description(self):
        """Human-readable about-one-sentence hint or tooltip for the requirement."""
        pass  # pragma: no cover

    @property
    def ignore_patterns(self):
        """Set of ignore patterns for files this requirement's provider might autogenerate."""
        return set()

    def _create_status(self, environ, local_state_file, default_env_spec_name, overrides, latest_provide_result,
                       has_been_provided, status_description, provider_class_name):
        provider = self.registry.find_provider_by_class_name(provider_class_name)
        analysis = provider.analyze(self, environ, local_state_file, default_env_spec_name, overrides)
        env_spec_name = analysis.config.get('env_name', None)
        return RequirementStatus(self,
                                 has_been_provided=has_been_provided,
                                 status_description=status_description,
                                 provider=provider,
                                 analysis=analysis,
                                 latest_provide_result=latest_provide_result,
                                 env_spec_name=env_spec_name)

    def _create_status_from_analysis(self, environ, local_state_file, default_env_spec_name, overrides,
                                     latest_provide_result, provider_class_name, status_getter):
        provider = self.registry.find_provider_by_class_name(provider_class_name)
        analysis = provider.analyze(self, environ, local_state_file, default_env_spec_name, overrides)
        (has_been_provided, status_description) = status_getter(environ, local_state_file, analysis)
        env_spec_name = analysis.config.get('env_name', None)

        return RequirementStatus(self,
                                 has_been_provided=has_been_provided,
                                 status_description=status_description,
                                 provider=provider,
                                 analysis=analysis,
                                 latest_provide_result=latest_provide_result,
                                 env_spec_name=env_spec_name)

    @abstractmethod
    def check_status(self, environ, local_state_file, default_env_spec_name, overrides, latest_provide_result=None):
        """Check on the requirement and return a ``RequirementStatus`` with the current status.

        This may attempt to talk to servers, check that files
        exist on disk, and other work of that nature to verify the
        requirement's status, so be careful about when and how
        often this gets called.

        Args:
            environ (dict): use this rather than the system environment directly
            local_state_file (LocalStateFile): project local state
            default_env_spec_name (str): fallback env spec name
            overrides (UserConfigOverrides): user-supplied forced choices
            latest_provide_result (ProvideResult): most recent result of ``provide()`` or None

        Returns:
            a ``RequirementStatus``

        """
        pass  # pragma: no cover (abstract method)


# suffixes that change the default for the "encrypted" option
_secret_suffixes = ('_PASSWORD', '_SECRET_KEY', '_SECRET')


class EnvVarRequirement(Requirement):
    """A requirement that a certain environment variable be set."""
    @classmethod
    def _parse_default(self, options, env_var, problems):
        assert (isinstance(options, dict))

        raw_default = options.get('default', None)

        if raw_default is None:
            good_default = True
        elif isinstance(raw_default, bool):
            # we have to check bool since it's considered an int apparently
            good_default = False
        elif is_string(raw_default) or isinstance(raw_default, (int, float)):
            good_default = True
        else:
            good_default = False

        if 'default' in options and raw_default is None:
            # convert null to be the same as simply missing
            del options['default']

        if good_default:
            return True
        else:
            problems.append(
                "default value for variable {env_var} must be null, a string, or a number, not {value}.".format(
                    env_var=env_var, value=raw_default))
            return False

    def __init__(self, registry, env_var, options=None):
        """Construct an EnvVarRequirement for the given ``env_var`` with the given options."""
        super(EnvVarRequirement, self).__init__(registry, options)
        assert env_var is not None
        self.env_var = env_var

    def __repr__(self):
        """Custom repr of EnvVarRequirement."""
        return "%s(env_var='%s')" % (self.__class__.__name__, self.env_var)

    @property
    def title(self):
        """Override superclass title."""
        return self.env_var

    @property
    def description(self):
        """Override superclass description."""
        return self._description("%s environment variable must be set." % (self.env_var))

    @property
    def encrypted(self):
        """Get whether this is a password-type value we should encrypt when possible."""
        if 'encrypted' in self.options:
            return self.options['encrypted']
        else:
            return any(self.env_var.endswith(suffix) for suffix in _secret_suffixes)

    @property
    def default_as_string(self):
        """Get the default, forced to string or None."""
        value = self.options.get('default', None)
        if value is None:
            return None
        else:
            # see _parse_default above, it can be a string already,
            # or an integer
            return str(value)

    def _get_value_of_env_var(self, environ):
        """A "protected" method for subtypes to use."""
        value = environ.get(self.env_var, None)
        if value == "":  # do we really want this, maybe empty string is a valid value sometimes?
            value = None
        return value

    def _unset_message(self):
        """A "protected" method for subtypes to use."""
        return "Environment variable {env_var} is not set.".format(env_var=self.env_var)

    def _set_message(self, environ):
        """A "protected" method for subtypes to use."""
        if self.encrypted:
            # don't include the value if it's an encrypted variable.
            return "Environment variable {env_var} is set.".format(env_var=self.env_var)
        else:
            return "Environment variable {env_var} set to '{value}'".format(env_var=self.env_var,
                                                                            value=self._get_value_of_env_var(environ))

    def check_status(self, environ, local_state_file, default_env_spec_name, overrides, latest_provide_result=None):
        """Override superclass to get our status."""
        value = self._get_value_of_env_var(environ)

        has_been_provided = value is not None
        if has_been_provided:
            status_description = self._set_message(environ)
        else:
            status_description = self._unset_message()

        return self._create_status(environ,
                                   local_state_file,
                                   default_env_spec_name=default_env_spec_name,
                                   overrides=overrides,
                                   has_been_provided=has_been_provided,
                                   status_description=status_description,
                                   provider_class_name='EnvVarProvider',
                                   latest_provide_result=latest_provide_result)
