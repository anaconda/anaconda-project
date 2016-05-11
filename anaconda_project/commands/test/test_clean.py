# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from anaconda_project.commands.main import _parse_args_and_run_subcommand
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME


def test_clean_command_on_empty_project(capsys):
    def check(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'clean', '--project', dirname])
        assert code == 0

        out, err = capsys.readouterr()
        assert 'Cleaned.\n' == out
        assert '' == err

    with_directory_contents(dict(), check)


def test_clean_command_on_invalid_project(capsys):
    def check(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'clean', '--project', dirname])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert ('variables section contains wrong value type 42,' + ' should be dict or list of requirements\n' +
                'Unable to load the project.\n' + 'Failed to clean everything up.\n') == err

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)
