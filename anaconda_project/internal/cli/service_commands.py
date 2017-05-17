# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Commands related to the downloads section."""
from __future__ import absolute_import, print_function

from anaconda_project.internal.cli.project_load import load_project
from anaconda_project import project_ops
from anaconda_project.internal.cli import console_utils
from anaconda_project.prepare import prepare_without_interaction
from anaconda_project.provide import PROVIDE_MODE_CHECK


def add_service(project_dir, service_type, variable_name):
    """Add an item to the services section."""
    project = load_project(project_dir)
    status = project_ops.add_service(project, service_type=service_type, variable_name=variable_name)
    if status:
        print(status.status_description)
        print("Added service %s to the project file, its address will be in %s." %
              (status.requirement.service_type, status.requirement.env_var))
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def remove_service(project_dir, variable_name):
    """Remove an item from the services section."""
    project = load_project(project_dir)
    result = prepare_without_interaction(project, mode=PROVIDE_MODE_CHECK)
    status = project_ops.remove_service(project, result, variable_name=variable_name)
    if status:
        print(status.status_description)
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def list_services(project_dir):
    """List the services listed on the project."""
    project = load_project(project_dir)
    if console_utils.print_project_problems(project):
        return 1

    if project.services:
        print("Services for project: {}\n".format(project_dir))
        console_utils.print_names_and_descriptions(project.service_requirements, name_attr='title')
    else:
        print("No services found for project: {}".format(project_dir))
    return 0


def main_add(args):
    """Start the add-service command and return exit status code."""
    return add_service(args.directory, args.service_type, args.variable)


def main_remove(args):
    """Start the remove-service command and return exit status code."""
    return remove_service(args.directory, args.variable)


def main_list(args):
    """Start the list the services command and return exit status code."""
    return list_services(args.directory)
