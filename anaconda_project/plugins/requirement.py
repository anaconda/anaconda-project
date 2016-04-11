# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Types related to project requirements."""
from __future__ import absolute_import

from abc import ABCMeta, abstractmethod
from copy import deepcopy

from anaconda_project.internal.metaclass import with_metaclass


class RequirementStatus(with_metaclass(ABCMeta)):
    """Class describing the status of a requirement.

    Values of this class are immutable; to get updated status, you
    would call ``recheck()`` to get a new status.

    """

    def __init__(self, requirement, has_been_provided, status_description, provider, analysis):
        """Construct an abstract RequirementStatus."""
        self._requirement = requirement
        self._has_been_provided = has_been_provided
        self._status_description = status_description
        self._provider = provider
        self._analysis = analysis

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

    def recheck(self, environ, local_state_file):
        """Get a new ``RequirementStatus`` reflecting the current state.

        This calls ``Requirement.check_status()`` which can do network and filesystem IO,
        so be cautious about where you call it.
        """
        return self.requirement.check_status(environ, local_state_file)


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
            registry (PluginRegistry): the plugin registry we came from
            options (dict): dict of requirement options from the project config
        """
        self.registry = registry

        if options is None:
            self.options = dict()
        else:
            self.options = deepcopy(options)

    @property
    @abstractmethod
    def title(self):
        """Human-readable title of the requirement."""
        pass  # pragma: no cover

    def _create_status(self, environ, local_state_file, has_been_provided, status_description, provider_class_name):
        provider = self.registry.find_provider_by_class_name(provider_class_name)
        analysis = provider.analyze(self, environ, local_state_file)
        return RequirementStatus(self,
                                 has_been_provided=has_been_provided,
                                 status_description=status_description,
                                 provider=provider,
                                 analysis=analysis)

    def _create_status_from_analysis(self, environ, local_state_file, provider_class_name, status_getter):
        provider = self.registry.find_provider_by_class_name(provider_class_name)
        analysis = provider.analyze(self, environ, local_state_file)
        (has_been_provided, status_description) = status_getter(environ, local_state_file, analysis)
        return RequirementStatus(self,
                                 has_been_provided=has_been_provided,
                                 status_description=status_description,
                                 provider=provider,
                                 analysis=analysis)

    @abstractmethod
    def check_status(self, environ, local_state_file):
        """Check on the requirement and return a ``RequirementStatus`` with the current status.

        This may attempt to talk to servers, check that files
        exist on disk, and other work of that nature to verify the
        requirement's status, so be careful about when and how
        often this gets called.

        Args:
            environ (dict): use this rather than the system environment directly
            local_state_file (LocalStateFile): project local state

        Returns:
            a ``RequirementStatus``

        """
        pass  # pragma: no cover (abstract method)

# suffixes that change the default for the "encrypted" option
_secret_suffixes = ('_PASSWORD', '_ENCRYPTED', '_SECRET_KEY', '_SECRET')


class EnvVarRequirement(Requirement):
    """A requirement that a certain environment variable be set."""

    def __init__(self, registry, env_var, options=None):
        """Construct an EnvVarRequirement for the given ``env_var`` with the given options."""
        super(EnvVarRequirement, self).__init__(registry, options)
        self.env_var = env_var

    def __repr__(self):
        """Custom repr of EnvVarRequirement."""
        return "%s(env_var='%s')" % (self.__class__.__name__, self.env_var)

    @property
    def title(self):
        """Override superclass title."""
        return "%s environment variable must be set" % (self.env_var)

    @property
    def encrypted(self):
        """Get whether this is a password-type value we should encrypt when possible."""
        if 'encrypted' in self.options:
            return self.options['encrypted']
        else:
            return any(self.env_var.endswith(suffix) for suffix in _secret_suffixes)

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

    def check_status(self, environ, local_state_file):
        """Override superclass to get our status."""
        value = self._get_value_of_env_var(environ)

        has_been_provided = value is not None
        if has_been_provided:
            status_description = self._set_message(environ)
        else:
            status_description = self._unset_message()

        return self._create_status(environ,
                                   local_state_file,
                                   has_been_provided=has_been_provided,
                                   status_description=status_description,
                                   provider_class_name='EnvVarProvider')
