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
    from anaconda_project.internal.pixi_export import _pick_use_default_env
    promoted = _pick_use_default_env(project)
    status = project_ops.export_pixi(project, filename=filename, use_default=use_default)
    if status:
        print(status.status_description)
        # When the project has no env_spec literally named `default`, the
        # exporter wraps every dep/task/prepare in [feature.{name}.*]
        # blocks. Renaming the project's "primary" env (the default
        # command's, or the first declared env_spec) to `default` collapses
        # those into top-level pixi sections — much cleaner. Tell the user
        # what we did when the flag is on; recommend it when it's off.
        if promoted is not None:
            if use_default:
                print(
                    'The "{}" environment has been renamed "default" in the '
                    'exported Pixi specification.'.format(promoted))
            else:
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
