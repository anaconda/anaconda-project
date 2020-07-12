# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import pytest

from anaconda_project.internal.cli.command_commands import main
from anaconda_project.internal.cli.main import _parse_args_and_run_subcommand
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents_completing_project_file
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME
from anaconda_project.project import Project


class Args(object):
    def __init__(self, type, name, command, directory='.'):
        self.type = type
        self.name = name
        self.command = command
        self.directory = directory
        self.env_spec = None
        self.supports_http_options = None


def test_add_command_ask_type(monkeypatch):
    def check_ask_type(dirname):
        def mock_is_interactive():
            return True

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.stdin_is_interactive', mock_is_interactive)

        def mock_console_input(prompt):
            return "b"

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.console_input', mock_console_input)

        args = Args(None, 'test', 'file.py', directory=dirname)
        res = main(args)
        assert res == 0

        project = Project(dirname)

        command = project.project_file.get_value(['commands', 'test'])
        assert len(command.keys()) == 2
        assert command['bokeh_app'] == 'file.py'
        assert command['env_spec'] == 'default'

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ''}, check_ask_type)


def test_add_command_not_interactive(monkeypatch, capsys):
    def check(dirname):
        def mock_is_interactive():
            return False

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.stdin_is_interactive', mock_is_interactive)

        args = Args(None, 'test', 'file.py', directory=dirname)
        res = main(args)
        assert res == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert 'Specify the --type option to add this command.\n' == err

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ''}, check)


def test_add_command_ask_type_interrupted(monkeypatch, capsys):
    def check_ask_type(dirname):
        def mock_is_interactive():
            return True

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.stdin_is_interactive', mock_is_interactive)

        def mock_input(prompt):
            raise KeyboardInterrupt('^C')

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils._input', mock_input)

        args = Args(None, 'test', 'file.py', directory=dirname)
        with pytest.raises(SystemExit) as excinfo:
            main(args)
        assert excinfo.value.code == 1

        out, err = capsys.readouterr()
        assert out == ''
        assert err == '\nCanceling\n\n'

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ''}, check_ask_type)


def test_add_command_ask_other_shell(monkeypatch):
    def check(dirname):
        def mock_is_interactive():
            return True

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.stdin_is_interactive', mock_is_interactive)

        def mock_console_input(prompt):
            return "c"

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.console_input', mock_console_input)

        def mock_system():
            return "Linux"

        monkeypatch.setattr('platform.system', mock_system)

        args = Args(None, 'test', 'echo hello', directory=dirname)
        res = main(args)
        assert res == 0

        project = Project(dirname)

        command = project.project_file.get_value(['commands', 'test'])
        assert len(command.keys()) == 2
        assert command['unix'] == 'echo hello'
        assert command['env_spec'] == 'default'

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ''}, check)


def test_add_command_ask_other_windows(monkeypatch):
    def check(dirname):
        def mock_is_interactive():
            return True

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.stdin_is_interactive', mock_is_interactive)

        def mock_console_input(prompt):
            return "c"

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.console_input', mock_console_input)

        def mock_system():
            return "Windows"

        monkeypatch.setattr('platform.system', mock_system)

        args = Args(None, 'test', 'echo hello', directory=dirname)
        res = main(args)
        assert res == 0

        project = Project(dirname)

        command = project.project_file.get_value(['commands', 'test'])
        assert len(command.keys()) == 2
        assert command['windows'] == 'echo hello'
        assert command['env_spec'] == 'default'

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ''}, check)


