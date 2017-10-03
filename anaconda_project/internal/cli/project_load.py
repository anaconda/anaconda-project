# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Command-line-specific project load utilities."""
from __future__ import absolute_import, print_function

import sys

from anaconda_project.project import Project
from anaconda_project.frontend import Frontend

import anaconda_project.internal.cli.console_utils as console_utils


class CliFrontend(Frontend):
    def __init__(self):
        super(CliFrontend, self).__init__()

    def info(self, message):
        print(message)

    def error(self, message):
        print(message, file=sys.stderr)

    def partial_info(self, data):
        sys.stdout.write(data)
        sys.stdout.flush()

    def partial_error(self, data):
        sys.stderr.write(data)
        sys.stderr.flush()


def load_project(dirname):
    """Load a Project, fixing it if needed and possible."""
    project = Project(dirname, frontend=CliFrontend())

    if console_utils.stdin_is_interactive():
        had_fixable = len(project.fixable_problems) > 0
        for problem in project.fixable_problems:
            print(problem.text)
            should_fix = console_utils.console_ask_yes_or_no(problem.fix_prompt, default=False)
            if should_fix:
                problem.fix(project)
            else:
                problem.no_fix(project)

        # both fix() and no_fix() can modify project_file, if no changes
        # were made this is a no-op.
        if had_fixable:
            project.save()

    return project
