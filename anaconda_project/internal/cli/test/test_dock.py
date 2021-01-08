# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2020, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from anaconda_project.internal.cli.main import _parse_args_and_run_subcommand
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents_completing_project_file
from anaconda_project.internal.simple_status import SimpleStatus


def _monkeypatch_dock(monkeypatch):
    params = {}

    def mock_dock(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        return SimpleStatus(success=True, description="Yay")

    monkeypatch.setattr('anaconda_project.project_ops.dock', mock_dock)
    return params


def test_dock(capsys, monkeypatch):
    params = _monkeypatch_dock(monkeypatch)

    def check(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'dock'])
        assert code == 0

        out, err = capsys.readouterr()
        assert 'Yay\n' == out
        assert '' == err

        assert params['kwargs']['tag'] is None
        assert params['kwargs']['command'] == 'default'
        assert params['kwargs']['builder_image'] == 'conda/s2i-anaconda-project-ubi7:latest'
        assert params['kwargs']['build_args'] == []

    with_directory_contents_completing_project_file(dict(), check)


def test_dock_tag(capsys, monkeypatch):
    params = _monkeypatch_dock(monkeypatch)

    def check(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'dock', '-t', 'dockme:1'])
        assert code == 0

        out, err = capsys.readouterr()
        assert 'Yay\n' == out
        assert '' == err

        assert params['kwargs']['tag'] == 'dockme:1'

    with_directory_contents_completing_project_file(dict(), check)


def test_dock_command(capsys, monkeypatch):
    params = _monkeypatch_dock(monkeypatch)

    def check(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'dock', '--command', 'other-command'])
        assert code == 0

        out, err = capsys.readouterr()
        assert 'Yay\n' == out
        assert '' == err

        assert params['kwargs']['command'] == 'other-command'

    with_directory_contents_completing_project_file(dict(), check)


def test_dock_build_args(capsys, monkeypatch):
    params = _monkeypatch_dock(monkeypatch)

    def check(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'dock', '--', '-e', 'CMD=other', '--run'])
        assert code == 0

        out, err = capsys.readouterr()
        assert 'Yay\n' == out
        assert '' == err

        assert params['kwargs']['build_args'] == ['-e', 'CMD=other', '--run']

    with_directory_contents_completing_project_file(dict(), check)


def test_dock_builder_image(capsys, monkeypatch):
    params = _monkeypatch_dock(monkeypatch)

    def check(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'dock', '--builder-image', 'custom:latest'])
        assert code == 0

        out, err = capsys.readouterr()
        assert 'Yay\n' == out
        assert '' == err

        assert params['kwargs']['builder_image'] == 'custom:latest'

    with_directory_contents_completing_project_file(dict(), check)
