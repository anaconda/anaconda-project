# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
import codecs
import os

from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.test.project_utils import assert_identical_except_blank_lines
from anaconda_project.project_lock_file import (ProjectLockFile, DEFAULT_PROJECT_LOCK_FILENAME,
                                                possible_project_lock_file_names)
from anaconda_project.conda_manager import CondaLockSet

expected_default_file = """# This is an Anaconda project lock file.
# The lock file locks down exact versions of all your dependencies.
#
# In most cases, this file is automatically maintained by the `anaconda-project` command or GUI tools.
# It's best to keep this file in revision control (such as git or svn).
# The file is in YAML format, please see http://www.yaml.org/start.html for more.
#

#
# Set to false to ignore locked versions.
#
locking_enabled: false

#
# A key goes in here for each env spec.
#
env_specs: {}
"""


def _get_locking_enabled(lock_file, env_spec_name):
    """Library-internal method."""
    enabled = lock_file.get_value(['env_specs', env_spec_name, 'locked'], None)
    if enabled is not None:
        return enabled

    enabled = lock_file.get_value(['locking_enabled'])
    if enabled is not None:
        return enabled

    return True


def _get_lock_set(lock_file, env_spec_name):
    """Library-internal method."""
    # TODO no validation here, we'll do that by moving this
    # into project.py soon
    enabled = _get_locking_enabled(lock_file, env_spec_name)
    packages = lock_file.get_value(['env_specs', env_spec_name, 'packages'], {})
    platforms = lock_file.get_value(['env_specs', env_spec_name, 'platforms'], [])
    env_spec_hash = lock_file.get_value(['env_specs', env_spec_name, 'env_spec_hash'], None)
    lock_set = CondaLockSet(packages, platforms, enabled=enabled)
    lock_set.env_spec_hash = env_spec_hash
    return lock_set


def test_create_missing_lock_file_only_when_not_default():
    def create_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_LOCK_FILENAME)
        assert not os.path.exists(filename)
        lock_file = ProjectLockFile.load_for_directory(dirname)
        assert lock_file is not None
        assert not os.path.exists(filename)

        assert _get_lock_set(lock_file, 'foo').disabled
        assert not _get_locking_enabled(lock_file, 'foo')

        lock_file.save()
        # should not have saved an unmodified (default) file)
        assert not os.path.exists(filename)

        # make a change, which should cause us to save
        lock_file.set_value(['something'], 42)

        lock_file.save()
        assert os.path.exists(filename)
        with codecs.open(filename, 'r', 'utf-8') as file:
            contents = file.read()
            expected = expected_default_file + "something: 42\n"
            assert_identical_except_blank_lines(expected, contents)

    with_directory_contents(dict(), create_file)


def _use_existing_lock_file(relative_name):
    def check_file(dirname):
        filename = os.path.join(dirname, relative_name)
        assert os.path.exists(filename)
        lock_file = ProjectLockFile.load_for_directory(dirname)
        assert lock_file.get_value(['env_specs', 'foo']) is not None
        assert lock_file.get_value(['locking_enabled']) is True

    with_directory_contents(
        {
            relative_name:
            """
locking_enabled: true
env_specs:
  foo:
    locked: true
    platforms: [linux-32,linux-64,osx-64,win-32,win-64]
    packages:
      all:
        - foo=1.0=1
  bar:
    locked: false
    platforms: [linux-32,linux-64,osx-64,win-32,win-64]
    packages:
      all:
        - bar=2.0=2
"""
        }, check_file)


def test_use_existing_lock_file_default_name():
    _use_existing_lock_file(DEFAULT_PROJECT_LOCK_FILENAME)


def test_use_existing_lock_file_all_names():
    for name in possible_project_lock_file_names:
        _use_existing_lock_file(name)


