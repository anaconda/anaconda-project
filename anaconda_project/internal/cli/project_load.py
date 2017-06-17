# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Command-line-specific project load utilities."""
from __future__ import absolute_import, print_function

import os, sys

from anaconda_project.project import Project
from anaconda_project.frontend import Frontend

import anaconda_project.internal.cli.console_utils as console_utils
from anaconda_project.internal.cli.init import init_command


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

    if not os.path.exists(project.project_file.filename):
        print("No project file exists. Please create one by running `anaconda-project init`.")
        exit(1)

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
