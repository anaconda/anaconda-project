# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""The ``upload`` command makes an archive of the project."""
from __future__ import absolute_import, print_function

from anaconda_project.internal.cli.project_load import load_project
from anaconda_project.internal.cli import console_utils
import anaconda_project.project_ops as project_ops


def upload_command(project_dir, private, site, username, token, suffix):
    """Upload project to Anaconda.

    Returns:
        exit code
    """
    project = load_project(project_dir)
    status = project_ops.upload(project, private=private, site=site, username=username, token=token, suffix=suffix)
    if status:
        print(status.status_description)
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def main(args):
    """Start the upload command and return exit status code."""
    return upload_command(args.directory, args.private, args.site, args.user, args.token, args.suffix)
