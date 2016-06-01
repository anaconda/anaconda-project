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


def add_variables(project_dir, vars_to_add):
    """Change default env variables for local project and change project file.

    Returns:
        Returns exit code
    """
    fixed_vars = []
    for var in vars_to_add:
        if '=' not in var:
            print("Error: {} doesn't define a name=value pair".format(var))
            return 1
        # maxsplit=1 -- no maxplist keywork in py27
        fixed_vars.append(tuple(var.split('=', 1)))
    project = Project(project_dir)
    status = project_ops.add_variables(project, fixed_vars)
    if status:
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def remove_variables(project_dir, vars_to_remove):
    """Unset the variables for local project and changes project file.

    Returns:
        Returns exit code
    """
    project = Project(project_dir)
    status = project_ops.remove_variables(project, vars_to_remove)
    if status:
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def list_variables(project_dir):
    """List variables present in project."""
    project = Project(project_dir)
    if console_utils.print_project_problems(project):
        return 1
    print("Variables for project: {}\n".format(project_dir))
    console_utils.print_names_and_descriptions(project.all_variable_requirements, name_attr='env_var')
    return 0


def main(args):
    """Submit the action to alter the variables in project."""
    if args.action == 'add':
        return add_variables(args.project, args.vars_to_add)
    elif args.action == 'remove':
        return remove_variables(args.project, args.vars_to_remove)


def main_list(args):
    """List the project variable names."""
    return list_variables(args.project)
