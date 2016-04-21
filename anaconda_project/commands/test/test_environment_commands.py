# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from anaconda_project.commands.main import _parse_args_and_run_subcommand
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.internal.simple_status import SimpleStatus


def _monkeypatch_pwd(monkeypatch, dirname):
    from os.path import abspath as real_abspath

    def mock_abspath(path):
        if path == ".":
            return dirname
        else:
            return real_abspath(path)

    monkeypatch.setattr('os.path.abspath', mock_abspath)


def _monkeypatch_add_environment(monkeypatch, result):
    params = {}

    def mock_add_environment(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        return result

    monkeypatch.setattr("anaconda_project.project_ops.add_environment", mock_add_environment)

    return params


def _monkeypatch_add_dependencies(monkeypatch, result):
    params = {}

    def mock_add_dependencies(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        return result

    monkeypatch.setattr("anaconda_project.project_ops.add_dependencies", mock_add_dependencies)

    return params


def test_add_environment_no_packages(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        _monkeypatch_add_environment(monkeypatch, SimpleStatus(success=True, description='Environment looks good.'))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'add-environment', '--name', 'foo'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Environment looks good.\n' + 'Added environment foo to the project file.\n') == out
        assert '' == err

    with_directory_contents(dict(), check)


def test_add_environment_with_packages(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        params = _monkeypatch_add_environment(monkeypatch,
                                              SimpleStatus(success=True,
                                                           description='Environment looks good.'))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'add-environment', '--name', 'foo', '--channel',
                                               'c1', '--channel=c2', 'a', 'b'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Environment looks good.\n' + 'Added environment foo to the project file.\n') == out
        assert '' == err

        assert 1 == len(params['args'])
        assert dict(name='foo', packages=['a', 'b'], channels=['c1', 'c2']) == params['kwargs']

    with_directory_contents(dict(), check)


def test_add_environment_fails(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        _monkeypatch_add_environment(monkeypatch,
                                     SimpleStatus(success=False,
                                                  description='Environment variable MYDATA is not set.',
                                                  logs=['This is a log message.'],
                                                  errors=['This is an error message.']))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'add-environment', '--name', 'foo'])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert 'This is a log message.\nThis is an error message.\nEnvironment variable MYDATA is not set.\n' == err

    with_directory_contents(dict(), check)


def test_add_environment_with_project_file_problems(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)

        code = _parse_args_and_run_subcommand(['anaconda-project', 'add-environment', '--name', 'foo'])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert ('variables section contains wrong value type 42,' + ' should be dict or list of requirements\n' +
                'Unable to load the project.\n') == err

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_add_dependencies_with_project_file_problems(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)

        code = _parse_args_and_run_subcommand(['anaconda-project', 'add-dependencies', 'foo'])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert ('variables section contains wrong value type 42,' + ' should be dict or list of requirements\n' +
                'Unable to load the project.\n') == err

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_add_dependencies_to_all_environments(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        params = _monkeypatch_add_dependencies(monkeypatch, SimpleStatus(success=True, description='Installed ok.'))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'add-dependencies', '--channel', 'c1',
                                               '--channel=c2', 'a', 'b'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Installed ok.\n' + 'Added dependencies to project file: a, b.\n') == out
        assert '' == err

        assert 1 == len(params['args'])
        assert dict(environment=None, packages=['a', 'b'], channels=['c1', 'c2']) == params['kwargs']

    with_directory_contents(dict(), check)


def test_add_dependencies_to_specific_environment(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        params = _monkeypatch_add_dependencies(monkeypatch, SimpleStatus(success=True, description='Installed ok.'))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'add-dependencies', '--environment', 'foo',
                                               '--channel', 'c1', '--channel=c2', 'a', 'b'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Installed ok.\n' + 'Added dependencies to environment foo in project file: a, b.\n') == out
        assert '' == err

        assert 1 == len(params['args'])
        assert dict(environment='foo', packages=['a', 'b'], channels=['c1', 'c2']) == params['kwargs']

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
environments:
  foo:
   dependencies:
     - bar
"""}, check)


def test_list_environments(capsys, monkeypatch):
    def check_list_not_empty(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'list-environments', '--project', dirname])

        assert code == 0
        out, err = capsys.readouterr()
        expected_out = "Found these environments in project: {}\nbar\nfoo\n".format(dirname)
        assert out == expected_out

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('environments:\n'
                                    '  foo:\n'
                                    '    dependencies:\n'
                                    '      - bar\n'
                                    '  bar:\n'
                                    '    dependencies:\n'
                                    '      - bar\n')}, check_list_not_empty)


def test_list_empty_environments(capsys, monkeypatch):
    def check_list_empty(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'list-environments', '--project', dirname])

        assert code == 0
        out, err = capsys.readouterr()
        expected_out = "Found these environments in project: {}\ndefault\n".format(dirname)
        assert out == expected_out

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ''}, check_list_empty)


def test_list_environments_with_project_file_problems(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)

        code = _parse_args_and_run_subcommand(['anaconda-project', 'list-environments', '--project', dirname])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert ('variables section contains wrong value type 42,' + ' should be dict or list of requirements\n' +
                'Unable to load the project.\n') == err

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)
