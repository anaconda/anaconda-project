from __future__ import absolute_import, print_function
from functools import partial

import pytest
import sys

from project.commands.main import main


def test_main_no_subcommand(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(['project'])

    assert 2 == excinfo.value.code

    out, err = capsys.readouterr()
    assert "" == out
    assert err.startswith("usage: Anaconda project tool [-h] {launch,prepare,activate}")


def test_main_bad_subcommand(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(['project', 'foo'])

    out, err = capsys.readouterr()
    expected_error_msg = ("usage: Anaconda project tool [-h] {launch,prepare,activate} ...\n"
                          "Anaconda project tool: error: invalid choice: 'project' "
                          "(choose from 'launch', 'prepare', 'activate')\n")
    assert expected_error_msg == err
    assert "" == out

    assert 2 == excinfo.value.code


def _main_calls_subcommand(monkeypatch, capsys, subcommand):
    with pytest.raises(SystemExit) as excinfo:

        def mock_subcommand_main(subcommand, args):
            print("Hi I am subcommand {} {}".format(subcommand, repr(args)))
            sys.exit(0)

        monkeypatch.setattr('project.commands.{}.main'.format(subcommand), partial(mock_subcommand_main, subcommand))
        main([subcommand, 'arg1'])

    assert 0 == excinfo.value.code

    out, err = capsys.readouterr()
    assert ("Hi I am subcommand {} 'arg1'\n".format(subcommand)) == out
    assert "" == err


def test_main_calls_launch(monkeypatch, capsys):
    _main_calls_subcommand(monkeypatch, capsys, 'launch')


def test_main_calls_prepare(monkeypatch, capsys):
    _main_calls_subcommand(monkeypatch, capsys, 'prepare')


def test_main_calls_activate(monkeypatch, capsys):
    _main_calls_subcommand(monkeypatch, capsys, 'activate')
