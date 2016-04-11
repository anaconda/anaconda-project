# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from anaconda_project.internal import keyring


def test_get_set():
    keyring.set("FOO", "bar")
    assert "bar" == keyring.get("FOO")
