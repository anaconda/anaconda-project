# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Commands related to pixi export."""
from __future__ import absolute_import, print_function

from anaconda_project.internal.cli.project_load import load_project
from anaconda_project.internal.cli import console_utils
from anaconda_project import project_ops


def export_pixi(project_dir, filename):
    """Export the project as a pixi.toml file."""
    import os
    project = load_project(project_dir)
    if console_utils.print_project_problems(project):
        return 1
    # Default to writing pixi.toml in the project directory
    if filename == 'pixi.toml' and not os.path.isabs(filename):
        filename = os.path.join(project_dir, filename)
    status = project_ops.export_pixi(project, filename=filename)
    if status:
        print(status.status_description)
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def main_export_pixi(args):
    """Start the export-pixi command and return exit status code."""
    return export_pixi(args.directory, args.filename)
