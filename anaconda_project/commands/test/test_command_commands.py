# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from anaconda_project.commands.command_commands import main
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME
from anaconda_project.project import Project


class Args(object):
    def __init__(self, type, name, command, project='.'):
        self.type = type
        self.name = name
        self.command = command
        self.project = project


def test_add_command_ask_type(monkeypatch):
    def check_ask_type(dirname):
        def mock_console_input(prompt):
            return "b"

        monkeypatch.setattr('anaconda_project.commands.console_utils.console_input', mock_console_input)

        args = Args(None, 'test', 'file.py', project=dirname)
        res = main(args)
        assert res == 0

        project = Project(dirname)

        command = project.project_file.get_value(['commands', 'test'])
        assert len(command.keys()) == 1
        assert command['bokeh_app'] == 'file.py'

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ''}, check_ask_type)


def test_add_command_ask_type_interrupted(monkeypatch, capsys):
    def check_ask_type(dirname):
        def mock_console_input(prompt):
            raise KeyboardInterrupt('^C')

        monkeypatch.setattr('anaconda_project.commands.console_utils.console_input', mock_console_input)

        args = Args(None, 'test', 'file.py', project=dirname)
        res = main(args)
        assert res == 1

        out, err = capsys.readouterr()
        assert out == '\nCanceling\n\n'

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ''}, check_ask_type)


def test_add_command_ask_type_twice(monkeypatch, capsys):
    def check_ask_type(dirname):
        calls = []

        def mock_console_input(prompt):
            res = ['-', 'b'][len(calls)]
            calls.append(True)
            return res

        monkeypatch.setattr('anaconda_project.commands.console_utils.console_input', mock_console_input)

        args = Args(None, 'test', 'file.py', project=dirname)
        res = main(args)
        assert res == 0
        assert len(calls) == 2

        project = Project(dirname)

        command = project.project_file.get_value(['commands', 'test'])
        assert len(command.keys()) == 1
        assert command['bokeh_app'] == 'file.py'
        out, err = capsys.readouterr()
        assert out == 'Invalid choice! Please choose between (B)okeh app, (N)otebook, (P)ython script, or (O)ther\n'

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ''}, check_ask_type)


def test_add_command_specifying_notebook(monkeypatch, capsys):
    def check_specifying_notebook(dirname):
        args = Args('notebook', 'test', 'file.ipynb', project=dirname)
        res = main(args)
        assert res == 0

        project = Project(dirname)

        command = project.project_file.get_value(['commands', 'test'])
        assert command['notebook'] == 'file.ipynb'
        assert len(command.keys()) == 1

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ''}, check_specifying_notebook)


def test_add_command_guessing_notebook(monkeypatch, capsys):
    def check_guessing_notebook(dirname):
        args = Args(None, 'test', 'file.ipynb', project=dirname)
        res = main(args)
        assert res == 0

        project = Project(dirname)

        command = project.project_file.get_value(['commands', 'test'])
        assert command['notebook'] == 'file.ipynb'
        assert len(command.keys()) == 1

    with_directory_contents({DEFAULT_PROJECT_FILENAME: '', 'file.ipynb': ""}, check_guessing_notebook)


def test_add_command_project_problem(capsys, monkeypatch):
    def check_problem_add_cmd(dirname):
        args = Args('notebook', 'test', 'file.ipynb', project=dirname)
        res = main(args)
        assert res == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert ('Unable to load project:\n  variables section contains wrong value type 42,' +
                ' should be dict or list of requirements\n') == err

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ("variables:\n" "  42")}, check_problem_add_cmd)
