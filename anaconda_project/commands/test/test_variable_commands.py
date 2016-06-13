# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from anaconda_project.commands.variable_commands import main_add, main_remove
from anaconda_project.commands.main import _parse_args_and_run_subcommand
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.internal.simple_status import SimpleStatus
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME

import platform

PLATFORM_ENV_VAR = 'CONDA_DEFAULT_ENV' if platform.system() == 'Windows' else 'CONDA_ENV_PATH'


class Args(object):
    def __init__(self, vars_to_add=None, vars_to_remove=None, project='.', default=None):
        self.project = project
        self.vars_to_add = vars_to_add
        self.vars_to_remove = vars_to_remove
        self.default = None


def test_add_variable_command(monkeypatch):

    params = []

    def mock_add_variables(project, _vars, defaults):
        params.append(_vars)
        params.append(defaults)
        return True

    monkeypatch.setattr('anaconda_project.project_ops.add_variables', mock_add_variables)

    args = Args(vars_to_add=['foo', 'baz'])
    res = main_add(args)
    assert res == 0
    assert ['foo', 'baz'] == params[0]


def test_add_variable_with_default(monkeypatch):

    params = []

    def mock_add_variables(project, _vars, defaults):
        params.append(_vars)
        params.append(defaults)
        return True

    monkeypatch.setattr('anaconda_project.project_ops.add_variables', mock_add_variables)

    res = _parse_args_and_run_subcommand(['anaconda-project', 'add-variable', '--default', 'bar', 'foo'])
    assert res == 0
    assert [['foo'], dict(foo='bar')] == params


def test_add_two_variables_with_default(monkeypatch, capsys):

    params = []

    def mock_add_variables(project, _vars, defaults):
        params.append(_vars)
        params.append(defaults)
        return True

    monkeypatch.setattr('anaconda_project.project_ops.add_variables', mock_add_variables)

    res = _parse_args_and_run_subcommand(['anaconda-project', 'add-variable', '--default', 'bar', 'foo', 'hello'])
    assert res == 1

    out, err = capsys.readouterr()
    assert out == ''
    expected_err = ("It isn't clear which variable your --default option goes with; " +
                    "add one variable at a time if using --default.\n")
    assert err == expected_err


def test_add_variable_project_problem(capsys):
    def check_problem(dirname):
        args = Args(vars_to_add=['foo', 'baz'], project=dirname)
        res = main_add(args)
        assert res == 1

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ("variables:\n" "  42")}, check_problem)

    out, err = capsys.readouterr()
    assert out == ''
    expected_err = ('variables section contains wrong value type 42, should be dict or list of requirements\n'
                    'Unable to load the project.\n')
    assert err == expected_err


def test_remove_variable_command(monkeypatch):
    params = []

    def check_remove_variable(dirname):
        def mock_remove_variables(project, _vars):
            params.append(_vars)
            return True

        monkeypatch.setattr('anaconda_project.project_ops.remove_variables', mock_remove_variables)
        args = Args(vars_to_remove=['foo', 'baz'], project=dirname)
        res = main_remove(args)
        assert res == 0
        assert len(params) == 1

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ("variables:\n"
                                    "  foo: {default: test}\n"
                                    "  baz: {default: bar}")}, check_remove_variable)


def test_remove_variable_project_problem(monkeypatch):
    def check_problem_remove(dirname):
        args = Args(vars_to_remove=['foo', 'baz'], project=dirname)
        res = main_remove(args)
        assert res == 1

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ("variables:\n" "  foo: true")}, check_problem_remove)


def test_list_variables(capsys):
    def check_list_not_empty(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'list-variables', '--project', dirname])

        assert code == 0
        out, err = capsys.readouterr()
        expected_out = """
Variables for project: {dirname}

Name{space}Description
===={space}===========
{varname}  The project needs a Conda environment containing all required packages.
tes2{space}A downloaded file which is referenced by tes2.
test{space}A downloaded file which is referenced by test.
""".format(dirname=dirname,
           varname=PLATFORM_ENV_VAR,
           space="".ljust(len(PLATFORM_ENV_VAR) - 2)).strip() + "\n"
        assert out == expected_out

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('downloads:\n'
                                    '  test: http://localhost:8000/test.tgz\n'
                                    '  tes2: http://localhost:8000/train.tgz\n')}, check_list_not_empty)


def test_list_variables_with_no_variables(capsys):
    def check_list_empty(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'list-variables', '--project', dirname])

        assert code == 0
        out, err = capsys.readouterr()
        expected_out = """
Variables for project: {dirname}

Name{space}Description
===={space}===========
{varname}  The project needs a Conda environment containing all required packages.
""".format(dirname=dirname,
           varname=PLATFORM_ENV_VAR,
           space="".ljust(len(PLATFORM_ENV_VAR) - 2)).strip() + "\n"
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


def test_set_variables_with_project_file_problems(capsys):
    def check(dirname):

        code = _parse_args_and_run_subcommand(['anaconda-project', 'set-variable', '--project', dirname, 'FOO=bar'])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert ('variables section contains wrong value type 42,' + ' should be dict or list of requirements\n' +
                'Unable to load the project.\n') == err

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_unset_variables_with_project_file_problems(capsys):
    def check(dirname):

        code = _parse_args_and_run_subcommand(['anaconda-project', 'unset-variable', '--project', dirname, 'FOO'])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert ('variables section contains wrong value type 42,' + ' should be dict or list of requirements\n' +
                'Unable to load the project.\n') == err

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_set_variable_command(monkeypatch):

    params = []

    def mock_set_variables(project, _vars):
        params.append(_vars)
        return SimpleStatus(success=True, description="BOO")

    monkeypatch.setattr('anaconda_project.project_ops.set_variables', mock_set_variables)

    def check(dirname):
        res = _parse_args_and_run_subcommand(['anaconda-project', 'set-variable', '--project', dirname, 'foo=bar',
                                              'baz=qux', 'has_two_equals=foo=bar'])
        assert res == 0

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  - foo
  - baz
  - has_two_equals
    """}, check)

    assert [('foo', 'bar'), ('baz', 'qux'), ('has_two_equals', 'foo=bar')] == params[0]


def test_set_variable_command_bad_arg(monkeypatch, capsys):

    params = []

    def mock_set_variables(project, _vars):
        params.append(_vars)
        return SimpleStatus(success=True, description="BOO")

    monkeypatch.setattr('anaconda_project.project_ops.set_variables', mock_set_variables)

    res = _parse_args_and_run_subcommand(['anaconda-project', 'set-variable', 'foo=bar', 'baz'])
    assert res == 1
    out, err = capsys.readouterr()
    assert "Error: argument '{}' should be in NAME=value format".format('baz') in out

    assert len(params) == 0


def test_unset_variable_command(monkeypatch):

    params = []

    def mock_unset_variables(project, _vars):
        params.append(_vars)
        return SimpleStatus(success=True, description="BOO")

    monkeypatch.setattr('anaconda_project.project_ops.unset_variables', mock_unset_variables)

    def check(dirname):
        res = _parse_args_and_run_subcommand(['anaconda-project', 'unset-variable', '--project', dirname, 'foo', 'baz'])
        assert res == 0

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
variables:
  - foo
  - baz
    """}, check)

    assert ['foo', 'baz'] == params[0]
