# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Abstract high-level interface to Conda."""
from __future__ import absolute_import

from abc import ABCMeta, abstractmethod
from copy import deepcopy
import difflib

from anaconda_project.yaml_file import (_CommentedMap, _CommentedSeq, _block_style_all_nodes)
from anaconda_project.internal.metaclass import with_metaclass
from anaconda_project.internal import conda_api
from anaconda_project.internal import pip_api

_conda_manager_classes = []


def _combine_keeping_last_duplicate(items1, items2, key_func=None):
    def default_key(item):
        return item

    if key_func is None:
        key_func = default_key
    items2_keys = set([key_func(item) for item in items2])
    combined = list([item for item in items1 if key_func(item) not in items2_keys])
    combined = combined + list(items2)
    return tuple(combined)


def _conda_combine_key(spec):
    parsed = conda_api.parse_spec(spec)
    if parsed is None:
        # this is broken but we complain about it in project.py, carry on here
        return spec
    else:
        return parsed.name


def _pip_combine_key(spec):
    parsed = pip_api.parse_spec(spec)
    if parsed is None:
        # this is broken but we complain about it in project.py, carry on here
        return spec
    else:
        return parsed.name


def _combine_conda_package_lists(first, second):
    return _combine_keeping_last_duplicate(first, second, key_func=_conda_combine_key)


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


def new_conda_manager(frontend=None):
    """Create a new concrete ``CondaManager``."""
    global _conda_manager_classes
    if len(_conda_manager_classes) == 0:
        from anaconda_project.internal.default_conda_manager import DefaultCondaManager
        klass = DefaultCondaManager
    else:
        klass = _conda_manager_classes[-1]
    return klass(frontend=frontend)


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
    def resolve_dependencies(self, package_specs, channels, platforms):
        """Compute the full transitive graph to install to satisfy package_specs.

        Raised exceptions that are user-interesting conda problems
        should be subtypes of ``CondaManagerError``.

        The passed-in package specs can be any constraints we want
        to "hold constant" while computing the other deps.

        The returned value is a ``CondaLockSet``.

        Args:
            package_specs (list of str): list of specs to hold constant
            channels (list of str): list of channels to resolve against
            platforms (list of str): list of platforms to resolve for

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
    def remove_packages(self, prefix, packages, pip):
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
           pip (bool): remove packages using pip

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
                 broken=False,
                 unfixable=False):
        """Construct a ``CondaEnvironmentDeviations``.

        Args:
          summary (str): the most immediate reason the environment deviates
          missing_packages (iterable of str): packages that aren't in the env
          wrong_version_packages (iterable of str): packages that are the wrong version
          broken (bool): True if it's broken for some other reason besides wrong packages
          unfixable (bool): True if fix_environment_deviations won't be able to solve it
        """
        self._summary = summary
        self._broken = broken
        self._unfixable = unfixable
        self._missing_packages = tuple(missing_packages)
        self._wrong_version_packages = tuple(wrong_version_packages)
        self._missing_pip_packages = tuple(missing_pip_packages)
        self._wrong_version_pip_packages = tuple(wrong_version_pip_packages)

        # not allowed to say unfixable=True unless you also give a broken reason
        assert (self.unfixable and not self.ok) or not self.unfixable

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
    def unfixable(self):
        """True if fix_environment_deviations can't resolve this."""
        return self._unfixable

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


def _pretty_diff(old_list, new_list, indent):
    diff = list(difflib.ndiff(old_list, new_list))

    # the diff has - lines, + lines, and ? lines
    # the ? lines have the ^ pointing to changed character,
    # which is just noise for these short version strings.
    # the diff also has lines with just whitespace at the
    # front, which are context.

    # remove context lines
    diff = filter(lambda x: x[0] != ' ', diff)
    # remove ? lines
    diff = filter(lambda x: x[0] != '?', diff)

    def indent_more(s):
        if s.startswith("+ "):
            return "+ " + indent + s[2:]
        elif s.startswith("- "):
            return "- " + indent + s[2:]
        else:
            return s  # pragma: no cover # should not be any other kind of lines

    diff = map(indent_more, diff)

    return list(diff)


