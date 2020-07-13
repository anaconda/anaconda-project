# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from anaconda_project.internal.cli.variable_commands import main_add, main_remove
from anaconda_project.internal.cli.main import _parse_args_and_run_subcommand
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents_completing_project_file
from anaconda_project.internal.simple_status import SimpleStatus
from anaconda_project.internal import conda_api
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME

PLATFORM_ENV_VAR = conda_api.conda_prefix_variable()


class Args(object):
    def __init__(self, vars_to_add=None, vars_to_remove=None, directory='.', default=None, env_spec=None):
        self.directory = directory
        self.vars_to_add = vars_to_add
        self.vars_to_remove = vars_to_remove
        self.default = None
        self.env_spec = None


def _monkeypatch_add_variables(monkeypatch):
    params = []

    def mock_add_variables(project, env_spec_name, _vars, defaults):
        params.append(env_spec_name)
        params.append(_vars)
        params.append(defaults)
        return True

    monkeypatch.setattr('anaconda_project.project_ops.add_variables', mock_add_variables)

    return params


def test_add_variable_command(monkeypatch):

    params = _monkeypatch_add_variables(monkeypatch)

    args = Args(vars_to_add=['foo', 'baz'])
    res = main_add(args)
    assert res == 0
    assert params[0] is None
    assert ['foo', 'baz'] == params[1]


def test_add_variable_with_default(monkeypatch):

    params = _monkeypatch_add_variables(monkeypatch)

    res = _parse_args_and_run_subcommand(['anaconda-project', 'add-variable', '--default', 'bar', 'foo'])
    assert res == 0
    assert [None, ['foo'], dict(foo='bar')] == params


def test_add_variable_with_env_spec(monkeypatch):

    params = _monkeypatch_add_variables(monkeypatch)

    res = _parse_args_and_run_subcommand(['anaconda-project', 'add-variable', '--env-spec', 'bar', 'foo'])
    assert res == 0
    assert ['bar', ['foo'], dict(foo=None)] == params


def test_add_two_variables_with_default(monkeypatch, capsys):

    params = _monkeypatch_add_variables(monkeypatch)

    res = _parse_args_and_run_subcommand(['anaconda-project', 'add-variable', '--default', 'bar', 'foo', 'hello'])
    assert res == 1
    assert [] == params

    out, err = capsys.readouterr()
    assert out == ''
    expected_err = ("It isn't clear which variable your --default option goes with; " +
                    "add one variable at a time if using --default.\n")
    assert err == expected_err


def test_add_variable_project_problem(capsys):
    def check_problem(dirname):
        args = Args(vars_to_add=['foo', 'baz'], directory=dirname)
        res = main_add(args)
        assert res == 1

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ("variables:\n" "  42")}, check_problem)

    out, err = capsys.readouterr()
    assert out == ''
    expected_err = ('variables section contains wrong value type 42, should be dict or list of requirements\n'
                    'Unable to load the project.\n')
    assert expected_err in err


def _monkeypatch_remove_variables(monkeypatch):
    params = []

    def mock_remove_variables(project, env_spec_name, _vars):
        params.append(env_spec_name)
        params.append(_vars)
        return True

    monkeypatch.setattr('anaconda_project.project_ops.remove_variables', mock_remove_variables)

    return params


def test_remove_variable_command(monkeypatch):

    params = _monkeypatch_remove_variables(monkeypatch)

    def check_remove_variable(dirname):
        args = Args(vars_to_remove=['foo', 'baz'], directory=dirname)
        res = main_remove(args)
        assert res == 0
        assert len(params) == 2

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ("variables:\n"
                                    "  foo: {default: test}\n"
                                    "  baz: {default: bar}")}, check_remove_variable)


def test_remove_variable_project_problem(monkeypatch):
    def check_problem_remove(dirname):
        args = Args(vars_to_remove=['foo', 'baz'], directory=dirname)
        res = main_remove(args)
        assert res == 1

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ("variables:\n"
                                                                                "  foo: true")}, check_problem_remove)


def test_list_variables(capsys):
    def check_list_not_empty(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'list-variables', '--directory', dirname])

        assert code == 0
        out, err = capsys.readouterr()
        expected_out = """
Variables for project: {dirname}

Name{space}Description
===={space}===========
{varname}  The project needs a Conda environment containing all required packages.
tes2{space}A downloaded file which is referenced by tes2.
test{space}A downloaded file which is referenced by test.
""".format(dirname=dirname, varname=PLATFORM_ENV_VAR, space="".ljust(len(PLATFORM_ENV_VAR) - 2)).strip() + "\n"
        assert out == expected_out

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: ('downloads:\n'
                                       '  test: http://localhost:8000/test.tgz\n'
                                       '  tes2: http://localhost:8000/train.tgz\n')
        }, check_list_not_empty)


