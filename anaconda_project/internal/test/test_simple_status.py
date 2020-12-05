# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from anaconda_project.internal.simple_status import SimpleStatus


def test_simple_status_properties():
    good_status = SimpleStatus(success=True, description="quick brown fox", errors=["bar"])
    assert good_status
    assert good_status.status_description == "quick brown fox"
    assert good_status.errors == ["bar"]

    bad_status = SimpleStatus(success=False, description="quick brown fox", errors=["bar"])
    assert not bad_status
    assert bad_status.status_description == "quick brown fox"
    assert bad_status.errors == ["bar"]
