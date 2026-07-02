# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Commands related to conda-workspaces (conda.toml) export."""
from __future__ import absolute_import, print_function

from anaconda_project.internal.cli.pixi_commands import _export_workspace
from anaconda_project import project_ops


def export_conda(project_dir, filename, use_default=False, add_current_platform=False):
    """Export the project as a conda.toml file."""
    return _export_workspace(project_dir, filename, use_default, add_current_platform,
                            project_ops.export_conda, 'conda.toml', 'conda-workspaces')


def main_export_conda(args):
    """Start the export-conda command and return exit status code."""
    return export_conda(args.directory, args.filename,
                        use_default=args.use_default,
                        add_current_platform=args.add_current_platform)
