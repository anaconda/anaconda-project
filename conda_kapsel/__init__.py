# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Library for working with projects."""

_beta_test_mode = False


def _enter_beta_test_mode():
    """Called by anaconda-project executable to do special things for beta."""
    global _beta_test_mode
    _beta_test_mode = True
