# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Commands related to setting and unsetting variables."""
from __future__ import absolute_import, print_function

from anaconda_project.project import Project
from anaconda_project import project_ops
from anaconda_project.commands import console_utils


def ask_command(command):
    """Prompt user to enter command type.

    Returns:
        command_type string: choice of 'bokeh_app', 'python', 'shell', 'notebook'
    """
    while True:
        try:
            data = console_utils.console_input(
                ("Is `{}` a (B)okeh app, (N)otebook, (P)ython script, or (O)ther executable file?\n"
                 "(enter 'b', 'p', 'n', or 'o'): ").format(command))
        except KeyboardInterrupt:
            print("\nCanceling\n")
            return None
        data = data.lower().strip()
        if data not in ('b', 'p', 'o', 'n'):
            print("Invalid choice! Please choose between (B)okeh app, (N)otebook, (P)ython script, or (O)ther")
            continue
        choices = {'b': 'bokeh_app', 'p': 'python', 'o': 'shell', 'n': 'notebook'}
        return choices[data]


def add_command(project_dir, command_type, name, command):
    """Add command to project.yml.

    Returns:
        int exit code
    """
    project = Project(project_dir)
    if console_utils.print_project_problems(project):
        return 1
    if command_type is None or command_type == 'ask' and console_utils.stdin_is_interactive():
        command_type = ask_command(name)

    if command_type is None:  # keyboard interrupted
        return 1

    project_ops.add_command(project, command_type, name, command)
    return 0


def main(args):
    """Submit the add command with args and returns exit code."""
    return add_command(args.project, args.type, args.name, args.command)
