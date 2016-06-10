# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function
from functools import partial

import os

import anaconda_project
from anaconda_project.commands.main import _parse_args_and_run_subcommand

all_subcommands = ('init', 'run', 'prepare', 'clean', 'activate', 'bundle', 'upload', 'add-variable', 'remove-variable',
                   'list-variables', 'set-variable', 'unset-variable', 'add-download', 'remove-download',
                   'list-downloads', 'add-service', 'remove-service', 'list-services', 'add-env-spec',
                   'remove-env-spec', 'list-env-specs', 'add-dependencies', 'remove-dependencies', 'list-dependencies',
                   'add-command', 'remove-command', 'list-commands')
all_subcommands_in_curlies = "{" + ",".join(all_subcommands) + "}"
all_subcommands_comma_space = ", ".join(["'" + s + "'" for s in all_subcommands])


def test_main_no_subcommand(capsys):
    code = _parse_args_and_run_subcommand(['project'])

    assert 2 == code

    out, err = capsys.readouterr()
    assert "" == out
    expected_error_msg = ('Must specify a subcommand.\nusage: anaconda-project [-h] [-v]\n'
                          '                        %s\n'
                          '                        ...\n') % all_subcommands_in_curlies
    assert expected_error_msg == err


def test_main_bad_subcommand(capsys):
    code = _parse_args_and_run_subcommand(['project', 'foo'])

    out, err = capsys.readouterr()
    expected_error_msg = ("usage: anaconda-project [-h] [-v]\n"
                          "                        %s\n"
                          "                        ...\nanaconda-project: error: invalid choice: 'foo' "
                          "(choose from %s)\n") % (all_subcommands_in_curlies, all_subcommands_comma_space)
    assert expected_error_msg == err
    assert "" == out

    assert 2 == code


expected_usage_msg = \
        'usage: anaconda-project [-h] [-v]\n' \
        '                        %s\n' \
        '                        ...\n' \
        '\n' \
        'Actions on Anaconda projects.\n' \
        '\n' \
        'positional arguments:\n' \
        '  %s\n' \
        '                        Sub-commands\n' \
        '    init                Initialize a directory with default project\n' \
        '                        configuration\n' \
        '    run                 Run the project, setting up requirements first\n' \
        '    prepare             Set up the project requirements, but does not run the\n' \
        '                        project\n' \
        '    clean               Removes generated state (stops services, deletes\n' \
        '                        environment files, etc)\n' \
        '    activate            Set up the project and output shell export commands\n' \
        '                        reflecting the setup\n' \
        '    bundle              Create a .zip, .tar.gz, or .tar.bz2 archive with\n' \
        '                        project files in it\n'\
        '    upload              Upload the project to Anaconda Cloud\n' \
        '    add-variable        Add an environment variable and add it to the project\n' \
        '                        if not present\n' \
        '    remove-variable     Remove an environment variable and remove it from the\n' \
        '                        project\n' \
        '    list-variables      List all variables on the project\n' \
        '    set-variable        Set an environment variable value in project-local.yml\n'\
        '    unset-variable      Unset an environment variable value from project-\n' \
        '                        local.yml\n' \
        '    add-download        Add a URL to be downloaded before running commands\n' \
        '    remove-download     Remove a download from the project and from the\n' \
        '                        filesystem\n' \
        '    list-downloads      List all downloads on the project\n' \
        '    add-service         Add a service to be available before running commands\n' \
        '    remove-service      Remove a service from the project\n' \
        '    list-services       List services present in the project\n' \
        '    add-env-spec        Add a new environment spec to the project\n' \
        '    remove-env-spec     Remove an environment spec from the project\n' \
        '    list-env-specs      List all environment specs for the project\n' \
        '    add-dependencies    Add packages to one or all project environments\n' \
        '    remove-dependencies\n' \
        '                        Remove packages from one or all project environments\n' \
        '    list-dependencies   List dependencies for an environment on the project\n' \
        '    add-command         Add a new command to the project\n' \
        '    remove-command      Remove a command from the project\n' \
        '    list-commands       List the commands on the project\n' \
        '\n' \
        'optional arguments:\n' \
        '  -h, --help            show this help message and exit\n' \
        "  -v, --version         show program's version number and exit\n"
expected_usage_msg = expected_usage_msg % (all_subcommands_in_curlies, all_subcommands_in_curlies)


def test_main_help(capsys):
    code = _parse_args_and_run_subcommand(['project', '--help'])

    out, err = capsys.readouterr()

    assert "" == err
    assert expected_usage_msg == out

    assert 0 == code


def test_main_help_via_entry_point(capsys, monkeypatch):
    from anaconda_project.commands.main import main

    monkeypatch.setattr("sys.argv", ['project', '--help'])

    code = main()

    out, err = capsys.readouterr()

    assert "" == err
    assert expected_usage_msg == out

    assert 0 == code

    # undo this side effect
    anaconda_project._beta_test_mode = False


def _main_calls_subcommand(monkeypatch, capsys, subcommand):
    def mock_subcommand_main(subcommand, args):
        print("Hi I am subcommand {}".format(subcommand))
        assert args.project == os.path.abspath('MYPROJECT')
        return 27

    monkeypatch.setattr('anaconda_project.commands.{}.main'.format(subcommand), partial(mock_subcommand_main,
                                                                                        subcommand))
    code = _parse_args_and_run_subcommand(['anaconda-project', subcommand, '--project', 'MYPROJECT'])

    assert 27 == code

    out, err = capsys.readouterr()
    assert ("Hi I am subcommand {}\n".format(subcommand)) == out
    assert "" == err


def test_main_calls_run(monkeypatch, capsys):
    _main_calls_subcommand(monkeypatch, capsys, 'run')


def test_main_calls_prepare(monkeypatch, capsys):
    _main_calls_subcommand(monkeypatch, capsys, 'prepare')


def test_main_calls_activate(monkeypatch, capsys):
    _main_calls_subcommand(monkeypatch, capsys, 'activate')
