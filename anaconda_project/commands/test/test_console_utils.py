# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import sys

import anaconda_project.commands.console_utils as console_utils


def test_stdin_is_interactive(monkeypatch):
    def mock_isatty_true():
        return True

    monkeypatch.setattr('sys.stdin.isatty', mock_isatty_true)
    assert console_utils.stdin_is_interactive()

    def mock_isatty_false():
        return False

    monkeypatch.setattr('sys.stdin.isatty', mock_isatty_false)
    assert not console_utils.stdin_is_interactive()


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

    monkeypatch.setattr('anaconda_project.commands.console_utils._input', mock_input)


def test_console_yes_or_no(monkeypatch, capsys):
    def mock_isatty_true():
        return True

    monkeypatch.setattr('sys.stdin.isatty', mock_isatty_true)

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
