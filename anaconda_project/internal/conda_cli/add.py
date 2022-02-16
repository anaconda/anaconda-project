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
from anaconda_project.internal.cli.environment_commands import add_packages



def main(args):
    """Start the init command and return exit status code."""
    return init_command(args.directory, args.name, args.channel, args.dependencies, not args.no_install)
