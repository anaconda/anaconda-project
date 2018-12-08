# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2017, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function, unicode_literals

import json
import os

import anaconda_project.internal.notebook_analyzer as notebook_analyzer

from anaconda_project.internal.test.tmpfile_utils import with_directory_contents


def _fake_notebook_json_with_code(source):
    ipynb = {
        "cells": [{
            "cell_type": "code",
            # source is a list of lines with the newline included in each
            "source": [(s + "\n") for s in source.split("\n")]
        }]
    }
    return ipynb


def _with_code_in_notebook_file(source, f):
    def check(dirname):
        filename = os.path.join(dirname, "foo.ipynb")
        return f(filename)

    json_string = json.dumps(_fake_notebook_json_with_code(source))
    with_directory_contents({"foo.ipynb": json_string}, check)


def test_extras_with_simple_has_fusion_register():
    def check(filename):
        errors = []
        extras = notebook_analyzer.extras(filename, errors)
        assert [] == errors
        assert extras == {'registers_fusion_function': True}

    _with_code_in_notebook_file("""
@fusion.register
def some_func():
   pass
    """, check)


def test_extras_without_has_fusion_register():
    def check(filename):
        errors = []
        extras = notebook_analyzer.extras(filename, errors)
        assert [] == errors
        assert extras == {}

    _with_code_in_notebook_file("""
def some_func():
   pass
    """, check)


def test_fusion_register():
    assert not notebook_analyzer._has_fusion_register("")
    assert not notebook_analyzer._has_fusion_register("fusion.register\n")
    assert notebook_analyzer._has_fusion_register("@fusion.register\n")
    assert notebook_analyzer._has_fusion_register("    @fusion.register\n")
    assert not notebook_analyzer._has_fusion_register("# @fusion.register\n")
    assert notebook_analyzer._has_fusion_register("# foo\n@fusion.register\n")
    assert notebook_analyzer._has_fusion_register("# foo\n\n    @fusion.register\n")
    assert notebook_analyzer._has_fusion_register("@fusion.register # foo\n")
    assert notebook_analyzer._has_fusion_register("""
@fusion.register(args=blah)
def some_func():
   pass
""")
    assert not notebook_analyzer._has_fusion_register("""
# @fusion.register
def some_func():
   pass
""")


def test_extras_with_io_error(monkeypatch):
    def mock_codecs_open(*args, **kwargs):
        raise IOError("Nope")

    monkeypatch.setattr('codecs.open', mock_codecs_open)
    errors = []
    extras = notebook_analyzer.extras("blah", errors)
    assert [] != errors
    assert extras is None
    assert 'Failed to read or parse' in errors[0]
