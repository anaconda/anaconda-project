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
from anaconda_project.commands import console_utils


def _handle_status(status, success_message):
    if status:
        print(status.status_description)
        print(success_message)
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def add_environment(project_dir, name, packages, channels):
    """Add an environment with packages from specified channels to the project."""
    project = Project(project_dir)
    status = project_ops.add_environment(project, name=name, packages=packages, channels=channels)
    return _handle_status(status, "Added environment {} to the project file.".format(name))


def remove_environment(project_dir, name):
    """Remove an environment with packages from the project."""
    project = Project(project_dir)
    status = project_ops.remove_environment(project, name=name)
    return _handle_status(status, "Removed environment {} from the project file.".format(name))


def add_dependencies(project, environment, packages, channels):
    """Add dependencies to the project."""
    project = Project(project)
    status = project_ops.add_dependencies(project, environment=environment, packages=packages, channels=channels)
    package_list = ", ".join(packages)
    if environment is None:
        success_message = "Added dependencies to project file: %s." % (package_list)
    else:
        success_message = "Added dependencies to environment %s in project file: %s." % (environment, package_list)
    return _handle_status(status, success_message)


def remove_dependencies(project, environment, packages):
    """Remove dependencies from the project."""
    project = Project(project)
    status = project_ops.remove_dependencies(project, environment=environment, packages=packages)
    package_list = ", ".join(packages)
    if environment is None:
        success_message = "Removed dependencies from project file: %s." % (package_list)
    else:
        success_message = "Removed dependencies from environment %s in project file: %s." % (environment, package_list)
    return _handle_status(status, success_message)


def list_environments(project_dir):
    """List environments in the project."""
    project = Project(project_dir)
    if console_utils.print_project_problems(project):
        return 1
    print("Environments for project: {}\n".format(project_dir))
    console_utils.print_names_and_descriptions(project.conda_environments.values())
    return 0


def list_dependencies(project_dir, environment):
    """List the dependencies for an environment in the project."""
    project = Project(project_dir)
    if console_utils.print_project_problems(project):
        return 1
    if environment is None:
        environment = project.default_conda_environment_name
    env = project.conda_environments.get(environment, None)
    if env is None:
        print("Project doesn't have an environment called '{}'".format(environment), file=sys.stderr)
        return 1
    print("Dependencies for environment '{}':\n".format(env.name))
    print("\n".join(sorted(env.dependencies)), end='\n\n')
    return 0


def main_add(args):
    """Start the add-environment command and return exit status code."""
    return add_environment(args.project, args.name, args.packages, args.channel)


def main_remove(args):
    """Start the remove-environment command and return exit status code."""
    return remove_environment(args.project, args.name)


def main_add_dependencies(args):
    """Start the add-dependencies command and return exit status code."""
    return add_dependencies(args.project, args.environment, args.packages, args.channel)


def main_remove_dependencies(args):
    """Start the remove-dependencies command and return exit status code."""
    return remove_dependencies(args.project, args.environment, args.packages)


def main_list_environments(args):
    """Start the list environments command and return exit status code."""
    return list_environments(args.project)


def main_list_dependencies(args):
    """Start the list dependencies command and return exit status code."""
    return list_dependencies(args.project, args.environment)