class CondaLockSet(object):
    """Represents a locked set of package versions."""
    def __init__(self, package_specs_by_platform, platforms, enabled=True, env_spec_hash=None, missing=False):
        """Construct a ``CondaLockSet``.

        The passed-in dict should be like:

        {
           "all" : [ "bokeh=0.12.4=1" ],
           "linux-64" : [ "libffi=1.2=0" ]
        }

        Args:
          packages_by_platform (dict): dict from platform to spec list
          platforms (list of str): platform list
        """
        assert package_specs_by_platform is not None
        assert platforms is not None
        # we deepcopy this to avoid sharing issues
        self._package_specs_by_platform = deepcopy(package_specs_by_platform)
        self._platforms = tuple(conda_api.sort_platform_list(platforms))
        self._enabled = enabled
        self._env_spec_hash = env_spec_hash
        self._missing = missing

    @property
    def platforms(self):
        """Platform list the lock set was resolved for."""
        return self._platforms

    @property
    def enabled(self):
        """Whether locking is enabled for this environment."""
        return self._enabled

    @property
    def disabled(self):
        """Whether locking is disabled for this environment.

        (yes, this is just "not enabled" but this can be more readable sometimes)
        """
        return not self._enabled

    @property
    def missing(self):
        """Whether a lock set existed in the lock file.

        This says whether the lock set was loaded from anaconda-project-lock.yml
        or was just a default we made up on the fly.
        """
        return self._missing

    @property
    def env_spec_hash(self):
        """Hash of the env spec we created this lock set for."""
        return self._env_spec_hash

    @env_spec_hash.setter
    def env_spec_hash(self, value):
        # can only be set once
        assert self._env_spec_hash is None
        self._env_spec_hash = value

    def equivalent_to(self, other):
        """Determine if this lock set the same as another one."""
        # do NOT consider env_spec_hash in here, because we
        # use this to test whether the lock set for an old env
        # spec is the same as the one for a new env spec.
        return self._package_specs_by_platform == other._package_specs_by_platform and \
            self._platforms == other._platforms and \
            self._enabled is other._enabled

    def diff_from(self, old):
        """A string showing the comparison between this lock set and another one.

        "old" can be None to mean diff vs. nothing.
        """
        keys = list(self._package_specs_by_platform.keys())
        if old is not None:
            keys = keys + list(old._package_specs_by_platform.keys())
            # de-dup
            keys = list(set(keys))

        # sort nicely
        keys = conda_api.sort_platform_list(keys)

        packages_diff = []
        for key in keys:
            if old is None:
                old_list = []
            else:
                old_list = old._package_specs_by_platform.get(key, [])

            new_list = self._package_specs_by_platform.get(key, [])

            diff = _pretty_diff(old_list, new_list, indent="    ")

            if diff:
                if old is None or key not in old._package_specs_by_platform:
                    packages_diff.append("+   %s:" % key)
                elif key not in self._package_specs_by_platform:
                    packages_diff.append("-   %s:" % key)
                else:
                    packages_diff.append("    %s:" % key)
                packages_diff.extend(map(lambda x: x, diff))

        if packages_diff:
            packages_diff = ['  packages:'] + packages_diff

        if old is None:
            old_platforms = []
        else:
            old_platforms = old.platforms
        platforms_diff = _pretty_diff(old_platforms, self.platforms, indent="  ")
        if platforms_diff:
            platforms_diff = ['  platforms:'] + platforms_diff

        return "\n".join(platforms_diff + packages_diff)

    def package_specs_for_platform(self, platform):
        """Sequence of package spec strings for the requested platform."""
        assert platform in self.platforms
        assert self.enabled

        # we merge "all", "unix", "linux", then "linux-64" for example
        shared = self._package_specs_by_platform.get("all", [])

        platform_name = conda_api.parse_platform(platform)[0]

        if platform_name in conda_api.unix_platform_names:
            shared_unix = self._package_specs_by_platform.get("unix", [])
            shared = _combine_conda_package_lists(shared, shared_unix)

        shared_across_bits = self._package_specs_by_platform.get(platform_name, [])
        shared = _combine_conda_package_lists(shared, shared_across_bits)

        per_platform = self._package_specs_by_platform.get(platform, [])
        return _combine_conda_package_lists(shared, per_platform)

    @property
    def pip_package_specs(self):
        """Sequence of pip packages."""
        return self._package_specs_by_platform.get('pip', [])

    @property
    def package_specs_for_current_platform(self):
        """Sequence of package spec strings for the current platform."""
        assert self.supports_current_platform
        return self.package_specs_for_platform(platform=conda_api.current_platform())

    @property
    def supports_current_platform(self):
        """Whether we have locked deps for the current platform."""
        return self.enabled and conda_api.current_platform() in self.platforms

    def to_json(self):
        """JSON/YAML version of the lock set."""
        yaml_dict = _CommentedMap()

        yaml_dict['locked'] = self.enabled

        if self.env_spec_hash is not None:
            yaml_dict['env_spec_hash'] = self.env_spec_hash

        platforms_list = _CommentedSeq()
        for platform in self.platforms:
            platforms_list.append(platform)
        yaml_dict['platforms'] = platforms_list

        packages_dict = _CommentedMap()
        for platform in conda_api.sort_platform_list(self._package_specs_by_platform.keys()):
            packages = _CommentedSeq()
            for package in self._package_specs_by_platform[platform]:
                packages.append(package)
            packages_dict[platform] = packages
        yaml_dict['packages'] = packages_dict

        _block_style_all_nodes(yaml_dict)
        return yaml_dict
