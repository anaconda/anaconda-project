# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function
from functools import partial

import re
import os
import platform
import pytest
import sys

import anaconda_project
from anaconda_project.internal.cli.main import _parse_args_and_run_subcommand

all_subcommands = ('init', 'run', 'prepare', 'clean', 'activate', 'archive', 'unarchive', 'upload', 'download',
                   'dockerize', 'add-variable', 'remove-variable', 'list-variables', 'set-variable', 'unset-variable',
                   'add-download', 'remove-download', 'list-downloads', 'add-service', 'remove-service',
                   'list-services', 'add-env-spec', 'remove-env-spec', 'list-env-specs', 'export-env-spec', 'lock',
                   'unlock', 'update', 'add-packages', 'remove-packages', 'list-packages', 'add-platforms',
                   'remove-platforms', 'list-platforms', 'add-command', 'remove-command', 'list-default-command',
                   'list-commands', 'export-pixi')
all_subcommands_in_curlies = "{" + ",".join(all_subcommands) + "}"
all_subcommands_comma_space = ", ".join(["'" + s + "'" for s in all_subcommands])


def _normalize_whitespace(s):
    """Normalize whitespace for argparse output comparison across Python versions.

    Argparse line wrapping changed in Python 3.11+, causing usage lines to wrap
    differently. This function collapses all whitespace to single spaces so that
    content can be compared regardless of line wrapping differences.
    """
    return re.sub(r'\s+', ' ', s).strip()


def test_main_no_subcommand(capsys):
    code = _parse_args_and_run_subcommand(['project'])

    assert 2 == code

    out, err = capsys.readouterr()
    assert "" == out
    expected_error_msg = ('Must specify a subcommand.\n'
                          'usage: anaconda-project [-h] [-v] [--verbose]\n'
                          '                        %s\n'
                          '                        ...\n') % all_subcommands_in_curlies
    assert _normalize_whitespace(expected_error_msg) == _normalize_whitespace(err)


def test_main_bad_subcommand(capsys):
    code = _parse_args_and_run_subcommand(['project', 'foo'])

    out, err = capsys.readouterr()
    normalized_err = _normalize_whitespace(err)

    # The error message format has changed across Python versions:
    # - Pre-3.9: "invalid choice: 'foo' (choose from 'init', 'run', ...)"
    # - 3.9-3.12: "argument {subcommands}: invalid choice: 'foo' (choose from init, run, ...)"
    # - 3.13+: "argument {subcommands}: invalid choice: 'foo' (choose from 'init', 'run', ...)"
    #
    # Rather than try to match exact formats, verify the key elements are present:
    assert "usage: anaconda-project" in normalized_err
    assert "invalid choice: 'foo'" in normalized_err
    assert "choose from" in normalized_err
    # Verify at least some subcommands are mentioned
    assert "init" in normalized_err
    assert "run" in normalized_err
    assert "list-commands" in normalized_err
    assert "" == out

    assert 2 == code


expected_usage_msg_format = (  # noqa
    'usage: anaconda-project [-h] [-v] [--verbose]\n'
    '                        %s\n'
    '                        ...\n'
    '\n'
    'Actions on projects (runnable projects).\n'
    '\n'
    'positional arguments:\n'
    '  %s\n'
    '                        Sub-commands\n'
    '    init                Initialize a directory with default project\n'
    '                        configuration\n'
    '    run                 Run the project, setting up requirements first\n'
    '    prepare             Set up the project requirements, but does not run the\n'
    '                        project\n'
    '    clean               Removes generated state (stops services, deletes\n'
    '                        environment files, etc)\n'
    '%s'
    '    archive             Create a .zip, .tar.gz, or .tar.bz2 archive with\n'
    '                        project files in it\n'
    '    unarchive           Unpack a .zip, .tar.gz, or .tar.bz2 archive with\n'
    '                        project files in it\n'
    '    upload              Upload the project to Anaconda Cloud\n'
    '    download            Download the project from Anaconda Cloud\n'
    '    dockerize           Build a docker image of the Anaconda Project.\n'
    '    add-variable        Add a required environment variable to the project\n'
    '    remove-variable     Remove an environment variable from the project\n'
    '    list-variables      List all variables on the project\n'
    '    set-variable        Set an environment variable value in anaconda-project-\n'
    '                        local.yml\n'
    '    unset-variable      Unset an environment variable value from anaconda-\n'
    '                        project-local.yml\n'
    '    add-download        Add a URL to be downloaded before running commands\n'
    '    remove-download     Remove a download from the project and from the\n'
    '                        filesystem\n'
    '    list-downloads      List all downloads on the project\n'
    '    add-service         Add a service to be available before running commands\n'
    '    remove-service      Remove a service from the project\n'
    '    list-services       List services present in the project\n'
    '    add-env-spec        Add a new environment spec to the project\n'
    '    remove-env-spec     Remove an environment spec from the project\n'
    '    list-env-specs      List all environment specs for the project\n'
    '    export-env-spec     Save an environment spec as a conda environment file\n'
    '    lock                Lock all packages at their current versions\n'
    '    unlock              Remove locked package versions\n'
    '    update              Update all packages to their latest versions\n'
    '    add-packages        Add packages to one or all project environments\n'
    '    remove-packages     Remove packages from one or all project environments\n'
    '    list-packages       List packages for an environment on the project\n'
    '    add-platforms       Add platforms to one or all project environments\n'
    '    remove-platforms    Remove platforms from one or all project environments\n'
    '    list-platforms      List platforms for an environment on the project\n'
    '    add-command         Add a new command to the project\n'
    '    remove-command      Remove a command from the project\n'
    '    list-default-command\n'
    '                        List only the default command on the project\n'
    '    list-commands       List the commands on the project\n'
    '    export-pixi         Export the project as a pixi.toml file\n'
    '\n'
    'optional arguments:\n'
    '  -h, --help            show this help message and exit\n'
    "  -v, --version         show program's version number and exit\n"
    '  --verbose             show verbose debugging details\n')

