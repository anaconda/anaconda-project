# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""The ``unarchive`` command unpacks an archive of the project."""
from __future__ import absolute_import, print_function

from anaconda_project.internal.cli import console_utils
import anaconda_project.project_ops as project_ops


def unarchive_command(archive_filename, project_dir):
    """Unpack an archive of the project.

    Returns:
        exit code
    """
    status = project_ops.unarchive(archive_filename, project_dir)
    if status:
        for line in status.logs:
            print(line)
        print(status.status_description)
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def main(args):
    """Start the unarchive command and return exit status code."""
    return unarchive_command(args.filename, args.directory)
