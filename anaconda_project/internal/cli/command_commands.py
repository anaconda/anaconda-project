# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Commands related to the 'commands' section of anaconda-project.yml."""
from __future__ import absolute_import, print_function

import os
import platform
import sys

from anaconda_project.internal.cli.project_load import load_project
from anaconda_project import project_ops
from anaconda_project.internal.cli import console_utils


def _ask_command(command):
    if not console_utils.stdin_is_interactive():
        return None

    if platform.system() == 'Windows':
        other = 'windows'
    else:
        other = 'unix'
    choices = {'b': 'bokeh_app', 'c': other, 'n': 'notebook'}

    while True:
        data = console_utils.console_input("Is `{}` a (B)okeh app, (N)otebook, or (C)ommand line? ".format(command))
        data = data.lower().strip()

        if len(data) == 0 or data[0] not in choices:
            print("Please enter 'b', 'n', or 'c'.")
            print("    A Bokeh app is the project-relative path to a Bokeh script or app directory.")
            print("    A notebook file is the project-relative path to a .ipynb file.")
            print("    A command line is any command you might type at the command prompt.")
            continue

        return choices[data]


def add_command(project_dir, name, command_type, command, env_spec_name, supports_http_options):
    """Add command to anaconda-project.yml.

    Returns:
        int exit code
    """
    project = load_project(project_dir)

    command_as_filename = os.path.join(project.directory_path, command)

    if command_type is None and command.endswith(".ipynb") and os.path.isfile(command_as_filename):
        command_type = 'notebook'

    if command_type is None or command_type == 'ask':
        command_type = _ask_command(name)

    if command_type is None:  # EOF, probably not an interactive console
        print("Specify the --type option to add this command.", file=sys.stderr)
        return 1

    status = project_ops.add_command(project, name, command_type, command, env_spec_name, supports_http_options)
    if not status:
        console_utils.print_status_errors(status)
        return 1
    else:
        print("Added a command '%s' to the project. Run it with `anaconda-project run %s`." % (name, name))
        return 0


def remove_command(project_dir, name):
    """Remove a command from the project.

    Returns:
        int exit code
    """
    project = load_project(project_dir)

    status = project_ops.remove_command(project, name)
    if not status:
        console_utils.print_status_errors(status)
        return 1
    else:
        print("Removed the command '{}' from the project.".format(name))
        return 0


def list_commands(project_dir):
    """List the commands on the project.

    Returns:
        int exit code
    """
    project = load_project(project_dir)
    if console_utils.print_project_problems(project):
        return 1

    if project.commands:
        print("Commands for project: {}\n".format(project_dir))
        console_utils.print_names_and_descriptions(project.commands.values())
    else:
        print("No commands found for project: {}\n".format(project_dir))
    return 0


def list_default_command(project_dir):
    """List only the default command on the project.

    Returns:
        int exit code
    """
    project = load_project(project_dir)
    if console_utils.print_project_problems(project):
        return 1

    if project.commands:
        # print("Commands for project: {}\n".format(project_dir))
        # console_utils.print_names_and_descriptions(project.commands.values())
        print(project.default_command.name)
    else:
        print("No commands found for project: {}\n".format(project_dir))
    return 0


def main(args):
    """Submit the add command with args and returns exit code."""
    return add_command(args.directory, args.name, args.type, args.command, args.env_spec, args.supports_http_options)


def main_remove(args):
    """Submit the remove command with args and returns exit code."""
    return remove_command(args.directory, args.name)


def main_list(args):
    """Start the list command with args and return exit code."""
    return list_commands(args.directory)


def main_default(args):
    """Start the list default command with args and return exit code."""
    return list_default_command(args.directory)
