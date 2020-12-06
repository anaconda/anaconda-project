# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""The ``prepare`` command configures a project to run, asking the user questions if necessary."""
from __future__ import absolute_import, print_function

import anaconda_project.internal.cli.console_utils as console_utils
from anaconda_project.internal.cli.prepare_with_mode import prepare_with_ui_mode_printing_errors
from anaconda_project.internal.cli.project_load import load_project
from anaconda_project.requirements_registry.providers.conda_env import _remove_env_path


def prepare_command(project_dir, ui_mode, conda_environment, command_name, all=False, refresh=False):
    """Configure the project to run.

    Returns:
        Prepare result (can be treated as True on success).
    """
    project = load_project(project_dir)
    project_dir = project.directory_path
    if console_utils.print_project_problems(project):
        return False
    if all:
        specs = project.env_specs
    else:
        envname = 'default' if conda_environment is None else conda_environment
        specs = {envname: project.env_specs[envname]}
    result = []
    for k, v in specs.items():
        if refresh:
            _remove_env_path(v.path(project_dir), project_dir)
        result = prepare_with_ui_mode_printing_errors(project,
                                                      env_spec_name=k,
                                                      ui_mode=ui_mode,
                                                      command_name=command_name)
    return result


def main(args):
    """Start the prepare command and return exit status code."""
    if prepare_command(args.directory, args.mode, args.env_spec, args.command, args.all, args.refresh):
        print("The project is ready to run commands.")
        print("Use `anaconda-project list-commands` to see what's available.")
        return 0
    else:
        return 1
