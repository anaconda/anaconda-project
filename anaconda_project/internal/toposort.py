# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import collections


class CycleError(Exception):
    def __init__(self, involving):
        """Initialize CycleError."""
        message = "Cycle in graph involving {involving}".format(involving=involving)
        super(CycleError, self).__init__(message)
        self.involving = involving


def toposort(nodes, get_next_nodes):
    """Sort list of graph nodes.

    Returns a new list, does not modify input list.

    Args:
        nodes (iterable): iterable of some kind of node
        get_next_nodes (function): takes a node and returns iterable of next nodes

    Returns:
        new sorted list of nodes
    """
    traversing = set()
    traversed = set()
    result = collections.deque()

    def traverse(node):
        if node in traversing:
            raise CycleError(node)
        if node in traversed:
            return  # not a cycle but we already saw this
        traversing.add(node)
        for next in get_next_nodes(node):
            traverse(next)
        traversed.add(node)
        traversing.remove(node)
        result.appendleft(node)

    for node in nodes:
        traverse(node)

    return list(result)


def toposort_from_dependency_info(nodes, get_node_key, get_dependency_keys, can_ignore_dependency=None):
    """Sort list of nodes that depend on other nodes in dependency-first order.

    All dependencies must be in the list of nodes.

    Returns a new list, does not modify input list.

    Args:
        nodes (iterable): iterable of some kind of node
        get_node_key (function): get identifier for a node
        get_dependency_keys (function): get iterable of node identifiers a node depends on

    Returns:
        new sorted list of nodes
    """
    nodes_by_key = dict()
    node_depended_on_by = dict()

    for node in nodes:
        key = get_node_key(node)
        if key in nodes_by_key:
            raise ValueError("two nodes with the same key %r" % key)
        nodes_by_key[key] = node
        node_depended_on_by[key] = set()

    for node in nodes:
        dep_keys = get_dependency_keys(node)
        for dep_key in dep_keys:
            if dep_key not in nodes_by_key:
                if can_ignore_dependency is None or not can_ignore_dependency(dep_key):
                    raise ValueError("Dependency %r was not in the list of nodes %r" % (dep_key, nodes))
            else:
                node_depended_on_by[dep_key].add(node)

    return toposort(nodes, lambda n: node_depended_on_by[get_node_key(n)])