def _use_existing_lock_file_from_subdir(relative_name):
    def check_file(dirname):
        filename = os.path.join(dirname, relative_name)
        assert os.path.exists(filename)
        subdir = os.path.join(dirname, 'subdir')
        os.makedirs(subdir)
        lock_file = ProjectLockFile.load_for_directory(subdir)
        assert lock_file.get_value(['env_specs', 'foo']) is not None
        assert lock_file.get_value(['locking_enabled']) is True

    with_directory_contents(
        {
            relative_name:
            """
locking_enabled: true
env_specs:
  foo:
    locked: true
    platforms: [linux-32,linux-64,osx-64,win-32,win-64]
    packages:
      all:
        - foo=1.0=1
  bar:
    locked: false
    platforms: [linux-32,linux-64,osx-64,win-32,win-64]
    packages:
      all:
        - bar=2.0=2
"""
        }, check_file)


def test_use_existing_lock_file_default_name_from_subdir():
    _use_existing_lock_file_from_subdir(DEFAULT_PROJECT_LOCK_FILENAME)


def test_use_existing_lock_file_all_names_from_subdir():
    for name in possible_project_lock_file_names:
        _use_existing_lock_file_from_subdir(name)


def test_get_lock_set():
    def check_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_LOCK_FILENAME)
        assert os.path.exists(filename)
        lock_file = ProjectLockFile.load_for_directory(dirname)
        foo_lock_set = _get_lock_set(lock_file, 'foo')
        assert foo_lock_set.enabled
        assert ('foo=1.0=1', ) == foo_lock_set.package_specs_for_current_platform
        assert ['qbert==1.0.0'] == foo_lock_set.pip_package_specs
        bar_lock_set = _get_lock_set(lock_file, 'bar')
        assert bar_lock_set.disabled

    with_directory_contents(
        {
            DEFAULT_PROJECT_LOCK_FILENAME:
            """
locking_enabled: true
env_specs:
  foo:
    locked: true
    platforms: [linux-32,linux-64,osx-64,osx-arm64,win-32,win-64]
    packages:
      all:
        - foo=1.0=1
      pip:
        - qbert==1.0.0
  bar:
    locked: false
    platforms: [linux-32,linux-64,osx-64,osx-arm64,win-32,win-64]
    packages:
      all:
        - bar=2.0=2
      pip:
        - pbert==1.1.0
"""
        }, check_file)


def test_disable_single_spec_locking():
    def check_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_LOCK_FILENAME)
        assert os.path.exists(filename)
        lock_file = ProjectLockFile.load_for_directory(dirname)
        foo_lock_set = _get_lock_set(lock_file, 'foo')
        assert ('foo=1.0=1', ) == foo_lock_set.package_specs_for_current_platform

        lock_file._disable_locking('foo')

        foo_lock_set = _get_lock_set(lock_file, 'foo')
        assert foo_lock_set.disabled
        assert _get_locking_enabled(lock_file, 'foo') is False

    with_directory_contents(
        {
            DEFAULT_PROJECT_LOCK_FILENAME:
            """
locking_enabled: true
env_specs:
  foo:
    locked: true
    platforms: [linux-32,linux-64,osx-64,osx-arm64,win-32,win-64]
    packages:
      all:
        - foo=1.0=1
  bar:
    locked: false
    platforms: [linux-32,linux-64,osx-64,osx-arm64,win-32,win-64]
    packages:
      all:
        - bar=2.0=2
"""
        }, check_file)


