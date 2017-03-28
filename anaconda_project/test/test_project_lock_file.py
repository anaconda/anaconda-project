# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
import codecs
import os

from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
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
locking_enabled: false



#
# A key goes in here for each env spec.
#
env_specs: {}
"""


def test_create_missing_lock_file():
    def create_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_LOCK_FILENAME)
        assert not os.path.exists(filename)
        lock_file = ProjectLockFile.load_for_directory(dirname)
        assert lock_file is not None
        assert not os.path.exists(filename)

        assert lock_file._get_lock_set('foo').disabled
        assert not lock_file._get_locking_enabled('foo')

        lock_file.save()
        assert os.path.exists(filename)
        with codecs.open(filename, 'r', 'utf-8') as file:
            contents = file.read()
            assert expected_default_file == contents

    with_directory_contents(dict(), create_file)


def _use_existing_lock_file(relative_name):
    def check_file(dirname):
        filename = os.path.join(dirname, relative_name)
        assert os.path.exists(filename)
        lock_file = ProjectLockFile.load_for_directory(dirname)
        assert lock_file.get_value(['env_specs', 'foo']) is not None
        assert lock_file.get_value(['locking_enabled']) is True

    with_directory_contents(
        {relative_name: """
locking_enabled: true
env_specs:
  foo:
    locked: true
    platforms: [all]
    packages:
      all:
        - foo=1.0=1
  bar:
    locked: false
    platforms: [all]
    packages:
      all:
        - bar=2.0=2
"""}, check_file)


def test_use_existing_lock_file_default_name():
    _use_existing_lock_file(DEFAULT_PROJECT_LOCK_FILENAME)


def test_use_existing_lock_file_all_names():
    for name in possible_project_lock_file_names:
        _use_existing_lock_file(name)


def test_get_lock_set():
    def check_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_LOCK_FILENAME)
        assert os.path.exists(filename)
        lock_file = ProjectLockFile.load_for_directory(dirname)
        foo_lock_set = lock_file._get_lock_set('foo')
        assert foo_lock_set.enabled
        assert ('foo=1.0=1', ) == foo_lock_set.package_specs_for_current_platform
        bar_lock_set = lock_file._get_lock_set('bar')
        assert bar_lock_set.disabled

    with_directory_contents(
        {DEFAULT_PROJECT_LOCK_FILENAME: """
locking_enabled: true
env_specs:
  foo:
    locked: true
    platforms: [all]
    packages:
      all:
        - foo=1.0=1
  bar:
    locked: false
    platforms: [all]
    packages:
      all:
        - bar=2.0=2
"""}, check_file)


def test_disable_single_spec_locking():
    def check_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_LOCK_FILENAME)
        assert os.path.exists(filename)
        lock_file = ProjectLockFile.load_for_directory(dirname)
        foo_lock_set = lock_file._get_lock_set('foo')
        assert ('foo=1.0=1', ) == foo_lock_set.package_specs_for_current_platform

        lock_file._disable_locking('foo')

        foo_lock_set = lock_file._get_lock_set('foo')
        assert foo_lock_set.disabled
        assert lock_file._get_locking_enabled('foo') is False

    with_directory_contents(
        {DEFAULT_PROJECT_LOCK_FILENAME: """
locking_enabled: true
env_specs:
  foo:
    locked: true
    platforms: [all]
    packages:
      all:
        - foo=1.0=1
  bar:
    locked: false
    platforms: [all]
    packages:
      all:
        - bar=2.0=2
"""}, check_file)


def test_set_lock_set():
    def check_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_LOCK_FILENAME)
        assert os.path.exists(filename)
        lock_file = ProjectLockFile.load_for_directory(dirname)

        # we have the global enabled flag off; individual
        # env spec settings override that; foo has no setting.
        foo_lock_set = lock_file._get_lock_set('foo')
        assert lock_file.get_value(['env_specs', 'foo', 'locked'], None) is None
        assert foo_lock_set.disabled
        bar_lock_set = lock_file._get_lock_set('bar')
        assert bar_lock_set.disabled

        all_names = ['foo', 'bar']

        lock_set = CondaLockSet({'all': ['something=3.0=0']}, platforms=['all'])

        lock_file._set_lock_set('bar', lock_set, all_names=all_names)

        # "foo" should have been DISABLED since we had to
        # enable the global flag in order to enable "bar"
        foo_lock_set = lock_file._get_lock_set('foo')
        assert lock_file.get_value(['env_specs', 'foo', 'locked']) is False
        assert foo_lock_set.disabled

        bar_lock_set = lock_file._get_lock_set('bar')
        assert bar_lock_set.enabled
        assert ('something=3.0=0', ) == bar_lock_set.package_specs_for_current_platform

        # and now we should enable "foo" when we set it to something
        lock_file._set_lock_set('foo', lock_set, all_names=all_names)
        foo_lock_set = lock_file._get_lock_set('foo')
        assert foo_lock_set.enabled
        assert ('something=3.0=0', ) == foo_lock_set.package_specs_for_current_platform

        # be sure we can save
        lock_file.save()

        reloaded = ProjectLockFile.load_for_directory(dirname)

        assert ('something=3.0=0', ) == reloaded._get_lock_set('bar').package_specs_for_current_platform
        assert ('something=3.0=0', ) == reloaded._get_lock_set('foo').package_specs_for_current_platform

    with_directory_contents(
        {DEFAULT_PROJECT_LOCK_FILENAME: """
locking_enabled: false
env_specs:
  foo:
    platforms: [all]
    packages:
      all:
        - foo=1.0=1
  bar:
    locked: false
    platforms: [all]
    packages:
      all:
        - bar=2.0=2
"""}, check_file)


def test_set_lock_set_has_to_create_env_specs_to_disable():
    def check_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_LOCK_FILENAME)
        assert os.path.exists(filename)
        lock_file = ProjectLockFile.load_for_directory(dirname)

        all_names = ['foo', 'bar']

        lock_set = CondaLockSet({'all': ['something=3.0=0']}, platforms=['all'])

        # so the point of this test is that we need to create env_specs
        # dict and the 'foo' entry as a side effect of setting 'bar',
        # in order to mark 'foo' disabled.
        lock_file._set_lock_set('bar', lock_set, all_names=all_names)

        # "foo" should have been DISABLED since we had to
        # enable the global flag in order to enable "bar"
        foo_lock_set = lock_file._get_lock_set('foo')
        assert lock_file.get_value(['env_specs', 'foo', 'locked']) is False
        assert foo_lock_set.disabled

        bar_lock_set = lock_file._get_lock_set('bar')
        assert bar_lock_set.enabled
        assert ('something=3.0=0', ) == bar_lock_set.package_specs_for_current_platform

        # be sure we can save
        lock_file.save()

        reloaded = ProjectLockFile.load_for_directory(dirname)

        assert ('something=3.0=0', ) == reloaded._get_lock_set('bar').package_specs_for_current_platform
        assert reloaded._get_lock_set('foo').disabled

    with_directory_contents({DEFAULT_PROJECT_LOCK_FILENAME: """
locking_enabled: false
"""}, check_file)


def test_empty_file_enables_locking():
    def check_file(dirname):
        lock_file = ProjectLockFile.load_for_directory(dirname)
        assert lock_file._get_locking_enabled('foo')

    with_directory_contents({DEFAULT_PROJECT_LOCK_FILENAME: """
"""}, check_file)


def test_default_file_disables_locking():
    def check_file(dirname):
        lock_file = ProjectLockFile.load_for_directory(dirname)
        assert not lock_file._get_locking_enabled('foo')

    with_directory_contents(dict(), check_file)
