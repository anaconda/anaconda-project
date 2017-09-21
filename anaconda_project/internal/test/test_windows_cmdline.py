# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import platform
import pytest

from anaconda_project.internal.windows_cmdline import (windows_split_command_line, windows_join_command_line,
                                                       WindowsCommandLineException)


def _roundtrip(args):
    if platform.system() != 'Windows':
        return
    joined = windows_join_command_line(args)
    assert isinstance(joined, str)
    split = windows_split_command_line(joined)
    assert isinstance(split, list)
    for s in split:
        assert isinstance(s, str)
    assert split == args


def test_empty_args():
    with pytest.raises(WindowsCommandLineException) as excinfo:
        windows_join_command_line([])
    assert "Windows has no way to encode an empty arg list as a command line" in str(excinfo.value)


def test_single_arg():
    _roundtrip(["foo"])


def test_single_arg_with_spaces():
    _roundtrip(["foo bar"])


def test_single_arg_with_backslash():
    _roundtrip(["foo\\bar"])


def test_single_arg_with_double_quote():
    _roundtrip(['foo"bar'])


def test_single_arg_which_is_a_space():
    _roundtrip([" "])


def test_multiple_args():
    _roundtrip(["foo", "bar"])


def test_multiple_args_with_spaces_and_quotes():
    _roundtrip(["foo", "bl ah", " bar ", "b\"az"])


def test_multiple_args_with_backslash():
    _roundtrip(["foo", "bl\\ah"])


def test_multiple_args_with_unicode():
    try:
        _roundtrip(["foo", "bÄr", "¿"])
    except WindowsCommandLineException as e:
        # on Win32/py2 apparently we end up in ASCII
        if 'cannot represent this command line in its character encoding' not in str(e):
            raise e


def test_multiple_args_which_are_spaces():
    _roundtrip([" ", " ", " "])


def test_cannot_join_first_arg_starting_with_quote():
    with pytest.raises(WindowsCommandLineException) as excinfo:
        windows_join_command_line(['"foo'])
    assert 'Windows does not allow the first arg to start with a quote' in str(excinfo.value)


def test_cannot_join_first_arg_with_quote_and_space():
    with pytest.raises(WindowsCommandLineException) as excinfo:
        windows_join_command_line(['foo"bar baz'])
    assert 'Windows does not allow the first arg to have both quotes and spaces' in str(excinfo.value)
