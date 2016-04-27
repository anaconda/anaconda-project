# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from anaconda_project.commands.main import _parse_args_and_run_subcommand
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME
from anaconda_project.project import Project
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents


class FakeRequirementStatus(object):
    def __init__(self, success, status_description):
        self.status_description = status_description
        self.success = success
        self.logs = ["This is a log message."]
        self.errors = []
        if not success:
            self.errors.append("This is an error message.")

    def __bool__(self):
        return self.success

    def __nonzero__(self):
        return self.success


def _monkeypatch_pwd(monkeypatch, dirname):
    from os.path import abspath as real_abspath

    def mock_abspath(path):
        if path == ".":
            return dirname
        else:
            return real_abspath(path)

    monkeypatch.setattr('os.path.abspath', mock_abspath)


def _monkeypatch_add_download(monkeypatch, result):
    def mock_add_download(*args, **kwargs):
        return result

    monkeypatch.setattr("anaconda_project.project_ops.add_download", mock_add_download)


def test_add_download(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        _monkeypatch_add_download(monkeypatch,
                                  FakeRequirementStatus(success=True,
                                                        status_description='File downloaded.'))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'add-download', 'MYDATA', 'http://localhost:123456'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('File downloaded.\n' + 'Added http://localhost:123456 to the project file.\n') == out
        assert '' == err

    with_directory_contents(dict(), check)


def _test_download_command_with_project_file_problems(capsys, monkeypatch, command):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)

        code = _parse_args_and_run_subcommand(command)
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert ('variables section contains wrong value type 42,' + ' should be dict or list of requirements\n' +
                'Unable to load the project.\n') == err

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_add_download_with_project_file_problems(capsys, monkeypatch):
    _test_download_command_with_project_file_problems(
        capsys, monkeypatch, ['anaconda-project', 'add-download', 'MYDATA', 'http://localhost:123456'])


def test_remove_download_with_project_file_problems(capsys, monkeypatch):
    _test_download_command_with_project_file_problems(capsys, monkeypatch,
                                                      ['anaconda-project', 'remove-download', 'MYDATA'])


def test_remove_download(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)

        code = _parse_args_and_run_subcommand(['anaconda-project', 'remove-download', 'TEST_FILE'])
        project = Project(dirname)
        assert not project.downloads
        assert code == 0

        out, err = capsys.readouterr()
        assert ("Removed file 'foo.tgz' from project.\nRemoved TEST_FILE to the project file.\n") == out
        assert '' == err

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME: "downloads:\n  TEST_FILE: http://localhost/foo.tgz",
            'foo.tgz': 'data here'
        }, check)


def test_remove_download_missing_var(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)

        code = _parse_args_and_run_subcommand(['anaconda-project', 'remove-download', 'TEST_FILE'])
        project = Project(dirname)
        assert not project.downloads
        assert code == 1

        out, err = capsys.readouterr()
        assert ("Download requirement: TEST_FILE not found.\n") == err
        assert '' == out

    with_directory_contents({DEFAULT_PROJECT_FILENAME: 'variables:\n  foo: {default: bar}'}, check)


def test_list_downloads_with_project_file_problems(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)

        code = _parse_args_and_run_subcommand(['anaconda-project', 'list-downloads'])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert ('variables section contains wrong value type 42,' + ' should be dict or list of requirements\n' +
                'Unable to load the project.\n') == err

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_list_empty_downloads(capsys, monkeypatch):
    def check_list_empty(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        code = _parse_args_and_run_subcommand(['anaconda-project', 'list-downloads'])

        assert code == 0
        out, err = capsys.readouterr()
        expected_out = "No downloads found in project.\n"
        assert out == expected_out

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ''}, check_list_empty)


def test_list_downloads(capsys, monkeypatch):
    def check_list_not_empty(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        code = _parse_args_and_run_subcommand(['anaconda-project', 'list-downloads'])
        assert code == 0
        out, err = capsys.readouterr()
        expected_out = "Found these downloads in project:\ntest\ntrain\n"
        assert out == expected_out

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('downloads:\n'
                                    '  test: http://localhost:8000/test.tgz\n'
                                    '  train: http://localhost:8000/train.tgz\n')}, check_list_not_empty)
