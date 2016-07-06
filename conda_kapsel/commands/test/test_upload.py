# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from conda_kapsel.commands.main import _parse_args_and_run_subcommand
from conda_kapsel.internal.test.tmpfile_utils import with_directory_contents
from conda_kapsel.internal.simple_status import SimpleStatus
from conda_kapsel.project_file import DEFAULT_PROJECT_FILENAME


def _monkeypatch_upload(monkeypatch):
    params = {}

    def mock_upload(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        return SimpleStatus(success=True, description="Yay", logs=['Hello'])

    monkeypatch.setattr('conda_kapsel.project_ops.upload', mock_upload)
    return params


def test_upload_command_on_empty_project(capsys, monkeypatch):
    _monkeypatch_upload(monkeypatch)

    def check(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'upload', '--project', dirname])
        assert code == 0

        out, err = capsys.readouterr()
        assert 'Hello\nYay\n' == out
        assert '' == err

    with_directory_contents(dict(), check)


def test_upload_command_on_invalid_project(capsys):
    def check(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'upload', '--project', dirname])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert ('variables section contains wrong value type 42,' + ' should be dict or list of requirements\n' +
                'Unable to load the project.\n') == err

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_upload_command_with_token_and_user(capsys, monkeypatch):
    params = _monkeypatch_upload(monkeypatch)

    def check(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'upload', '--project', dirname, '--user=foo',
                                               '--token=bar'])
        assert code == 0

        out, err = capsys.readouterr()
        assert 'Hello\nYay\n' == out
        assert '' == err

        assert params['kwargs']['token'] == 'bar'
        assert params['kwargs']['username'] == 'foo'

    with_directory_contents(dict(), check)
