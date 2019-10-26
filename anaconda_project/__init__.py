# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Library for working with projects."""
from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

_beta_test_mode = False


def _enter_beta_test_mode():
    """Called by anaconda-project executable to do special things for beta."""
    global _beta_test_mode
    _beta_test_mode = True
