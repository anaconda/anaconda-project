# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Internal file and directory utilities."""
from __future__ import absolute_import, print_function

import os


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
