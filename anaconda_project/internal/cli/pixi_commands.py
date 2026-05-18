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


def export_pixi(project_dir, filename, use_default=False, add_current_platform=False):
    """Export the project as a pixi.toml file."""
    import os
    project = load_project(project_dir)
    if console_utils.print_project_problems(project):
        return 1
    # Default to writing pixi.toml in the project directory
    if filename == 'pixi.toml' and not os.path.isabs(filename):
        filename = os.path.join(project_dir, filename)
    status = project_ops.export_pixi(project, filename=filename,
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
                'exported Pixi specification.'.format(status.default_rename_from))
        elif not use_default:
            promoted = default_rename_target(project)
            if promoted is not None:
                print(
                    'Recommendation: re-run using the --use-default flag to '
                    'rename the "{}" environment to "default". This will '
                    'simplify the resulting Pixi specification.'.format(promoted))
        if add_current_platform and status.current_platform_added:
            print(
                'The current platform "{}" has been added to the platforms '
                'list in the exported Pixi specification.'
                .format(status.current_platform_added))
        elif not add_current_platform:
            missing = current_platform_addition_target(project)
            if missing is not None:
                print(
                    'Recommendation: re-run using the --add-current-platform '
                    'flag to add "{}" to the platforms list. Pixi requires '
                    'the host platform to be declared before it will install '
                    'the environment.'.format(missing))
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def main_export_pixi(args):
    """Start the export-pixi command and return exit status code."""
    return export_pixi(args.directory, args.filename,
                       use_default=args.use_default,
                       add_current_platform=args.add_current_platform)
