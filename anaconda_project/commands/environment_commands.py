# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Commands related to the environments section."""
from __future__ import absolute_import, print_function

import sys

from anaconda_project.project import Project
from anaconda_project import project_ops
from anaconda_project.commands.console_utils import print_project_problems


def _handle_status(status, success_message, fail_message):
    if status is None:
        # this is bad because it doesn't explain why
        print(fail_message, file=sys.stderr)
        return 1
    elif status:
        print(status.status_description)
        print(success_message)
        return 0
    else:
        for log in status.logs:
            print(log, file=sys.stderr)
        for error in status.errors:
            print(error, file=sys.stderr)
        print(status.status_description, file=sys.stderr)
        return 1


def add_environment(project_dir, name, packages, channels):
    """Add an item to the downloads section."""
    project = Project(project_dir)
    if print_project_problems(project):
        return 1
    status = project_ops.add_environment(project, name=name, packages=packages, channels=channels)
    return _handle_status(status, "Added environment %s to the project file." % name,
                          "Unable to add environment %s." % name)


def add_dependencies(project, environment, packages, channels):
    """Add dependencies to the project."""
    project = Project(project)
    if print_project_problems(project):
        return 1
    status = project_ops.add_dependencies(project, environment=environment, packages=packages, channels=channels)
    package_list = ", ".join(packages)
    if environment is None:
        success_message = "Added dependencies to project file: %s." % (package_list)
    else:
        success_message = "Added dependencies to environment %s in project file: %s." % (environment, package_list)
    return _handle_status(status, success_message, "Unable to add dependencies.")


def main_add(args):
    """Start the add-environment command and return exit status code."""
    return add_environment(args.project, args.name, args.packages, args.channel)


def main_add_dependencies(args):
    """Start the add-dependencies command and return exit status code."""
    return add_dependencies(args.project, args.environment, args.packages, args.channel)