def test_add_command_ask_type_twice(monkeypatch, capsys):
    def check_ask_type(dirname):
        def mock_is_interactive():
            return True

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.stdin_is_interactive', mock_is_interactive)

        calls = []

        def mock_console_input(prompt):
            res = ['-', 'b'][len(calls)]
            calls.append(True)
            return res

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.console_input', mock_console_input)

        args = Args(None, 'test', 'file.py', directory=dirname)
        res = main(args)
        assert res == 0
        assert len(calls) == 2

        project = Project(dirname)

        command = project.project_file.get_value(['commands', 'test'])
        assert len(command.keys()) == 2
        assert command['bokeh_app'] == 'file.py'
        assert command['env_spec'] == 'default'
        out, err = capsys.readouterr()
        assert out == ("Please enter 'b', 'n', or 'c'.\n" +
                       "    A Bokeh app is the project-relative path to a Bokeh script or app directory.\n" +
                       "    A notebook file is the project-relative path to a .ipynb file.\n"
                       "    A command line is any command you might type at the command prompt.\n"
                       "Added a command 'test' to the project. Run it with `anaconda-project run test`.\n")

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ''}, check_ask_type)


def test_add_command_specifying_notebook(monkeypatch, capsys):
    def check_specifying_notebook(dirname):
        args = Args('notebook', 'test', 'file.ipynb', directory=dirname)
        res = main(args)
        assert res == 0

        project = Project(dirname)

        command = project.project_file.get_value(['commands', 'test'])
        assert command['notebook'] == 'file.ipynb'
        assert command['env_spec'] == 'default'
        assert len(command.keys()) == 2

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: 'packages:\n - notebook\n'},
                                                    check_specifying_notebook)


def test_add_command_guessing_notebook(monkeypatch, capsys):
    def check_guessing_notebook(dirname):
        args = Args(None, 'test', 'file.ipynb', directory=dirname)
        res = main(args)
        assert res == 0

        project = Project(dirname)

        command = project.project_file.get_value(['commands', 'test'])
        assert command['notebook'] == 'file.ipynb'
        assert command['env_spec'] == 'default'
        assert len(command.keys()) == 2

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: 'packages:\n - notebook\n',
            'file.ipynb': "{}"
        }, check_guessing_notebook)


def test_add_command_with_env_spec(monkeypatch, capsys):
    def check(dirname):
        code = _parse_args_and_run_subcommand([
            'anaconda-project', 'add-command', '--directory', dirname, '--env-spec', 'foo', '--type', 'notebook',
            'test', 'file.ipynb'
        ])
        assert code == 0

        project = Project(dirname)

        command = project.project_file.get_value(['commands', 'test'])
        assert command['notebook'] == 'file.ipynb'
        assert command['env_spec'] == 'foo'
        assert len(command.keys()) == 2

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: 'env_specs:\n  default: {}\n  foo: {}\n'}, check)


def test_add_command_with_supports_http_options(monkeypatch, capsys):
    def check(dirname):
        code = _parse_args_and_run_subcommand([
            'anaconda-project', 'add-command', '--directory', dirname, '--supports-http-options', '--type', 'notebook',
            'test', 'file.ipynb'
        ])
        assert code == 0

        project = Project(dirname)

        command = project.project_file.get_value(['commands', 'test'])
        assert command['notebook'] == 'file.ipynb'
        assert command['env_spec'] == 'default'
        assert command['supports_http_options'] is True
        assert len(command.keys()) == 3

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: 'env_specs:\n  default: {}\n  foo: {}\n'}, check)


def test_add_command_with_no_supports_http_options(monkeypatch, capsys):
    def check(dirname):
        code = _parse_args_and_run_subcommand([
            'anaconda-project', 'add-command', '--directory', dirname, '--no-supports-http-options', '--type',
            'notebook', 'test', 'file.ipynb'
        ])
        assert code == 0

        project = Project(dirname)

        command = project.project_file.get_value(['commands', 'test'])
        assert command['notebook'] == 'file.ipynb'
        assert command['env_spec'] == 'default'
        assert command['supports_http_options'] is False
        assert len(command.keys()) == 3

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: 'env_specs:\n  default: {}\n  foo: {}\n'}, check)


def _test_command_command_project_problem(capsys, monkeypatch, command, append_dir=False):
    def check(dirname):
        if append_dir:
            command.extend(['--directory', dirname])
        code = _parse_args_and_run_subcommand(command)
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert ('variables section contains wrong value type 42,' + ' should be dict or list of requirements\n' +
                'Unable to load the project.\n') in err

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_add_command_project_problem(capsys, monkeypatch):
    _test_command_command_project_problem(
        capsys,
        monkeypatch, ['anaconda-project', 'add-command', '--type', 'notebook', 'test', 'file.ipynb'],
        append_dir=True)


