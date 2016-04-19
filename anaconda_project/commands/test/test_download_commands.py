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


def test_add_download_fails(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        _monkeypatch_add_download(monkeypatch,
                                  FakeRequirementStatus(success=False,
                                                        status_description='Environment variable MYDATA is not set.'))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'add-download', 'MYDATA', 'http://localhost:123456'])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert 'This is a log message.\nThis is an error message.\nEnvironment variable MYDATA is not set.\n' == err

    with_directory_contents(dict(), check)


def test_add_download_with_project_file_problems(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)

        code = _parse_args_and_run_subcommand(['anaconda-project', 'add-download', 'MYDATA', 'http://localhost:123456'])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert ('variables section contains wrong value type 42,' + ' should be dict or list of requirements\n' +
                'Unable to load the project.\n') == err

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)
