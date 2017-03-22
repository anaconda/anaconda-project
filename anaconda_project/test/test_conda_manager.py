# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import

import random

from anaconda_project.conda_manager import (push_conda_manager_class, pop_conda_manager_class, new_conda_manager,
                                            CondaManager, CondaLockSet, _pretty_platform_sort)
import anaconda_project.internal.conda_api as conda_api
from anaconda_project.yaml_file import _dump_string


def test_use_non_default_conda_manager():
    called = dict()

    class MyCondaManager(CondaManager):
        def resolve_dependencies(self, package_specs):
            return CondaLockSet({})

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
    lock_set = CondaLockSet({'all': ["something=0.5=2", "bokeh=0.12.4=1"],
                             'linux-64': ["linux-thing=1.0=0"],
                             'win': ["windows-cross-bit-thing=3.2"],
                             'win-32': ["windows-thing=2.0=3", "bokeh=2.3=7"]})
    # it is part of the API definition that we need to APPEND the
    # per-platform stuff, so it overrides.
    assert lock_set.package_specs_for_platform('win-32') == ("something=0.5=2", "windows-cross-bit-thing=3.2",
                                                             "windows-thing=2.0=3", "bokeh=2.3=7")

    # on Linux-64, test that it works without monkeypatch
    if conda_api.current_platform() != 'linux-64':
        monkeypatch.setattr('anaconda_project.internal.conda_api.current_platform', lambda: 'linux-64')

    assert lock_set.package_specs_for_current_platform == ("something=0.5=2", "bokeh=0.12.4=1", "linux-thing=1.0=0")


def test_lock_set_to_json(monkeypatch):
    lock_set = CondaLockSet({'all': ["something=0.5=2", "bokeh=0.12.4=1"],
                             'linux-64': ["linux-thing=1.0=0"],
                             'win-32': ["windows-thing=2.0=3", "bokeh=2.3=7"]})
    assert {'all': ['something=0.5=2', 'bokeh=0.12.4=1'],
            'linux-64': ['linux-thing=1.0=0'],
            'win-32': ['windows-thing=2.0=3', 'bokeh=2.3=7']} == lock_set.to_json()


def test_pretty_platform_sort():
    everything_sorted = ('all', 'linux', 'osx', 'win') + conda_api.popular_platforms
    backward = list(reversed(everything_sorted))
    shuffled = list(everything_sorted)
    random.shuffle(shuffled)

    assert everything_sorted == tuple(_pretty_platform_sort(backward))
    assert everything_sorted == tuple(_pretty_platform_sort(shuffled))
    assert [] == _pretty_platform_sort([])


def test_lock_set_to_yaml(monkeypatch):
    lock_set = CondaLockSet({'all': ['a', 'b'], 'linux': ['x'], 'win': ['y'], 'linux-64': ['z', 'q'], 'osx-64': ['s']})

    # Mostly our interest here is that the ordering of the dict
    # is deterministic
    j = lock_set.to_json()
    assert _dump_string(j) == """all:
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
    old_lock_set = CondaLockSet({'all': ['a', 'b'],
                                 'linux': ['x'],
                                 'win': ['y'],
                                 'linux-64': ['z', 'q'],
                                 'osx-64': ['s']})
    new_lock_set = CondaLockSet({'all': ['a', 'b', 'c'],
                                 'linux': ['x', 'h'],
                                 'win': ['y'],
                                 'linux-64': ['q', 'w'],
                                 'osx-64': ['s'],
                                 'win-64': ['j']})

    assert """  all:
+    c
  linux:
+    h
  linux-64:
-    z
+    w
+ win-64:
+    j""" == new_lock_set.diff_from(old_lock_set)

    assert """  all:
-    c
  linux:
-    h
  linux-64:
+    z
-    w
- win-64:
-    j""" == old_lock_set.diff_from(new_lock_set)

    assert "" == new_lock_set.diff_from(new_lock_set)
    assert "" == old_lock_set.diff_from(old_lock_set)

    assert old_lock_set.equivalent_to(old_lock_set)
    assert new_lock_set.equivalent_to(new_lock_set)
    assert not old_lock_set.equivalent_to(new_lock_set)
    assert not new_lock_set.equivalent_to(old_lock_set)
