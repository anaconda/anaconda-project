# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""The ``archive`` command makes an archive of the project."""
from __future__ import absolute_import, print_function

from anaconda_project.internal.cli.project_load import load_project
from anaconda_project.internal.cli import console_utils
import anaconda_project.project_ops as project_ops


def archive_command(project_dir, archive_filename):
    """Make an archive of the project.

    Returns:
        exit code
    """
    project = load_project(project_dir)
    status = project_ops.archive(project, archive_filename)
    if status:
        print(status.status_description)
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def main(args):
    """Start the archive command and return exit status code."""
    return archive_command(args.directory, args.filename)