def test_add_command_breaks_project(capsys, monkeypatch):
    def check_problem_add_cmd(dirname):
        args = Args('notebook', 'test', 'file.ipynb', directory=dirname)
        res = main(args)
        assert res == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert (("%s: command 'test' has multiple commands in it, 'notebook' can't go with 'unix'\n" %
                 DEFAULT_PROJECT_FILENAME) + "Unable to add the command.\n") == err

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ("commands:\n  test:\n    unix: foo\n")},
                                                    check_problem_add_cmd)


def test_remove_command_with_project_file_problems(capsys, monkeypatch):
    _test_command_command_project_problem(capsys,
                                          monkeypatch, ['anaconda-project', 'remove-command', 'test'],
                                          append_dir=True)


def test_remove_command(monkeypatch, capsys):
    def check(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'remove-command', 'test', '--directory', dirname])
        assert code == 0

        project = Project(dirname)

        command = project.project_file.get_value(['commands', 'test'])
        assert command is None

        out, err = capsys.readouterr()
        assert out == "Removed the command 'test' from the project.\n"
        assert err == ''

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: 'packages: ["notebook"]\ncommands:\n  test:\n    notebook: file.ipynb\n'}, check)


def test_remove_command_missing(monkeypatch, capsys):
    def check(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'remove-command', 'test', '--directory', dirname])
        assert code == 1

        out, err = capsys.readouterr()
        assert err == "Command: 'test' not found in project file.\n"
        assert out == ''

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ''}, check)


def test_list_commands_with_project_file_problems(capsys, monkeypatch):
    _test_command_command_project_problem(capsys, monkeypatch, ['anaconda-project', 'list-commands'], append_dir=True)


def test_list_commands_empty_project(capsys):
    def check_empty_project(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'list-commands', '--directory', dirname])
        assert code == 0

        out, err = capsys.readouterr()
        assert '' == err
        assert ("No commands found for project: {}\n\n".format(dirname)) == out

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ""}, check_empty_project)


def test_list_commands(capsys):
    def check_empty_project(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'list-commands', '--directory', dirname])
        assert code == 0

        out, err = capsys.readouterr()
        assert '' == err

        expected_out = """
Commands for project: {dirname}

Name          Description
====          ===========
default       Bokeh app test.py
run_notebook  Notebook test.ipynb
""".format(dirname=dirname).strip() + "\n"

        assert expected_out == out

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: ("commands:\n"
                                       "  default:\n"
                                       "    bokeh_app: test.py\n"
                                       "  run_notebook:\n"
                                       "    notebook: test.ipynb\n"
                                       "packages:\n"
                                       " - bokeh\n"
                                       " - notebook\n")
        }, check_empty_project)


def test_list_default_command(capsys):
    def check_empty_project(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'list-default-command', '--directory', dirname])
        assert code == 0

        out, err = capsys.readouterr()
        assert '' == err
        assert out.strip() == 'app'

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: ("commands:\n"
                                       "  app:\n"
                                       "    bokeh_app: test.py\n"
                                       "  0second:\n"
                                       "    notebook: test.ipynb\n"
                                       "packages:\n"
                                       " - bokeh\n"
                                       " - notebook\n")
        }, check_empty_project)


def test_list_default_command_with_project_file_problems(capsys, monkeypatch):
    _test_command_command_project_problem(capsys,
                                          monkeypatch, ['anaconda-project', 'list-default-command'],
                                          append_dir=True)


def test_list_default_command_empty_project(capsys):
    def check_empty_project(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'list-default-command', '--directory', dirname])
        assert code == 0

        out, err = capsys.readouterr()
        assert '' == err
        assert ("No commands found for project: {}\n\n".format(dirname)) == out

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ""}, check_empty_project)
