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


def _export_workspace(project_dir, filename, use_default, add_current_platform,
                     export_fn, default_filename, format_label):
    """Shared workspace export logic for both pixi and conda-workspaces formats.

    Args:
        project_dir: Directory containing the project.
        filename: Output filename (or 'pixi.toml'/'conda.toml' for project_dir default).
        use_default: Whether to promote a non-default env to 'default'.
        add_current_platform: Whether to add the current platform to the list.
        export_fn: Function to call from project_ops (export_pixi or export_conda).
        default_filename: Default filename if relative ('pixi.toml' or 'conda.toml').
        format_label: Format name for user-facing messages (e.g. 'pixi' or 'conda-workspaces').

    Returns:
        Exit status code (0 on success, 1 on error).
    """
    import os
    project = load_project(project_dir)
    if console_utils.print_project_problems(project):
        return 1
    # Default to writing the manifest file in the project directory
    if filename == default_filename and not os.path.isabs(filename):
        filename = os.path.join(project_dir, filename)
    status = export_fn(project, filename=filename,
                       use_default=use_default,
                       add_current_platform=add_current_platform)
    if status:
        print(status.status_description)
        # When the corresponding flag actually changed something, the
        # status carries the value (rename source / added platform);
        # surface it so the user can see what we did. When the user
        # didn't pass the flag but the project would benefit, recommend
        # the flag instead.
        from anaconda_project.internal.pixi_export import (
            current_platform_addition_target, default_rename_target,
        )
        if use_default and status.default_rename_from:
            print(
                'The "{}" environment has been renamed "default" in the '
                'exported {} specification.'.format(status.default_rename_from, format_label))
        elif not use_default:
            promoted = default_rename_target(project)
            if promoted is not None:
                print(
                    'Recommendation: re-run using the --use-default flag to '
                    'rename the "{}" environment to "default". This will '
                    'simplify the resulting {} specification.'.format(promoted, format_label))
        if add_current_platform and status.current_platform_added:
            print(
                'The current platform "{}" has been added to the platforms '
                'list in the exported {} specification.'
                .format(status.current_platform_added, format_label))
        elif not add_current_platform:
            missing = current_platform_addition_target(project)
            if missing is not None:
                print(
                    'Recommendation: re-run using the --add-current-platform '
                    'flag to add "{}" to the platforms list. {} requires '
                    'the host platform to be declared before it will install '
                    'the environment.'.format(missing, format_label))
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def export_pixi(project_dir, filename, use_default=False, add_current_platform=False):
    """Export the project as a pixi.toml file."""
    return _export_workspace(project_dir, filename, use_default, add_current_platform,
                            project_ops.export_pixi, 'pixi.toml', 'Pixi')


def main_export_pixi(args):
    """Start the export-pixi command and return exit status code."""
    return export_pixi(args.directory, args.filename,
                       use_default=args.use_default,
                       add_current_platform=args.add_current_platform)