activate_help = ('    activate            Set up the project and output shell export commands\n'
                 '                        reflecting the setup\n')

expected_usage_msg = expected_usage_msg_format % (all_subcommands_in_curlies, all_subcommands_in_curlies, activate_help)

expected_usage_msg_without_activate = expected_usage_msg_format % (all_subcommands_in_curlies.replace(
    ",activate", ""), all_subcommands_in_curlies.replace(",activate", ""), "")


def test_main_help(capsys):
    code = _parse_args_and_run_subcommand(['project', '--help'])

    out, err = capsys.readouterr()

    assert "" == err
    normalized_out = _normalize_whitespace(out)
    # Python 3.10+ changed 'optional arguments:' to 'options:'
    assert (_normalize_whitespace(expected_usage_msg) == normalized_out or
            _normalize_whitespace(expected_usage_msg.replace('optional arguments:', 'options:')) == normalized_out)

    assert 0 == code


def test_main_help_via_entry_point(capsys, monkeypatch):
    from anaconda_project.internal.cli.main import main

    monkeypatch.setattr("sys.argv", ['project', '--help'])

    code = main()

    out, err = capsys.readouterr()

    assert "" == err
    normalized_out = _normalize_whitespace(out)
    # Python 3.10+ changed 'optional arguments:' to 'options:'
    assert (_normalize_whitespace(expected_usage_msg_without_activate) == normalized_out or
            _normalize_whitespace(expected_usage_msg_without_activate.replace('optional arguments:', 'options:')) == normalized_out)

    assert 0 == code

    # undo this side effect
    anaconda_project._beta_test_mode = False


def _main_calls_subcommand(monkeypatch, capsys, subcommand):
    def mock_subcommand_main(subcommand, args):
        print("Hi I am subcommand {}".format(subcommand))
        assert args.directory == os.path.realpath(os.path.abspath('MYPROJECT'))
        return 27

    monkeypatch.setattr('anaconda_project.internal.cli.{}.main'.format(subcommand),
                        partial(mock_subcommand_main, subcommand))
    code = _parse_args_and_run_subcommand(['anaconda-project', subcommand, '--directory', 'MYPROJECT'])

    assert 27 == code

    out, err = capsys.readouterr()
    assert ("Hi I am subcommand {}\n".format(subcommand)) == out
    assert "" == err


def test_main_calls_run(monkeypatch, capsys):
    _main_calls_subcommand(monkeypatch, capsys, 'run')


def test_main_calls_prepare(monkeypatch, capsys):
    _main_calls_subcommand(monkeypatch, capsys, 'prepare')


@pytest.mark.skipif(platform.system() != 'Windows', reason='Windows paths are case-insensitive')
def test_main_realpath_directory(monkeypatch):
    def mock_subcommand_main(args):
        return args

    monkeypatch.setattr('anaconda_project.internal.cli.command_commands.main_list', mock_subcommand_main)
    dirname = 'C:\\UsErS\\PRojecT'
    args = _parse_args_and_run_subcommand(['anaconda-project', 'list-commands', '--directory', dirname])
    assert args.directory == os.path.realpath(dirname)


def test_main_when_buggy(capsys, monkeypatch):
    from anaconda_project.internal.cli.main import main

    def mock_is_interactive():
        return True

    monkeypatch.setattr('anaconda_project.internal.cli.console_utils.stdin_is_interactive', mock_is_interactive)

    def mock_main():
        raise AssertionError("It did not work")

    monkeypatch.setattr('anaconda_project.internal.cli.main._main_without_bug_handler', mock_main)
    monkeypatch.setattr("sys.argv", ['anaconda-project'])

    result = main()
    assert result == 1
    out, err = capsys.readouterr()

    assert '' == out
    assert err.startswith("""An unexpected error occurred, most likely a bug in anaconda-project.
    (The error was: AssertionError: It did not work)
Details about the error were saved to """)
    filename = err.split()[-1]
    assert filename.endswith(".txt")
    assert os.path.basename(filename).startswith("bug_details_anaconda-project_")
    assert os.path.isfile(filename)

    os.remove(filename)