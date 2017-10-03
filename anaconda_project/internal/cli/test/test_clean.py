# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from anaconda_project.internal.cli.main import _parse_args_and_run_subcommand
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents_completing_project_file
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME


def test_clean_command_on_empty_project(capsys):
    def check(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'clean', '--directory', dirname])
        assert code == 0

        out, err = capsys.readouterr()
        assert "Nothing to clean up for environment 'default'.\nCleaned.\n" == out
        assert '' == err

    with_directory_contents_completing_project_file(dict(), check)


def test_clean_command_on_invalid_project(capsys):
    def check(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'clean', '--directory', dirname])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert ('variables section contains wrong value type 42,' + ' should be dict or list of requirements\n' +
                'Unable to load the project.\n' + 'Failed to clean everything up.\n') in err

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)