def test_list_variables_with_no_variables(capsys):
    def check_list_empty(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'list-variables', '--directory', dirname])

        assert code == 0
        out, err = capsys.readouterr()
        expected_out = """
Variables for project: {dirname}

Name{space}Description
===={space}===========
{varname}  The project needs a Conda environment containing all required packages.
""".format(dirname=dirname, varname=PLATFORM_ENV_VAR, space="".ljust(len(PLATFORM_ENV_VAR) - 2)).strip() + "\n"
        assert out == expected_out

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ''}, check_list_empty)


def test_list_variables_with_project_file_problems(capsys):
    def check(dirname):

        code = _parse_args_and_run_subcommand(['anaconda-project', 'list-variables', '--directory', dirname])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert ('variables section contains wrong value type 42,' + ' should be dict or list of requirements\n' +
                'Unable to load the project.\n') in err

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_set_variables_with_project_file_problems(capsys):
    def check(dirname):

        code = _parse_args_and_run_subcommand(['anaconda-project', 'set-variable', '--directory', dirname, 'FOO=bar'])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert ('variables section contains wrong value type 42,' + ' should be dict or list of requirements\n' +
                'Unable to load the project.\n') in err

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_unset_variables_with_project_file_problems(capsys):
    def check(dirname):

        code = _parse_args_and_run_subcommand(['anaconda-project', 'unset-variable', '--directory', dirname, 'FOO'])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert ('variables section contains wrong value type 42,' + ' should be dict or list of requirements\n' +
                'Unable to load the project.\n') in err

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def _monkeypatch_set_variables(monkeypatch):
    params = []

    def mock_set_variables(project, env_spec_name, _vars):
        params.append(env_spec_name)
        params.append(_vars)
        return SimpleStatus(success=True, description="BOO")

    monkeypatch.setattr('anaconda_project.project_ops.set_variables', mock_set_variables)

    return params


def test_set_variable_command(monkeypatch):

    params = _monkeypatch_set_variables(monkeypatch)

    def check(dirname):
        res = _parse_args_and_run_subcommand([
            'anaconda-project', 'set-variable', '--directory', dirname, 'foo=bar', 'baz=qux', 'has_two_equals=foo=bar'
        ])
        assert res == 0

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  - foo
  - baz
  - has_two_equals
    """}, check)

    assert [('foo', 'bar'), ('baz', 'qux'), ('has_two_equals', 'foo=bar')] == params[1]


def test_set_variable_command_with_env_spec(monkeypatch):

    params = _monkeypatch_set_variables(monkeypatch)

    def check(dirname):
        res = _parse_args_and_run_subcommand([
            'anaconda-project', 'set-variable', '--env-spec', 'somespec', '--directory', dirname, 'foo=bar', 'baz=qux',
            'has_two_equals=foo=bar'
        ])
        assert res == 0

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  - foo
  - baz
  - has_two_equals
    """}, check)

    assert 'somespec' == params[0]
    assert [('foo', 'bar'), ('baz', 'qux'), ('has_two_equals', 'foo=bar')] == params[1]


def test_set_variable_command_bad_arg(monkeypatch, capsys):

    params = _monkeypatch_set_variables(monkeypatch)

    res = _parse_args_and_run_subcommand(['anaconda-project', 'set-variable', 'foo=bar', 'baz'])
    assert res == 1
    out, err = capsys.readouterr()
    assert "Error: argument '{}' should be in NAME=value format".format('baz') in out

    assert len(params) == 0


def _monkeypatch_unset_variables(monkeypatch):
    params = []

    def mock_unset_variables(project, env_spec_name, _vars):
        params.append(env_spec_name)
        params.append(_vars)
        return SimpleStatus(success=True, description="BOO")

    monkeypatch.setattr('anaconda_project.project_ops.unset_variables', mock_unset_variables)

    return params


def test_unset_variable_command(monkeypatch):

    params = _monkeypatch_unset_variables(monkeypatch)

    def check(dirname):
        res = _parse_args_and_run_subcommand(
            ['anaconda-project', 'unset-variable', '--directory', dirname, 'foo', 'baz'])
        assert res == 0

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
variables:
  - foo
  - baz
    """}, check)

    assert params[0] is None
    assert ['foo', 'baz'] == params[1]
