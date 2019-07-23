# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2019, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from anaconda_project.internal.cli.main import _parse_args_and_run_subcommand
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents_completing_project_file
from anaconda_project.internal.simple_status import SimpleStatus


def _monkeypatch_download(monkeypatch):
    params = {}

    def mock_download(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        return SimpleStatus(success=True, description="Yay")

    monkeypatch.setattr('anaconda_project.project_ops.download', mock_download)
    return params


def test_download(capsys, monkeypatch):
    _monkeypatch_download(monkeypatch)

    def check(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'download', 'fake_user/fake_project'])
        assert code == 0

        out, err = capsys.readouterr()
        assert 'Yay\n' == out
        assert '' == err

    with_directory_contents_completing_project_file(dict(), check)


def test_download_no_username(capsys, monkeypatch):
    _monkeypatch_download(monkeypatch)

    def check(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'download', 'fake_project'])
        assert code == 0

        out, err = capsys.readouterr()
        assert 'Yay\n' == out
        assert '' == err

    with_directory_contents_completing_project_file(dict(), check)


def test_download_no_unpack(capsys, monkeypatch):
    params = _monkeypatch_download(monkeypatch)

    def check(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'download', 'fake_user/fake_project', '--no-unpack'])
        assert code == 0

        out, err = capsys.readouterr()
        assert 'Yay\n' == out
        assert '' == err

        assert not params['kwargs']['unpack']

    with_directory_contents_completing_project_file(dict(), check)


def test_download_parent_dir(capsys, monkeypatch):
    params = _monkeypatch_download(monkeypatch)

    def check(dirname):
        code = _parse_args_and_run_subcommand(
            ['anaconda-project', 'download', 'fake_user/fake_project', '--parent_dir', '.'])
        assert code == 0

        out, err = capsys.readouterr()
        assert 'Yay\n' == out
        assert '' == err

        assert params['kwargs']['parent_dir'] == '.'

    with_directory_contents_completing_project_file(dict(), check)
