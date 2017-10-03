# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Internal file and directory utilities."""
from __future__ import absolute_import, print_function

import os
import platform


def directory_contains_subdirectory(parent, child):
    """Test whether child is somewhere underneath parent."""
    parent = os.path.realpath(parent)
    child = os.path.realpath(child)

    # note: there's an os.path.commonprefix() but it's useless
    # because it's character-based so it thinks /foo is the common
    # prefix of /foo and /foobar.
    def _helper(real_parent, real_child):
        dirname = os.path.dirname(real_child)
        if dirname == real_parent:
            return True
        elif len(dirname) < len(real_parent):
            return False
        else:
            return _helper(real_parent, dirname)

    return _helper(parent, child)


def subdirectory_relative_to_directory(child, parent):
    """Make subdirectory name relative to the given parent."""
    parent = os.path.realpath(parent)
    child = os.path.realpath(child)

    if not directory_contains_subdirectory(parent, child):
        return child

    assert child.startswith(parent)

    child = child[len(parent):]
    if child.startswith("/"):  # on both unix and windows
        child = child[1:]
    if platform.system() == 'Windows' and child.startswith("\\"):
        child = child[1:]  # pragma: no cover (too hard to test on linux)
    return child
