# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""The ``unarchive`` command unpacks an archive of the project."""
from __future__ import absolute_import, print_function

from anaconda_project.internal.cli import console_utils
from anaconda_project.internal.cli.project_load import CliFrontend
import anaconda_project.project_ops as project_ops


def unarchive_command(archive_filename, project_dir):
    """Unpack an archive of the project.

    Returns:
        exit code
    """
    status = project_ops.unarchive(archive_filename, project_dir, frontend=CliFrontend())
    if status:
        print(status.status_description)
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def main(args):
    """Start the unarchive command and return exit status code."""
    return unarchive_command(args.filename, args.directory)
