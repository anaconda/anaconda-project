# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""The ``bundle`` command makes an archive of the project."""
from __future__ import absolute_import, print_function

from anaconda_project.project import Project
from anaconda_project.commands import console_utils
import anaconda_project.project_ops as project_ops


def bundle_command(project_dir, bundle_filename):
    """Make an archive of the project.

    Returns:
        exit code
    """
    project = Project(project_dir)
    status = project_ops.bundle(project, bundle_filename)
    if status:
        for line in status.logs:
            print(line)
        print(status.status_description)
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def main(args):
    """Start the bundle command and return exit status code."""
    return bundle_command(args.project, args.filename)
