# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import pytest

from anaconda_project.internal.toposort import toposort_from_dependency_info, CycleError


# sort tuples of the form (thing, (dep1, dep2))
def sort_tuples(tuples, can_ignore=None):
    def get_node_key(t):
        return t[0]

    def get_dependency_keys(t):
        return t[1]

    def can_ignore_key(k):
        return k in can_ignore

    if can_ignore is None:
        can_ignore_func = None
    else:
        can_ignore_func = can_ignore_key

    return list(
        map(lambda t: t[0], toposort_from_dependency_info(tuples, get_node_key, get_dependency_keys, can_ignore_func)))


def test_empty():
    sorted = sort_tuples([])
    assert [] == sorted


def test_one():
    unsorted = [(1, ())]
    sorted = sort_tuples(unsorted)
    assert [1] == sorted


def test_two():
    unsorted = [(1, (2, )), (2, ())]
    sorted = sort_tuples(unsorted)
    assert [2, 1] == sorted


def test_three():
    unsorted = [(1, (2, 3)), (2, (3, )), (3, ())]
    sorted = sort_tuples(unsorted)
    assert [3, 2, 1] == sorted


def test_four():
    unsorted = [(1, (2, 3)), (2, (3, 4)), (3, ()), (4, ())]
    sorted = sort_tuples(unsorted)
    assert [4, 3, 2, 1] == sorted or [3, 4, 2, 1] == sorted


def test_cycle():
    unsorted = [(1, (2, )), (2, (1, ))]
    with pytest.raises(CycleError) as excinfo:
        sort_tuples(unsorted)
    assert 'Cycle in graph' in repr(excinfo.value)
    assert isinstance(excinfo.value.involving, tuple)


def test_duplicate_nodes():
    unsorted = [(1, (2, )), (1, ()), (2, ())]
    with pytest.raises(ValueError) as excinfo:
        sort_tuples(unsorted)
    assert 'two nodes with the same key 1' in repr(excinfo.value)


def test_dependency_not_in_list():
    unsorted = [(1, (2, ))]
    with pytest.raises(ValueError) as excinfo:
        sort_tuples(unsorted)
    assert 'Dependency 2 was not in the list of nodes' in repr(excinfo.value)


def test_dependency_not_in_list_but_can_ignore_that():
    unsorted = [(1, (2, ))]
    sorted = sort_tuples(unsorted, can_ignore=set([2]))
    assert [1] == sorted
