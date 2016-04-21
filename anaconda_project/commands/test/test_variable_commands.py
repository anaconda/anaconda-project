# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from anaconda_project.commands.variable_commands import main
from anaconda_project.commands.main import _parse_args_and_run_subcommand
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME

import platform

PLATFORM_ENV_VAR = 'CONDA_DEFAULT_ENV' if platform.system() == 'Windows' else 'CONDA_ENV_PATH'


class Args(object):
    def __init__(self, action, vars_to_add=None, vars_to_remove=None, project='.'):
        self.project = project
        self.action = action
        self.vars_to_add = vars_to_add
        self.vars_to_remove = vars_to_remove


def test_add_variable_command(monkeypatch):

    params = []

    def mock_add_variables(project, _vars):
        params.append(_vars)
        return True

    monkeypatch.setattr('anaconda_project.project_ops.add_variables', mock_add_variables)

    args = Args('add', vars_to_add=['foo=bar', 'baz=qux', 'has_two_equals=foo=bar'])
    res = main(args)
    assert res == 0
    assert [('foo', 'bar'), ('baz', 'qux'), ('has_two_equals', 'foo=bar')] == params[0]


def test_add_variable_project_problem(capsys):
    def check_problem(dirname):
        args = Args('add', vars_to_add=['foo=bar', 'baz=qux'], project=dirname)
        res = main(args)
        assert res == 1

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ("variables:\n" "  42")}, check_problem)

    out, err = capsys.readouterr()
    assert out == ''
    expected_err = ('variables section contains wrong value type 42, should be dict or list of requirements\n'
                    'Unable to load the project.\n')
    assert err == expected_err


def test_add_variable_command_bad(monkeypatch, capsys):

    params = []

    def mock_add_variables(project, _vars):
        params.append(_vars)
        return True

    monkeypatch.setattr('anaconda_project.project_ops.add_variables', mock_add_variables)

    args = Args('add', vars_to_add=['foo=bar', 'baz'])
    res = main(args)
    assert res == 1
    out, err = capsys.readouterr()
    assert "Error: {} doesn't define a name=value pair".format('baz') in out

    assert len(params) == 0


def test_remove_variable_command(monkeypatch):
    params = []

    def check_remove_variable(dirname):
        def mock_remove_variables(project, _vars):
            params.append(_vars)
            return True

        monkeypatch.setattr('anaconda_project.project_ops.remove_variables', mock_remove_variables)
        args = Args('remove', vars_to_remove=['foo', 'baz'], project=dirname)
        res = main(args)
        assert res == 0
        assert len(params) == 1

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ("variables:\n"
                                    "  foo: {default: test}\n"
                                    "  baz: {default: bar}")}, check_remove_variable)


def test_remove_variable_project_problem(monkeypatch):
    def check_problem_remove(dirname):
        args = Args('remove', vars_to_remove=['foo', 'baz'], project=dirname)
        res = main(args)
        assert res == 1

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ("variables:\n" "  foo: true")}, check_problem_remove)


def test_list_variables(capsys):
    def check_list_not_empty(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'list-variables', '--project', dirname])

        assert code == 0
        out, err = capsys.readouterr()
        expected_out = "Variables for project: {}\ntest\ntrain\n{}\n".format(dirname, PLATFORM_ENV_VAR)
        assert out == expected_out

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('downloads:\n'
                                    '  test: http://localhost:8000/test.tgz\n'
                                    '  train: http://localhost:8000/train.tgz\n')}, check_list_not_empty)


def test_list_empty_environments(capsys):
    def check_list_empty(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'list-variables', '--project', dirname])

        assert code == 0
        out, err = capsys.readouterr()
        expected_out = "Variables for project: {}\n{}\n".format(dirname, PLATFORM_ENV_VAR)
        assert out == expected_out

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ''}, check_list_empty)


def test_list_variables_with_project_file_problems(capsys):
    def check(dirname):

        code = _parse_args_and_run_subcommand(['anaconda-project', 'list-variables', '--project', dirname])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert ('variables section contains wrong value type 42,' + ' should be dict or list of requirements\n' +
                'Unable to load the project.\n') == err

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)
