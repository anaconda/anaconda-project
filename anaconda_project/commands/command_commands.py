# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Commands related to the 'commands' section of project.yml."""
from __future__ import absolute_import, print_function

import os
import platform
import sys

from anaconda_project.project import Project
from anaconda_project import project_ops
from anaconda_project.commands import console_utils


def _ask_command(command):
    if platform.system() == 'Windows':
        other = 'windows'
    else:
        other = 'shell'
    choices = {'b': 'bokeh_app', 'c': other, 'n': 'notebook'}

    while True:
        try:
            data = console_utils.console_input("Is `{}` a (B)okeh app, (N)otebook, or (C)ommand line? ".format(command))
        except KeyboardInterrupt:
            print("\nCanceling\n")
            return None
        data = data.lower().strip()

        if len(data) == 0 or data[0] not in choices:
            print("Please enter 'b', 'n', or 'c'.")
            print("    A Bokeh app is the project-relative path to a Bokeh script or app directory.")
            print("    A notebook file is the project-relative path to a .ipynb file.")
            print("    A command line is any command you might type at the command prompt.")
            continue

        return choices[data]


def add_command(project_dir, command_type, name, command):
    """Add command to project.yml.

    Returns:
        int exit code
    """
    project = Project(project_dir)
    if console_utils.print_project_problems(project):
        return 1

    command_as_filename = os.path.join(project.directory_path, command)

    if command_type is None and command.endswith(".ipynb") and os.path.isfile(command_as_filename):
        command_type = 'notebook'

    if command_type is None or command_type == 'ask' and console_utils.stdin_is_interactive():
        command_type = _ask_command(name)

    if command_type is None:  # keyboard interrupted
        return 1

    problems = project_ops.add_command(project, command_type, name, command)
    if problems is not None:
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1
    else:
        print("Added a command '%s' to the project. Run it with `anaconda-project launch --command %s`." % (name, name))
        return 0


def main(args):
    """Submit the add command with args and returns exit code."""
    return add_command(args.project, args.type, args.name, args.command)
