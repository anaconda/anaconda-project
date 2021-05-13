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
from anaconda_project.internal.cli.console_utils import (print_project_problems, console_ask_yes_or_no)


def init_command(project_dir, assume_yes, with_anaconda_package):
    """Initialize a new project.

    Returns:
        Exit code (0 on success)
    """
    # we don't want False right now because either you specify
    # --yes or we go with the default in project_ops.create
    # (depends on whether project file already exists).
    assert assume_yes is None or assume_yes is True
    assert with_anaconda_package is None or with_anaconda_package is True

    if not os.path.exists(project_dir):
        if assume_yes:
            make_directory = True
        else:
            make_directory = console_ask_yes_or_no("Create directory '%s'?" % project_dir, default=False)
    else:
        make_directory = False

    project = project_ops.create(project_dir,
                                 make_directory=make_directory,
                                 fix_problems=assume_yes,
                                 with_anaconda_package=with_anaconda_package)
    if print_project_problems(project):
        return 1
    else:
        print("Project configuration is in %s" % project.project_file.filename)
        return 0


def main(args):
    """Start the init command and return exit status code."""
    return init_command(args.directory, args.yes, args.with_anaconda_package)
