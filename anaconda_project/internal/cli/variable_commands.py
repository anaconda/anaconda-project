# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Commands related to setting and unsetting variables."""
from __future__ import absolute_import, print_function

import sys

from anaconda_project.internal.cli.project_load import load_project
from anaconda_project import project_ops
from anaconda_project.internal.cli import console_utils


def add_variables(project_dir, env_spec_name, vars_to_add, default):
    """Add env variables to project file.

    Returns:
        Returns exit code
    """
    if len(vars_to_add) > 1 and default is not None:
        # yapf on P2.7 vs yapf on P3.6 disagree here.
        # yapf: disable
        print("It isn't clear which variable your --default option goes with; "
              "add one variable at a time if using --default.", file=sys.stderr)
        # yapf: enable
        return 1
    project = load_project(project_dir)
    status = project_ops.add_variables(project, env_spec_name, vars_to_add, {vars_to_add[0]: default})
    if status:
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def remove_variables(project_dir, env_spec_name, vars_to_remove):
    """Remove env variable requirements from the project file.

    Returns:
        Returns exit code
    """
    project = load_project(project_dir)
    status = project_ops.remove_variables(project, env_spec_name, vars_to_remove)
    if status:
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def list_variables(project_dir, env_spec_name):
    """List variables present in project."""
    project = load_project(project_dir)
    if console_utils.print_project_problems(project):
        return 1
    print("Variables for project: {}\n".format(project_dir))
    console_utils.print_names_and_descriptions(project.all_variable_requirements(env_spec_name), name_attr='env_var')
    return 0


def set_variables(project_dir, env_spec_name, vars_and_values):
    """Set the given variables to the given values.

    Returns:
        Returns exit code
    """
    fixed_vars = []
    for var in vars_and_values:
        if '=' not in var:
            print("Error: argument '{}' should be in NAME=value format".format(var))
            return 1
        # maxsplit=1 -- no maxsplit keywork in py27
        fixed_vars.append(tuple(var.split('=', 1)))
    project = load_project(project_dir)
    status = project_ops.set_variables(project, env_spec_name, fixed_vars)
    if status:
        print(status.status_description)
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def unset_variables(project_dir, env_spec_name, vars_to_unset):
    """Unset the variables for local project.

    Returns:
        Returns exit code
    """
    project = load_project(project_dir)
    status = project_ops.unset_variables(project, env_spec_name, vars_to_unset)
    if status:
        print(status.status_description)
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def main_add(args):
    """Add variables main."""
    return add_variables(args.directory, args.env_spec, args.vars_to_add, args.default)


def main_remove(args):
    """Remove variables main."""
    return remove_variables(args.directory, args.env_spec, args.vars_to_remove)


def main_list(args):
    """List the project variable names."""
    return list_variables(args.directory, args.env_spec)


def main_set(args):
    """Set the project variables."""
    return set_variables(args.directory, args.env_spec, args.vars_and_values)


def main_unset(args):
    """Unset the project variables."""
    return unset_variables(args.directory, args.env_spec, args.vars_to_unset)
