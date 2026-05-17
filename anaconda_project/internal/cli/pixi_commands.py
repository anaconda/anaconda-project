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


def export_pixi(project_dir, filename, use_default=False):
    """Export the project as a pixi.toml file."""
    import os
    project = load_project(project_dir)
    if console_utils.print_project_problems(project):
        return 1
    # Default to writing pixi.toml in the project directory
    if filename == 'pixi.toml' and not os.path.isabs(filename):
        filename = os.path.join(project_dir, filename)
    status = project_ops.export_pixi(project, filename=filename, use_default=use_default)
    if status:
        print(status.status_description)
        # When --use-default actually promoted an env, the status carries
        # the original name in default_rename_from; surface it so the user
        # can see what we did. When the user didn't pass the flag but the
        # project would benefit, recommend it.
        if use_default and status.default_rename_from:
            print(
                'The "{}" environment has been renamed "default" in the '
                'exported Pixi specification.'.format(status.default_rename_from))
        elif not use_default:
            from anaconda_project.internal.pixi_export import default_rename_target
            promoted = default_rename_target(project)
            if promoted is not None:
                print(
                    'Recommendation: re-run using the --use-default flag to '
                    'rename the "{}" environment to "default". This will '
                    'simplify the resulting Pixi specification.'.format(promoted))
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def main_export_pixi(args):
    """Start the export-pixi command and return exit status code."""
    return export_pixi(args.directory, args.filename, use_default=args.use_default)
