# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""The ``run`` command executes a project, by default without asking questions (fails on missing config)."""
from __future__ import absolute_import, print_function

import sys

from anaconda_project.internal.cli.prepare_with_mode import prepare_with_ui_mode_printing_errors
from anaconda_project.internal.cli.project_load import load_project
from anaconda_project.project_commands import ProjectCommand
from anaconda_project.internal.cli.environment_commands import (create_bootstrap_env, run_on_bootstrap_env)


def _command_from_name(project, command_name):
    command = project.command_for_name(command_name)
    if command is None and command_name is not None:
        # if the command name isn't a configured command name,
        # interpret the command as a notebook or executable.
        attrs = dict(env_spec=project.default_env_spec_name)
        if command_name.lower().endswith(".ipynb"):
            attrs['notebook'] = command_name
        else:
            attrs['args'] = [command_name]

        command = ProjectCommand(name=command_name, attributes=attrs)

    return command


def run_command(project_dir, ui_mode, conda_environment, command_name, extra_command_args):
    """Run the project.

    Returns:
        Does not return if successful.
    """
    project = load_project(project_dir)

    if project.has_bootstrap_env_spec() and not project.is_running_in_bootstrap_env():
        print("Project should be ran by bootstrap env... fixing.")
        create_bootstrap_env(project)
        run_on_bootstrap_env(project)
    else:
        environ = None
        command = _command_from_name(project, command_name)

        result = prepare_with_ui_mode_printing_errors(project,
                                                      ui_mode=ui_mode,
                                                      env_spec_name=conda_environment,
                                                      command=command,
                                                      extra_command_args=extra_command_args,
                                                      environ=environ)

        if result.failed:
            # errors were printed already
            return
        elif result.command_exec_info is None:
            print("No known run command for project %s; try adding a 'commands:' section to anaconda-project.yml" %
                  project_dir,
                  file=sys.stderr)
        else:
            try:

                result.command_exec_info.execvpe()
            except OSError as e:
                print("Failed to execute '%s': %s" % (" ".join(result.command_exec_info.args), e.strerror),
                      file=sys.stderr)


def main(args):
    """Start the run command and return exit status code.."""
    run_command(args.directory, args.mode, args.env_spec, args.command, args.extra_args_for_command)
    # if we returned, we failed to run the command and should have printed an error
    return 1
