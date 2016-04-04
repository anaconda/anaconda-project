# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function

from project.internal.shell_cmdline import (shell_split_command_line, shell_join_command_line)


def _roundtrip(args):
    joined = shell_join_command_line(args)
    assert isinstance(joined, str)
    split = shell_split_command_line(joined)
    assert isinstance(split, list)
    for s in split:
        assert isinstance(s, str)
    assert split == args


def test_empty_args():
    _roundtrip([])


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


def test_single_arg_which_is_a_double_quote():
    _roundtrip(['"'])


def test_single_arg_which_is_a_single_quote():
    _roundtrip(["'"])


def test_single_arg_which_is_a_dollar():
    _roundtrip(["$"])


def test_multiple_args():
    _roundtrip(["foo", "bar"])


def test_multiple_args_with_spaces_and_quotes():
    _roundtrip(["foo", "bl ah", " bar ", "b\"az", "''"])


def test_multiple_args_with_backslash():
    _roundtrip(["foo", "bl\\ah"])


def test_multiple_args_with_unicode():
    _roundtrip(["foo", "bÄr", "¿"])


def test_multiple_args_which_are_spaces():
    _roundtrip([" ", " ", " "])
