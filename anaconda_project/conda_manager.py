# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Abstract high-level interface to Conda."""
from __future__ import absolute_import

from abc import ABCMeta, abstractmethod

from anaconda_project.internal.metaclass import with_metaclass

_conda_manager_classes = []


def push_conda_manager_class(klass):
    """Push the concrete subtype of ``CondaManager`` to be used."""
    global _conda_manager_classes
    assert issubclass(klass, CondaManager)
    _conda_manager_classes.append(klass)


def pop_conda_manager_class():
    """Remove the most recently-pushed concrete subtype of ``CondaManager``."""
    global _conda_manager_classes
    assert len(_conda_manager_classes) > 0
    _conda_manager_classes.pop()


def new_conda_manager():
    """Create a new concrete ``CondaManager``."""
    global _conda_manager_classes
    if len(_conda_manager_classes) == 0:
        from anaconda_project.internal.default_conda_manager import DefaultCondaManager
        klass = DefaultCondaManager
    else:
        klass = _conda_manager_classes[-1]
    return klass()


class CondaManagerError(Exception):
    """General Conda error."""

    pass


class CondaManager(with_metaclass(ABCMeta)):
    """Methods for interacting with Conda.

    This is meant to be a stateless class. Multiple may be created
    and they may be used from multiple threads. If instances are
    implemented using any global state under the hood, that global
    state should be protected by locks, and shared among
    ``CondaManager`` instances.

    """

    @abstractmethod
    def find_environment_deviations(self, prefix, spec):
        """Compute a ``CondaEnvironmentDeviations`` describing deviations of the env at prefix from the spec.

        Raised exceptions that are user-interesting conda problems
        should be subtypes of ``CondaManagerError``.

        The prefix may not exist (which would be considered a
        deviation).

        Args:
            prefix (str): the environment prefix (absolute path)
            spec (CondaEnvironment): specification for the environment

        Returns:
            a ``CondaEnvironmentDeviations`` instance

        """
        pass  # pragma: no cover

    @abstractmethod
    def fix_environment_deviations(self, prefix, spec, deviations=None):
        """Fix deviations of the env in prefix from the spec.

        Raised exceptions that are user-interesting conda problems
        should be subtypes of ``CondaManagerError``.

        The prefix may not exist (this method should then try to create it).

        Args:
            prefix (str): the environment prefix (absolute path)
            spec (CondaEnvironment): specification for the environment
            deviations (CondaEnvironmentDeviations): optional previous result from find_environment_deviations()

        Returns:
            None
        """
        pass  # pragma: no cover


class CondaEnvironmentDeviations(object):
    """Represents differences between actual and desired environment state."""

    def __init__(self, summary, missing_packages, wrong_version_packages, broken=False):
        """Construct a ``CondaEnvironmentDeviations``.

        Args:
          summary (str): the most immediate reason the environment deviates
          missing_packages (iterable of str): packages that aren't in the env
          wrong_version_packages (iterable of str): packages that are the wrong version
          broken (bool): True if it's broken for some other reason besides wrong packages
        """
        self._summary = summary
        self._broken = broken
        self._missing_packages = tuple(missing_packages)
        self._wrong_version_packages = tuple(wrong_version_packages)

    @property
    def ok(self):
        """True if no deviations were found, environment exists and looks good.

        If the deviations are "ok" then
        ``CondaManager.fix_environment_deviations()`` would be
        expected to have no work to do and doesn't need to be
        called.

        """
        return len(self.missing_packages) == 0 and len(self.wrong_version_packages) == 0 and not self._broken

    @property
    def summary(self):
        """Summary description of status."""
        return self._summary

    @property
    def missing_packages(self):
        """Iterable collection of missing package names."""
        return self._missing_packages

    @property
    def wrong_version_packages(self):
        """Iterable collection of package names an unacceptable version installed."""
        return self._wrong_version_packages
