# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from anaconda_project.commands.main import _parse_args_and_run_subcommand
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME
from anaconda_project.plugins.requirements.redis import RedisRequirement
from anaconda_project.plugins.registry import PluginRegistry
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.internal.simple_status import SimpleStatus
from anaconda_project.local_state_file import LocalStateFile


def _monkeypatch_pwd(monkeypatch, dirname):
    from os.path import abspath as real_abspath

    def mock_abspath(path):
        if path == ".":
            return dirname
        else:
            return real_abspath(path)

    monkeypatch.setattr('os.path.abspath', mock_abspath)


def _monkeypatch_add_service(monkeypatch, result):
    def mock_add_service(*args, **kwargs):
        return result

    monkeypatch.setattr("anaconda_project.project_ops.add_service", mock_add_service)


def test_add_service(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)

        status = SimpleStatus(success=True, description='Service added.')
        status.requirement = RedisRequirement(PluginRegistry(), env_var='REDIS_URL', options=dict(type='redis'))

        _monkeypatch_add_service(monkeypatch, status)

        code = _parse_args_and_run_subcommand(['anaconda-project', 'add-service', 'redis'])
        assert code == 0

        out, err = capsys.readouterr()
        assert (
            'Service added.\n' + 'Added service redis to the project file, its address will be in REDIS_URL.\n') == out
        assert '' == err

    with_directory_contents(dict(), check)


def test_add_service_fails(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        _monkeypatch_add_service(monkeypatch, SimpleStatus(success=False, description='Service add FAIL.'))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'add-service', 'redis'])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert 'Service add FAIL.\n' == err

    with_directory_contents(dict(), check)


def test_remove_service(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        local_state = LocalStateFile.load_for_directory(dirname)
        local_state.set_service_run_state('ABC', {'shutdown_commands': [['echo', '"shutting down ABC"']]})
        local_state.set_service_run_state('TEST', {'shutdown_commands': [['echo', '"shutting down TEST"']]})
        local_state.save()

        code = _parse_args_and_run_subcommand(['anaconda-project', 'remove-service', '--variable', 'TEST'])
        assert code == 0

        out, err = capsys.readouterr()
        assert '' == err
        expected_out = ('Running [\'echo\', \'"shutting down TEST"\']\n'
                        '  exited with 0\n'
                        'Removed service requirement referenced by \'TEST\'\n'
                        'Removed service TEST from the project file.\n')
        assert expected_out == out

    with_directory_contents({DEFAULT_PROJECT_FILENAME: 'services:\n  ABC: redis\n  TEST: redis'}, check)


def test_remove_service_missing_variable(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)

        code = _parse_args_and_run_subcommand(['anaconda-project', 'remove-service', '--variable', 'TEST'])
        assert code == 1

        out, err = capsys.readouterr()

        assert "Service requirement referenced by 'TEST' not found\n" == err
        assert '' == out

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ''}, check)


def _test_service_command_with_project_file_problems(capsys, monkeypatch, command):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)

        code = _parse_args_and_run_subcommand(command)
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert ('variables section contains wrong value type 42,' + ' should be dict or list of requirements\n' +
                'Unable to load the project.\n') == err

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_add_service_with_project_file_problems(capsys, monkeypatch):
    _test_service_command_with_project_file_problems(capsys, monkeypatch, ['anaconda-project', 'add-service', 'redis'])


def test_remove_service_with_project_file_problems(capsys, monkeypatch):
    _test_service_command_with_project_file_problems(capsys, monkeypatch,
                                                     ['anaconda-project', 'remove-service', '--variable', 'TEST'])


def test_list_service_with_project_file_problems(capsys, monkeypatch):
    _test_service_command_with_project_file_problems(capsys, monkeypatch, ['anaconda-project', 'list-services'])


def test_list_service(capsys, monkeypatch):
    def check_list(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        code = _parse_args_and_run_subcommand(['anaconda-project', 'list-services'])
        assert code == 0

        out, err = capsys.readouterr()
        assert err == ''
        assert out == "Services for project: {}\n\n{}\n".format(dirname, 'REDIS_URL')

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "services:\n  REDIS_URL: redis\n"}, check_list)


def test_list_service_with_empty_project(capsys, monkeypatch):
    def check_empty(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        code = _parse_args_and_run_subcommand(['anaconda-project', 'list-services'])
        assert code == 0

        out, err = capsys.readouterr()
        assert err == ''
        assert out == "No services found for project: {}\n".format(dirname)

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ""}, check_empty)
