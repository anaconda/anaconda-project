from __future__ import absolute_import, print_function

import pytest
import sys

from project.commands.main import main


def test_main_no_subcommand(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(['project'])

    assert 1 == excinfo.value.code

    out, err = capsys.readouterr()
    assert "" == out
    assert "Please specify a subcommand.\n" == err


def test_main_bad_subcommand(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(['project', 'foo'])

    assert 1 == excinfo.value.code

    out, err = capsys.readouterr()
    assert "" == out
    assert "Unknown subcommand 'foo'.\n" == err


def _main_calls_subcommand(monkeypatch, capsys, subcommand):
    with pytest.raises(SystemExit) as excinfo:

        def mock_subcommand_main(args):
            print("Hi I am subcommand " + repr(args))
            sys.exit(0)

        monkeypatch.setattr('project.commands.' + subcommand + '.main', mock_subcommand_main)
        main(['project', subcommand, 'arg1', 'arg2'])

    assert 0 == excinfo.value.code

    out, err = capsys.readouterr()
    assert ("Hi I am subcommand " + repr([subcommand, 'arg1', 'arg2']) + "\n") == out
    assert "" == err


def test_main_calls_launch(monkeypatch, capsys):
    _main_calls_subcommand(monkeypatch, capsys, 'launch')


def test_main_calls_prepare(monkeypatch, capsys):
    _main_calls_subcommand(monkeypatch, capsys, 'prepare')


def test_main_calls_activate(monkeypatch, capsys):
    _main_calls_subcommand(monkeypatch, capsys, 'activate')
