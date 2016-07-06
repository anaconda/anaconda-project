# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from conda_kapsel.internal.simple_status import SimpleStatus


def test_simple_status_properties():
    good_status = SimpleStatus(success=True, description="quick brown fox", logs=["foo"], errors=["bar"])
    assert good_status
    assert good_status.status_description == "quick brown fox"
    assert good_status.logs == ["foo"]
    assert good_status.errors == ["bar"]

    bad_status = SimpleStatus(success=False, description="quick brown fox", logs=["foo"], errors=["bar"])
    assert not bad_status
    assert bad_status.status_description == "quick brown fox"
    assert bad_status.logs == ["foo"]
    assert bad_status.errors == ["bar"]
