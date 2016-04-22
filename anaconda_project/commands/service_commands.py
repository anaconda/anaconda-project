# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Commands related to the downloads section."""
from __future__ import absolute_import, print_function

from anaconda_project.project import Project
from anaconda_project import project_ops
from anaconda_project.commands.console_utils import print_status_errors


def add_service(project_dir, service_type, variable_name):
    """Add an item to the services section."""
    project = Project(project_dir)
    status = project_ops.add_service(project, service_type=service_type, variable_name=variable_name)
    if status:
        print(status.status_description)
        print("Added service %s to the project file, its address will be in %s." %
              (status.requirement.service_type, status.requirement.env_var))
        return 0
    else:
        print_status_errors(status)
        return 1


def main_add(args):
    """Start the add-service command and return exit status code."""
    return add_service(args.project, args.service_type, args.variable)
