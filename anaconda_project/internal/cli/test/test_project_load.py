# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import sys

from anaconda_project.project import Project
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME
from anaconda_project.internal.cli.project_load import load_project

from anaconda_project.internal.test.tmpfile_utils import with_directory_contents


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


def test_interactively_fix_project(monkeypatch, capsys):
    def check(dirname):

        broken_project = Project(dirname)
        assert len(broken_project.fixable_problems) == 1

        def mock_isatty_true():
            return True

        # python 2 can throw a "readonly" error if you try to patch sys.stdin.isatty itself
        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.stdin_is_interactive', mock_isatty_true)
        _monkeypatch_input(monkeypatch, ["y"])

        project = load_project(dirname)
        assert project.problems == []

        out, err = capsys.readouterr()
        assert out == ("%s: The env_specs section is empty.\nAdd an environment spec to anaconda-project.yml? " %
                       DEFAULT_PROJECT_FILENAME)
        assert err == ""

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "name: foo"}, check)


def test_interactively_no_fix_project(monkeypatch, capsys):
    def check(dirname):

        broken_project = Project(dirname)
        assert len(broken_project.fixable_problems) == 1

        def mock_isatty_true():
            return True

        # python 2 can throw a "readonly" error if you try to patch sys.stdin.isatty itself
        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.stdin_is_interactive', mock_isatty_true)
        _monkeypatch_input(monkeypatch, ["n"])

        project = load_project(dirname)
        assert project.problems == ["%s: The env_specs section is empty." % DEFAULT_PROJECT_FILENAME]

        out, err = capsys.readouterr()
        assert out == ("%s: The env_specs section is empty.\nAdd an environment spec to anaconda-project.yml? " %
                       DEFAULT_PROJECT_FILENAME)
        assert err == ""

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "name: foo\nplatforms: [linux-64,osx-64,win-64]\n"}, check)
