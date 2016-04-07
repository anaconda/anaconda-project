# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function
from functools import partial

import os

from project.commands.main import _parse_args_and_run_subcommand


def test_main_no_subcommand(capsys):
    code = _parse_args_and_run_subcommand(['project'])

    assert 2 == code

    out, err = capsys.readouterr()
    assert "" == out
    assert 'Must specify a subcommand.\nusage: anaconda-project [-h] {launch,prepare,activate} ...\n' == err


def test_main_bad_subcommand(capsys):
    code = _parse_args_and_run_subcommand(['project', 'foo'])

    out, err = capsys.readouterr()
    expected_error_msg = ("usage: anaconda-project [-h] {launch,prepare,activate} ...\n"
                          "anaconda-project: error: invalid choice: 'foo' "
                          "(choose from 'launch', 'prepare', 'activate')\n")
    assert expected_error_msg == err
    assert "" == out

    assert 2 == code


expected_usage_msg = \
        'usage: anaconda-project [-h] {launch,prepare,activate} ...\n' \
        '\n' \
        'Actions on Anaconda projects.\n' \
        '\n' \
        'positional arguments:\n' \
        '  {launch,prepare,activate}\n' \
        '                        Sub-commands\n' \
        '    launch              Runs the project, setting up requirements first.\n' \
        '    prepare             Sets up project requirements but does not run the\n' \
        '                        project.\n' \
        '    activate            Sets up project and outputs shell export commands\n' \
        '                        reflecting the setup.\n' \
        '\n' \
        'optional arguments:\n' \
        '  -h, --help            show this help message and exit\n'


def test_main_help(capsys):
    code = _parse_args_and_run_subcommand(['project', '--help'])

    out, err = capsys.readouterr()

    assert "" == err
    assert expected_usage_msg == out

    assert 0 == code


def test_main_help_via_entry_point(capsys, monkeypatch):
    from project.commands.main import main

    monkeypatch.setattr("sys.argv", ['project', '--help'])

    code = main()

    out, err = capsys.readouterr()

    assert "" == err
    assert expected_usage_msg == out

    assert 0 == code


def _main_calls_subcommand(monkeypatch, capsys, subcommand):
    def mock_subcommand_main(subcommand, args):
        print("Hi I am subcommand {}".format(subcommand))
        assert args.project_dir == os.path.abspath('MYPROJECT')
        return 27

    monkeypatch.setattr('project.commands.{}.main'.format(subcommand), partial(mock_subcommand_main, subcommand))
    code = _parse_args_and_run_subcommand(['anaconda-project', subcommand, 'MYPROJECT'])

    assert 27 == code

    out, err = capsys.readouterr()
    assert ("Hi I am subcommand {}\n".format(subcommand)) == out
    assert "" == err


def test_main_calls_launch(monkeypatch, capsys):
    _main_calls_subcommand(monkeypatch, capsys, 'launch')


def test_main_calls_prepare(monkeypatch, capsys):
    _main_calls_subcommand(monkeypatch, capsys, 'prepare')


def test_main_calls_activate(monkeypatch, capsys):
    _main_calls_subcommand(monkeypatch, capsys, 'activate')
