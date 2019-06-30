# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from anaconda_project.internal.cli.main import _parse_args_and_run_subcommand
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents_completing_project_file
from anaconda_project.internal.simple_status import SimpleStatus
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME


def _monkeypatch_upload(monkeypatch):
    params = {}

    def mock_upload(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        args[0].frontend.info('Hello')
        return SimpleStatus(success=True, description="Yay")

    monkeypatch.setattr('anaconda_project.project_ops.upload', mock_upload)
    return params


def test_upload_command_on_empty_project(capsys, monkeypatch):
    _monkeypatch_upload(monkeypatch)

    def check(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'upload', '--directory', dirname])
        assert code == 0

        out, err = capsys.readouterr()
        assert 'Hello\nYay\n' == out
        assert '' == err

    with_directory_contents_completing_project_file(dict(), check)


def test_upload_command_on_invalid_project(capsys):
    def check(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'upload', '--directory', dirname])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert ('variables section contains wrong value type 42,' + ' should be dict or list of requirements\n' +
                'Unable to load the project.\n') in err

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_upload_command_with_token_and_user(capsys, monkeypatch):
    params = _monkeypatch_upload(monkeypatch)

    def check(dirname):
        code = _parse_args_and_run_subcommand(
            ['anaconda-project', 'upload', '--directory', dirname, '--user=foo', '--token=bar'])
        assert code == 0

        out, err = capsys.readouterr()
        assert 'Hello\nYay\n' == out
        assert '' == err

        assert params['kwargs']['token'] == 'bar'
        assert params['kwargs']['username'] == 'foo'

    with_directory_contents_completing_project_file(dict(), check)


def test_upload_command_with_suffix_zip(capsys, monkeypatch):
    params = _monkeypatch_upload(monkeypatch)

    def check(dirname):
        code = _parse_args_and_run_subcommand(
            ['anaconda-project', 'upload', '--directory', dirname, '--suffix', '.zip'])
        assert code == 0

        out, err = capsys.readouterr()
        assert 'Hello\nYay\n' == out
        assert '' == err

        assert params['kwargs']['suffix'] == '.zip'

    with_directory_contents_completing_project_file(dict(), check)


def test_upload_command_with_suffix_tarbz2(capsys, monkeypatch):
    params = _monkeypatch_upload(monkeypatch)

    def check(dirname):
        code = _parse_args_and_run_subcommand(
            ['anaconda-project', 'upload', '--directory', dirname, '--suffix', '.tar.bz2'])
        assert code == 0

        out, err = capsys.readouterr()
        assert 'Hello\nYay\n' == out
        assert '' == err

        assert params['kwargs']['suffix'] == '.tar.bz2'

    with_directory_contents_completing_project_file(dict(), check)


def test_upload_command_with_suffix_targz(capsys, monkeypatch):
    params = _monkeypatch_upload(monkeypatch)

    def check(dirname):
        code = _parse_args_and_run_subcommand(
            ['anaconda-project', 'upload', '--directory', dirname, '--suffix', '.tar.gz'])
        assert code == 0

        out, err = capsys.readouterr()
        assert 'Hello\nYay\n' == out
        assert '' == err

        assert params['kwargs']['suffix'] == '.tar.gz'

    with_directory_contents_completing_project_file(dict(), check)
