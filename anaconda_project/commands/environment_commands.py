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


def add_environment(project_dir, name, packages, channels):
    """Add an item to the downloads section."""
    project = Project(project_dir)
    if print_project_problems(project):
        return 1
    status = project_ops.add_environment(project, name=name, packages=packages, channels=channels)
    if status is None:
        # this is bad because it doesn't explain why
        print("Unable to add environment %s" % name, file=sys.stderr)
        return 1
    elif status:
        print(status.status_description)
        print("Added environment %s to the project file." % name)
        return 0
    else:
        for log in status.logs:
            print(log, file=sys.stderr)
        for error in status.errors:
            print(error, file=sys.stderr)
        print(status.status_description, file=sys.stderr)
        return 1


def main_add(args):
    """Start the add-environment command and return exit status code."""
    return add_environment(args.project, args.name, args.packages, args.channel)