def test_set_lock_set():
    def check_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_LOCK_FILENAME)
        assert os.path.exists(filename)
        lock_file = ProjectLockFile.load_for_directory(dirname)

        # we have the global enabled flag off; individual
        # env spec settings override that; foo has no setting.
        foo_lock_set = _get_lock_set(lock_file, 'foo')
        assert lock_file.get_value(['env_specs', 'foo', 'locked'], None) is None
        assert foo_lock_set.disabled
        bar_lock_set = _get_lock_set(lock_file, 'bar')
        assert bar_lock_set.disabled

        all_names = ['foo', 'bar']

        lock_set = CondaLockSet({'all': ['something=3.0=0']},
                                platforms=['linux-32', 'linux-64', 'osx-64', 'osx-arm64', 'win-32', 'win-64'])
        lock_set.env_spec_hash = "hash-hash-hash"

        lock_file._set_lock_set('bar', lock_set, all_names=all_names)

        # "foo" should have been DISABLED since we had to
        # enable the global flag in order to enable "bar"
        foo_lock_set = _get_lock_set(lock_file, 'foo')
        assert lock_file.get_value(['env_specs', 'foo', 'locked']) is False
        assert foo_lock_set.disabled
        assert foo_lock_set.env_spec_hash is None

        bar_lock_set = _get_lock_set(lock_file, 'bar')
        assert bar_lock_set.enabled
        assert ('something=3.0=0', ) == bar_lock_set.package_specs_for_current_platform
        assert "hash-hash-hash" == bar_lock_set.env_spec_hash

        # and now we should enable "foo" when we set it to something
        lock_file._set_lock_set('foo', lock_set, all_names=all_names)
        foo_lock_set = _get_lock_set(lock_file, 'foo')
        assert foo_lock_set.enabled
        assert ('something=3.0=0', ) == foo_lock_set.package_specs_for_current_platform

        # be sure we can save
        lock_file.save()

        reloaded = ProjectLockFile.load_for_directory(dirname)

        assert ('something=3.0=0', ) == _get_lock_set(reloaded, 'bar').package_specs_for_current_platform
        assert ('something=3.0=0', ) == _get_lock_set(reloaded, 'foo').package_specs_for_current_platform

        # Check _set_lock_set_hash
        lock_file._set_lock_set_hash('bar', 'hash2.0')
        lock_file.save()

        reloaded = ProjectLockFile.load_for_directory(dirname)
        bar_lock_set = _get_lock_set(reloaded, 'bar')
        assert bar_lock_set.env_spec_hash == 'hash2.0'

    with_directory_contents(
        {
            DEFAULT_PROJECT_LOCK_FILENAME:
            """
locking_enabled: false
env_specs:
  foo:
    platforms: [linux-32,linux-64,osx-64,osx-arm64,win-32,win-64]
    packages:
      all:
        - foo=1.0=1
  bar:
    locked: false
    platforms: [linux-32,linux-64,osx-64,osx-arm64,win-32,win-64]
    packages:
      all:
        - bar=2.0=2
"""
        }, check_file)


def test_set_lock_set_has_to_create_env_specs_to_disable():
    def check_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_LOCK_FILENAME)
        assert os.path.exists(filename)
        lock_file = ProjectLockFile.load_for_directory(dirname)

        all_names = ['foo', 'bar']

        lock_set = CondaLockSet({'all': ['something=3.0=0']},
                                platforms=['linux-32', 'linux-64', 'osx-64', 'osx-arm64', 'win-32', 'win-64'])

        # so the point of this test is that we need to create env_specs
        # dict and the 'foo' entry as a side effect of setting 'bar',
        # in order to mark 'foo' disabled.
        lock_file._set_lock_set('bar', lock_set, all_names=all_names)

        # "foo" should have been DISABLED since we had to
        # enable the global flag in order to enable "bar"
        foo_lock_set = _get_lock_set(lock_file, 'foo')
        assert lock_file.get_value(['env_specs', 'foo', 'locked']) is False
        assert foo_lock_set.disabled

        bar_lock_set = _get_lock_set(lock_file, 'bar')
        assert bar_lock_set.enabled
        assert ('something=3.0=0', ) == bar_lock_set.package_specs_for_current_platform

        # be sure we can save
        lock_file.save()

        reloaded = ProjectLockFile.load_for_directory(dirname)

        assert ('something=3.0=0', ) == _get_lock_set(reloaded, 'bar').package_specs_for_current_platform
        assert _get_lock_set(reloaded, 'foo').disabled

    with_directory_contents({DEFAULT_PROJECT_LOCK_FILENAME: """
locking_enabled: false
"""}, check_file)
