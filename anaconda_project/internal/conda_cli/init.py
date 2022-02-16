# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""The ``init`` command creates a new project."""
from __future__ import absolute_import, print_function

import os

from anaconda_project import project_ops
from anaconda_project.internal.cli.environment_commands import lock
from anaconda_project.internal.cli.prepare import prepare_command


def init_command(project_dir, name, channels, dependencies, install):
    """Initialize a new project.

    Returns:
        Exit code (0 on success)
    """

    if not os.path.exists(project_dir):
        make_directory = True
    else:
        make_directory = False

    project = project_ops.init(directory_path=project_dir,
                               make_directory=make_directory,
                               dependencies=dependencies,
                               channels=channels,
                               name=name)
    if install:
        status = prepare_command(project_dir, ui_mode='production_defaults', conda_environment=None,
                                 command_name=None)
        if not status:
            return 1
        else:
            status = lock(project_dir, env_spec_name=None)
            if not status:
                return 1
    return 0


def main(args):
    """Start the init command and return exit status code."""
    return init_command(args.directory, args.name, args.channel, args.dependencies, not args.no_install)
