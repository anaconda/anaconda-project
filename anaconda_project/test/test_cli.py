# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
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
