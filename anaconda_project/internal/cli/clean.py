# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""The ``clean`` command removes generated state."""
from __future__ import absolute_import, print_function

from anaconda_project.internal.cli.project_load import load_project
from anaconda_project.prepare import prepare_without_interaction
from anaconda_project.provide import PROVIDE_MODE_CHECK
from anaconda_project.internal.cli import console_utils
import anaconda_project.project_ops as project_ops


def clean_command(project_dir):
    """Clean up generated state.

    Returns:
        exit code
    """
    project = load_project(project_dir)
    # we don't want to print errors during this prepare, clean
    # can proceed even though the prepare fails.
    with project.null_frontend():
        result = prepare_without_interaction(project, mode=PROVIDE_MODE_CHECK)
    status = project_ops.clean(project, result)
    if status:
        print(status.status_description)
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def main(args):
    """Start the clean command and return exit status code."""
    return clean_command(args.directory)
