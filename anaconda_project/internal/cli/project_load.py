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
        """Frontend for printing."""
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
    project = Project(dirname, frontend=CliFrontend(), must_exist=True)

    # No sense in engaging the user if we cannot achieve a fixed state.
    if project.unfixable_problems:
        return project

    if console_utils.stdin_is_interactive():
        regressions = 0
        problems = project.fixable_problems
        while problems and regressions < 3:
            # Instead of looping through the problems in the list, we
            # fix only the first one and refresh the list. This allows
            # us to detect when fixing one problem impacts another,
            # positively or negatively.
            problem = problems[0]
            print(problem.text)
            should_fix = console_utils.console_ask_yes_or_no(problem.fix_prompt, default=False)
            if not should_fix:
                break
            problem.fix(project)
            project.use_changes_without_saving()
            o_problems, problems = problems, project.fixable_problems
            # If the number of problems doesn't decrease as a result of
            # fixing a problem, it suggests some sort of negative cycle.
            # We can't reliably detect a cycle, so instead we simply let
            # this happen 3 times before we give up.
            regressions += (len(problems) >= len(o_problems))
        if not problems:
            project.save()

    return project
