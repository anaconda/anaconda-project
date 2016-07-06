# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""The ``prepare`` command configures a project to run, asking the user questions if necessary."""
from __future__ import absolute_import, print_function

from conda_kapsel.commands.prepare_with_mode import prepare_with_ui_mode_printing_errors
from conda_kapsel.project import Project


def prepare_command(project_dir, ui_mode, conda_environment):
    """Configure the project to run.

    Returns:
        Prepare result (can be treated as True on success).
    """
    project = Project(project_dir)
    result = prepare_with_ui_mode_printing_errors(project, env_spec_name=conda_environment, ui_mode=ui_mode)

    return result


def main(args):
    """Start the prepare command and return exit status code."""
    if prepare_command(args.directory, args.mode, args.env_spec):
        print("The project is ready to run commands.")
        print("Use `conda-kapsel list-commands` to see what's available.")
        return 0
    else:
        return 1
