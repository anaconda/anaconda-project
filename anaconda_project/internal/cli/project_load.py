# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Command-line-specific project load utilities."""
from __future__ import absolute_import, print_function

from anaconda_project.project import Project

import anaconda_project.internal.cli.console_utils as console_utils


def load_project(dirname):
    """Load a Project, fixing it if needed and possible."""
    project = Project(dirname)

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
