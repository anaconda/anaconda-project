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
from anaconda_project.commands.console_utils import print_project_problems


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
        fixed_vars.append(tuple(var.split('=', maxsplit=1)))
    project = Project(project_dir)
    if print_project_problems(project):
        return 1
    project_ops.add_variables(project, fixed_vars)
    return 0


def remove_variables(project_dir, vars_to_remove):
    """Unset the variables for local project and changes project file.

    Returns:
        Returns exit code
    """
    project = Project(project_dir)
    if print_project_problems(project):
        return 1
    project_ops.remove_variables(project, vars_to_remove)
    return 0


def main(args):
    """Start the prepare command and return exit status code."""
    if args.action == 'add':
        return add_variables(args.project, args.vars_to_add)
    elif args.action == 'remove':
        return remove_variables(args.project, args.vars_to_remove)
