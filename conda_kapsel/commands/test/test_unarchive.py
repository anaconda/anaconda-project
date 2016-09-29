# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from conda_kapsel.commands.main import _parse_args_and_run_subcommand
from conda_kapsel.internal.simple_status import SimpleStatus


def test_unarchive_command(capsys, monkeypatch):
    def mock_unarchive(filename, project_dir, parent_dir=None):
        return SimpleStatus(success=True, description="DESC", logs=['a', 'b'])

    monkeypatch.setattr('conda_kapsel.project_ops.unarchive', mock_unarchive)
    code = _parse_args_and_run_subcommand(['conda-kapsel', 'unarchive', 'foo.tar.gz', 'bar'])
    assert code == 0

    out, err = capsys.readouterr()
    assert 'a\nb\nDESC\n' == out
    assert '' == err


def test_unarchive_command_error(capsys, monkeypatch):
    def mock_unarchive(filename, project_dir, parent_dir=None):
        return SimpleStatus(success=False, description="DESC", logs=['a', 'b'], errors=['c', 'd'])

    monkeypatch.setattr('conda_kapsel.project_ops.unarchive', mock_unarchive)
    code = _parse_args_and_run_subcommand(['conda-kapsel', 'unarchive', 'foo.tar.gz', 'bar'])
    assert code == 1

    out, err = capsys.readouterr()
    assert '' == out
    assert 'a\nb\nc\nd\nDESC\n' == err
