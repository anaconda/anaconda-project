# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""The ``init`` command creates a new project."""
from __future__ import absolute_import, print_function

import os

from conda_kapsel import project_ops
from conda_kapsel.commands.console_utils import (print_project_problems, console_ask_yes_or_no)


def init_command(project_dir):
    """Initialize a new project.

    Returns:
        Exit code (0 on success)
    """
    if not os.path.exists(project_dir):
        make_directory = console_ask_yes_or_no("Create directory '%s'?" % project_dir, False)
    else:
        make_directory = False

    project = project_ops.create(project_dir, make_directory=make_directory)
    if print_project_problems(project):
        return 1
    else:
        print("Project configuration is in %s" % project.project_file.filename)
        return 0


def main(args):
    """Start the init command and return exit status code."""
    return init_command(args.directory)
