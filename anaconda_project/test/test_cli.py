# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import anaconda_project.cli as cli


def test_main(monkeypatch):
    result = {}

    def mock_main(*args, **kwargs):
        result['args'] = args
        result['kwargs'] = kwargs

    monkeypatch.setattr('anaconda_project.internal.cli.main.main', mock_main)
    cli.main()

    assert dict(args=(), kwargs={}) == result
