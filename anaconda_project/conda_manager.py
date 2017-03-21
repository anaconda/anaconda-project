# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Abstract high-level interface to Conda."""
from __future__ import absolute_import

from abc import ABCMeta, abstractmethod
from copy import deepcopy

from anaconda_project.yaml_file import (_CommentedMap, _CommentedSeq, _block_style_all_nodes)
from anaconda_project.internal.metaclass import with_metaclass
from anaconda_project.internal import conda_api
from anaconda_project.env_spec import _combine_conda_package_lists

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
    def resolve_dependencies(self, package_specs):
        """Compute the full transitive graph to install to satisfy package_specs.

        Raised exceptions that are user-interesting conda problems
        should be subtypes of ``CondaManagerError``.

        The passed-in package specs can be any constraints we want
        to "hold constant" while computing the other deps.

        The returned value is a ``CondaLockSet``.

        Args:
            package_specs (list of str): list of specs to hold constant

        Returns:
            a ``CondaLockSet`` instance

        """
        pass  # pragma: no cover

    @abstractmethod
    def find_environment_deviations(self, prefix, spec):
        """Compute a ``CondaEnvironmentDeviations`` describing deviations of the env at prefix from the spec.

        Raised exceptions that are user-interesting conda problems
        should be subtypes of ``CondaManagerError``.

        The prefix may not exist (which would be considered a
        deviation).

        Args:
            prefix (str): the environment prefix (absolute path)
            spec (EnvSpec): specification for the environment

        Returns:
            a ``CondaEnvironmentDeviations`` instance

        """
        pass  # pragma: no cover

    @abstractmethod
    def fix_environment_deviations(self, prefix, spec, deviations=None, create=True):
        """Fix deviations of the env in prefix from the spec.

        Raised exceptions that are user-interesting conda problems
        should be subtypes of ``CondaManagerError``.

        The prefix may not exist (this method should then try to create it).

        Args:
            prefix (str): the environment prefix (absolute path)
            spec (EnvSpec): specification for the environment
            deviations (CondaEnvironmentDeviations): optional previous result from find_environment_deviations()
            create (bool): True if we should create if completely nonexistent

        Returns:
            None
        """
        pass  # pragma: no cover

    @abstractmethod
    def remove_packages(self, prefix, packages):
        """Remove the given package name from the environment in prefix.

        This method ideally would not exist. The ideal approach is
        that in find_enviroment_deviations, the generated
        deviation could include "pruned" or "unnecessary" packages
        that are in the prefix but aren't needed for the
        spec. fix_environment_deviations would then remove any
        extra packages. In effect we'd always force the
        environment to be the fresh env we would install from
        scratch, given the spec.

        Args:
           prefix (str): environment path
           package (list of str): package names

        Returns:
           None

        """
        pass  # pragma: no cover


class CondaEnvironmentDeviations(object):
    """Represents differences between actual and desired environment state."""

    def __init__(self,
                 summary,
                 missing_packages,
                 wrong_version_packages,
                 missing_pip_packages,
                 wrong_version_pip_packages,
                 broken=False):
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
        self._missing_pip_packages = tuple(missing_pip_packages)
        self._wrong_version_pip_packages = tuple(wrong_version_pip_packages)

    @property
    def ok(self):
        """True if no deviations were found, environment exists and looks good.

        If the deviations are "ok" then
        ``CondaManager.fix_environment_deviations()`` would be
        expected to have no work to do and doesn't need to be
        called.

        """
        return len(self.missing_packages) == 0 and \
            len(self.wrong_version_packages) == 0 and \
            len(self.missing_pip_packages) == 0 and \
            len(self.wrong_version_pip_packages) == 0 and \
            not self._broken

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

    @property
    def missing_pip_packages(self):
        """Iterable collection of missing pip package names."""
        return self._missing_pip_packages

    @property
    def wrong_version_pip_packages(self):
        """Iterable collection of pip package names an unacceptable version installed."""
        return self._wrong_version_pip_packages


class CondaLockSet(object):
    """Represents a locked set of package versions."""

    def __init__(self, package_specs_by_platform):
        """Construct a ``CondaLockSet``.

        The passed-in dict should be like:

        {
           "all" : [ "bokeh=0.12.4=1" ],
           "linux-64" : [ "libffi=1.2=0" ]
        }

        Args:
          packages_by_platform (dict): dict from platform to spec list
        """
        # we deepcopy this to avoid sharing issues
        self._package_specs_by_platform = deepcopy(package_specs_by_platform)

    def package_specs_for_platform(self, platform):
        """Sequence of package spec strings for the requested platform."""
        # we merge "all", "linux", then "linux-64" for example
        shared = self._package_specs_by_platform.get("all", [])
        platform_name = conda_api.parse_platform(platform)[0]
        shared_across_bits = self._package_specs_by_platform.get(platform_name, [])
        per_platform = self._package_specs_by_platform.get(platform, [])
        all_shared = _combine_conda_package_lists(shared, shared_across_bits)
        return _combine_conda_package_lists(all_shared, per_platform)

    @property
    def package_specs_for_current_platform(self):
        """Sequence of package spec strings for the current platform."""
        return self.package_specs_for_platform(platform=conda_api.current_platform())

    def to_json(self):
        """JSON/YAML version of the lock set."""
        yaml_dict = _CommentedMap()
        for platform in self._package_specs_by_platform.keys():
            packages = _CommentedSeq()
            for package in self._package_specs_by_platform[platform]:
                packages.append(package)
            yaml_dict[platform] = packages
        _block_style_all_nodes(yaml_dict)
        return yaml_dict
