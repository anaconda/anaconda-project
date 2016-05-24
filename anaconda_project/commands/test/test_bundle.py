# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import os

from anaconda_project.commands.main import _parse_args_and_run_subcommand
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME


def test_bundle_command_on_empty_project(capsys):
    def check(dirname):
        bundlefile = os.path.join(dirname, "foo.zip")
        code = _parse_args_and_run_subcommand(['anaconda-project', 'bundle', '--project', dirname, bundlefile])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Created project bundle %s\n' % bundlefile) == out
        assert '' == err

    with_directory_contents(dict(), check)


def test_bundle_command_on_simple_project(capsys):
    def check(dirname):
        bundlefile = os.path.join(dirname, "foo.zip")
        code = _parse_args_and_run_subcommand(['anaconda-project', 'bundle', '--project', dirname, bundlefile])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('  added foo.py\nCreated project bundle %s\n' % bundlefile) == out
        assert '' == err

    with_directory_contents({'foo.py': 'print("hello")\n'}, check)


def test_bundle_command_on_invalid_project(capsys):
    def check(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'bundle', '--project', dirname, 'foo.zip'])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert ('variables section contains wrong value type 42,' + ' should be dict or list of requirements\n' +
                'Unable to load the project.\n') == err

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)
