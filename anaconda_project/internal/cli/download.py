# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2019, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""The ``download`` command retrieves a project archive from anaconda.org."""
from __future__ import absolute_import, print_function

from anaconda_project.internal.cli import console_utils
import anaconda_project.project_ops as project_ops


def download_command(
    project,
    unpack,
    parent_dir,
    site,
    username,
    token,
):
    """Download project from Anaconda Cloud.

    Returns:
        exit code
    """
    status = project_ops.download(project,
                                  unpack=unpack,
                                  parent_dir=parent_dir,
                                  site=site,
                                  username=username,
                                  token=token)
    if status:
        print(status.status_description)
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def main(args):
    """Start the upload command and return exit status code."""
    return download_command(args.project, not args.no_unpack, args.parent_dir, args.site, args.user, args.token)
