# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------

from __future__ import absolute_import, print_function

from anaconda_project import __version__ as version


def test_version():
    assert isinstance(version, (type('str'), type(u'str')))
