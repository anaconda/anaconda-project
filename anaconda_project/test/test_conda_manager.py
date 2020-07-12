# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import

from anaconda_project.conda_manager import (push_conda_manager_class, pop_conda_manager_class, new_conda_manager,
                                            CondaManager, CondaLockSet)
import anaconda_project.internal.conda_api as conda_api
from anaconda_project.yaml_file import _dump_string


def test_use_non_default_conda_manager():
    called = dict()

    class MyCondaManager(CondaManager):
        def __init__(self, frontend):
            pass

        def resolve_dependencies(self, package_specs, channels, platforms):
            return CondaLockSet({}, platforms=[])

        def find_environment_deviations(self, *args):
            called['find_environment_deviations'] = args

        def fix_environment_deviations(self, *args):
            called['fix_environment_deviations'] = args

        def remove_packages(self, *args):
            called['remove_packages'] = args

    push_conda_manager_class(MyCondaManager)
    try:
        manager = new_conda_manager()
        manager.find_environment_deviations(None, None)
        manager.fix_environment_deviations(None, None)
        manager.remove_packages(None, None)
        assert dict(find_environment_deviations=(None, None),
                    fix_environment_deviations=(None, None),
                    remove_packages=(None, None)) == called
    finally:
        pop_conda_manager_class()


def test_lock_set_properties(monkeypatch):
    lock_set = CondaLockSet(
        {
            'all': ["something=0.5=2", "bokeh=0.12.4=1"],
            'linux-64': ["linux-thing=1.0=0"],
            'unix': ["unix-thing=5=1"],
            'win': ["windows-cross-bit-thing=3.2"],
            'win-32': ["windows-thing=2.0=3", "bokeh=2.3=7"]
        },
        platforms=['linux-64', 'win-32'])
    # it is part of the API definition that we need to APPEND the
    # per-platform stuff, so it overrides.
    assert lock_set.package_specs_for_platform('win-32') == ("something=0.5=2", "windows-cross-bit-thing=3.2",
                                                             "windows-thing=2.0=3", "bokeh=2.3=7")

    # on Linux-64, test that it works without monkeypatch
    if conda_api.current_platform() != 'linux-64':
        monkeypatch.setattr('anaconda_project.internal.conda_api.current_platform', lambda: 'linux-64')

    assert lock_set.package_specs_for_current_platform == ("something=0.5=2", "bokeh=0.12.4=1", "unix-thing=5=1",
                                                           "linux-thing=1.0=0")

    assert lock_set.platforms == ('linux-64', 'win-32')


def test_lock_set_to_json(monkeypatch):
    lock_set = CondaLockSet(
        {
            'all': ["something=0.5=2", "bokeh=0.12.4=1"],
            'linux-64': ["linux-thing=1.0=0"],
            'win-32': ["windows-thing=2.0=3", "bokeh=2.3=7"]
        },
        platforms=['linux-64', 'win-32'])
    assert {
        'locked': True,
        'packages': {
            'all': ['something=0.5=2', 'bokeh=0.12.4=1'],
            'linux-64': ['linux-thing=1.0=0'],
            'win-32': ['windows-thing=2.0=3', 'bokeh=2.3=7']
        },
        'platforms': ['linux-64', 'win-32']
    } == lock_set.to_json()


def test_lock_set_to_yaml(monkeypatch):
    lock_set = CondaLockSet({
        'all': ['a', 'b'],
        'linux': ['x'],
        'win': ['y'],
        'linux-64': ['z', 'q'],
        'osx-64': ['s']
    },
                            platforms=['linux-64', 'win-64', 'osx-64'])

    # Mostly our interest here is that the ordering of the dict
    # is deterministic
    j = lock_set.to_json()
    assert _dump_string(j) == """locked: true
platforms:
- linux-64
- osx-64
- win-64
packages:
  all:
  - a
  - b
  linux:
  - x
  win:
  - y
  linux-64:
  - z
  - q
  osx-64:
  - s
"""


def test_lock_set_diff_and_equivalent():
    old_lock_set = CondaLockSet(
        {
            'all': ['a', 'b'],
            'linux': ['x'],
            'win': ['y'],
            'linux-64': ['z', 'q'],
            'osx-64': ['s']
        },
        platforms=['linux-64', 'osx-64'])
    new_lock_set = CondaLockSet(
        {
            'all': ['a', 'b', 'c'],
            'linux': ['x', 'h'],
            'win': ['y'],
            'linux-64': ['q', 'w'],
            'osx-64': ['s'],
            'win-64': ['j']
        },
        platforms=['linux-64', 'win-64'])

    assert """  platforms:
-   osx-64
+   win-64
  packages:
    all:
+     c
    linux:
+     h
    linux-64:
-     z
+     w
+   win-64:
+     j""" == new_lock_set.diff_from(old_lock_set)

    assert """  platforms:
-   win-64
+   osx-64
  packages:
    all:
-     c
    linux:
-     h
    linux-64:
+     z
-     w
-   win-64:
-     j""" == old_lock_set.diff_from(new_lock_set)

    assert "" == new_lock_set.diff_from(new_lock_set)
    assert "" == old_lock_set.diff_from(old_lock_set)

    assert old_lock_set.equivalent_to(old_lock_set)
    assert new_lock_set.equivalent_to(new_lock_set)
    assert not old_lock_set.equivalent_to(new_lock_set)
    assert not new_lock_set.equivalent_to(old_lock_set)

    assert """  platforms:
+   linux-64
+   win-64
  packages:
+   all:
+     a
+     b
+     c
+   linux:
+     x
+     h
+   win:
+     y
+   linux-64:
+     q
+     w
+   osx-64:
+     s
+   win-64:
+     j""" == new_lock_set.diff_from(None)
