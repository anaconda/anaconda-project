# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import os
import sys

from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME
from anaconda_project.project_lock_file import DEFAULT_PROJECT_LOCK_FILENAME
from anaconda_project.internal.cli.main import _parse_args_and_run_subcommand
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents


def _monkeypatch_pwd(monkeypatch, dirname):
    from os.path import abspath as real_abspath

    def mock_abspath(path):
        if path == ".":
            return dirname
        else:
            return real_abspath(path)

    monkeypatch.setattr('os.path.abspath', mock_abspath)


def _monkeypatch_isatty(monkeypatch, value):
    def mock_isatty():
        return value

    # python 2 can throw a "readonly" error if you try to patch sys.stdin.isatty itself
    monkeypatch.setattr('anaconda_project.internal.cli.console_utils.stdin_is_interactive', mock_isatty)


def test_init_in_pwd(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)

        code = _parse_args_and_run_subcommand(['anaconda-project', 'init'])
        assert code == 0

        assert os.path.isfile(os.path.join(dirname, DEFAULT_PROJECT_FILENAME))
        assert not os.path.isfile(os.path.join(dirname, DEFAULT_PROJECT_LOCK_FILENAME))

        out, err = capsys.readouterr()
        assert ("Project configuration is in %s\n" % (os.path.join(dirname, DEFAULT_PROJECT_FILENAME))) == out
        assert '' == err

    with_directory_contents(dict(), check)


def test_init_with_anaconda_package(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)

        code = _parse_args_and_run_subcommand(['anaconda-project', 'init', '--with-anaconda-package'])
        assert code == 0

        assert os.path.isfile(os.path.join(dirname, DEFAULT_PROJECT_FILENAME))
        assert not os.path.isfile(os.path.join(dirname, DEFAULT_PROJECT_LOCK_FILENAME))

        out, err = capsys.readouterr()
        assert ("Project configuration is in %s\n" % (os.path.join(dirname, DEFAULT_PROJECT_FILENAME))) == out
        assert '' == err

    with_directory_contents(dict(), check)


def test_init_create_directory(capsys, monkeypatch):
    _monkeypatch_isatty(monkeypatch, True)

    def mock_input_yes(prompt):
        sys.stdout.write(prompt)
        return "yes"

    monkeypatch.setattr('anaconda_project.internal.cli.console_utils._input', mock_input_yes)

    def check(dirname):
        subdir = os.path.join(dirname, "foo")

        code = _parse_args_and_run_subcommand(['anaconda-project', 'init', '--directory', subdir])
        assert code == 0

        assert os.path.isfile(os.path.join(subdir, DEFAULT_PROJECT_FILENAME))
        assert not os.path.isfile(os.path.join(dirname, DEFAULT_PROJECT_LOCK_FILENAME))

        out, err = capsys.readouterr()

        assert ("Create directory '%s'? Project configuration is in %s\n" %
                (subdir, os.path.join(subdir, DEFAULT_PROJECT_FILENAME))) == out
        assert '' == err

    with_directory_contents(dict(), check)


def test_init_do_not_create_directory(capsys, monkeypatch):
    _monkeypatch_isatty(monkeypatch, True)

    def mock_input_no(prompt):
        sys.stdout.write(prompt)
        return "no"

    monkeypatch.setattr('anaconda_project.internal.cli.console_utils._input', mock_input_no)

    def check(dirname):
        subdir = os.path.join(dirname, "foo")

        code = _parse_args_and_run_subcommand(['anaconda-project', 'init', '--directory', subdir])
        assert code == 1

        assert not os.path.isfile(os.path.join(subdir, DEFAULT_PROJECT_FILENAME))
        assert not os.path.isdir(subdir)

        out, err = capsys.readouterr()
        assert ("Create directory '%s'? " % subdir) == out
        assert ("Project directory '%s' does not exist.\nUnable to load the project.\n" % subdir) == err

    with_directory_contents(dict(), check)


def test_init_do_not_create_directory_not_interactive(capsys, monkeypatch):
    _monkeypatch_isatty(monkeypatch, False)

    def mock_input(prompt):
        raise RuntimeError("This should not have been called")

    monkeypatch.setattr('anaconda_project.internal.cli.console_utils._input', mock_input)

    def check(dirname):
        subdir = os.path.join(dirname, "foo")

        code = _parse_args_and_run_subcommand(['anaconda-project', 'init', '--directory', subdir])
        assert code == 1

        assert not os.path.isfile(os.path.join(subdir, DEFAULT_PROJECT_FILENAME))
        assert not os.path.isdir(subdir)

        out, err = capsys.readouterr()
        assert '' == out
        assert ("Project directory '%s' does not exist.\nUnable to load the project.\n" % subdir) == err

    with_directory_contents(dict(), check)


def test_init_create_directory_not_interactive_with_yes(capsys, monkeypatch):
    _monkeypatch_isatty(monkeypatch, False)

    def mock_input(prompt):
        raise RuntimeError("This should not have been called")

    monkeypatch.setattr('anaconda_project.internal.cli.console_utils._input', mock_input)

    def check(dirname):
        subdir = os.path.join(dirname, "foo")

        code = _parse_args_and_run_subcommand(['anaconda-project', 'init', '--yes', '--directory', subdir])
        assert code == 0

        assert os.path.isfile(os.path.join(subdir, DEFAULT_PROJECT_FILENAME))
        assert not os.path.isfile(os.path.join(dirname, DEFAULT_PROJECT_LOCK_FILENAME))
        assert os.path.isdir(subdir)

        out, err = capsys.readouterr()
        assert ("Project configuration is in %s\n" % (os.path.join(subdir, DEFAULT_PROJECT_FILENAME))) == out
        assert '' == err

    with_directory_contents(dict(), check)
