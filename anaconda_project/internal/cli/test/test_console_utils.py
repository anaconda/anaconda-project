# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import sys

import anaconda_project.internal.cli.console_utils as console_utils


def test_stdin_is_interactive(monkeypatch):
    result = console_utils.stdin_is_interactive()
    assert result is True or result is False


def _monkeypatch_input(monkeypatch, answer):
    answers = []
    if answer is None or isinstance(answer, str):
        answers.append(answer)
    else:
        answers = list(answer)
        answers.reverse()

    def mock_input(prompt):
        sys.stdout.write(prompt)
        item = answers.pop()
        if item is None:
            raise EOFError("eof on input")
        else:
            return item

    monkeypatch.setattr('anaconda_project.internal.cli.console_utils._input', mock_input)


def _monkeypatch_getpass(monkeypatch, answer):
    answers = []
    if answer is None or isinstance(answer, str):
        answers.append(answer)
    else:
        answers = list(answer)
        answers.reverse()

    def mock_getpass(prompt, stream=None):
        sys.stderr.write(prompt)
        item = answers.pop()
        if item is None:
            raise EOFError("eof on getpass")
        else:
            return item

    monkeypatch.setattr('getpass.getpass', mock_getpass)


def test_console_yes_or_no(monkeypatch, capsys):
    def mock_isatty_true():
        return True

    # python 2 can throw a "readonly" error if you try to patch sys.stdin.isatty itself
    monkeypatch.setattr('anaconda_project.internal.cli.console_utils.stdin_is_interactive', mock_isatty_true)

    for answer in ("y", "Y", "yes", "Yes", "YES", "yoyo"):
        _monkeypatch_input(monkeypatch, answer)
        assert console_utils.console_ask_yes_or_no("foo?", False)
        out, err = capsys.readouterr()
        assert out == "foo? "
        assert err == ""

    for answer in ("n", "N", "no", "No", "NO", "nay"):
        _monkeypatch_input(monkeypatch, answer)
        assert not console_utils.console_ask_yes_or_no("foo?", True)
        out, err = capsys.readouterr()
        assert out == "foo? "
        assert err == ""

    _monkeypatch_input(monkeypatch, ("", "yes"))
    assert console_utils.console_ask_yes_or_no("foo?", False)
    out, err = capsys.readouterr()
    assert out == "foo? foo? (enter y or n): "
    assert err == ""

    _monkeypatch_input(monkeypatch, None)
    assert console_utils.console_ask_yes_or_no("foo?", True)
    out, err = capsys.readouterr()
    assert out == "foo? "
    assert err == ""

    _monkeypatch_input(monkeypatch, None)
    assert not console_utils.console_ask_yes_or_no("foo?", False)
    out, err = capsys.readouterr()
    assert out == "foo? "
    assert err == ""


def test_format_names_and_descriptions():
    class Thing(object):
        def __init__(self, name, description):
            self.name = name
            self.description = description

    cases = [([], "\n"), ([Thing("a", "b")], "Name  Description\n====  ===========\na     b\n"),
             ([Thing("cd", "ef"), Thing("a", "b")], "Name  Description\n====  ===========\na     b\ncd    ef\n")]
    for case in cases:
        assert console_utils.format_names_and_descriptions(case[0]) == case[1]


def test_console_get_password(monkeypatch, capsys):
    def mock_isatty_true():
        return True

    # python 2 can throw a "readonly" error if you try to patch sys.stdin.isatty itself
    monkeypatch.setattr('anaconda_project.internal.cli.console_utils.stdin_is_interactive', mock_isatty_true)

    _monkeypatch_getpass(monkeypatch, "s3kr3t")

    password = console_utils.console_input("foo: ", encrypted=True)

    assert password == 's3kr3t'

    (out, err) = capsys.readouterr()

    assert out == ''
    assert err == 'foo: '
