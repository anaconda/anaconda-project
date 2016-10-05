# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Command-line-specific project load utilities."""
from __future__ import absolute_import, print_function

from conda_kapsel.project import Project

import conda_kapsel.commands.console_utils as console_utils


def load_project(dirname):
    """Load a Project, fixing it if needed and possible."""
    project = Project(dirname)

    if console_utils.stdin_is_interactive():
        for problem in project.fixable_problems:
            print(problem.text)
            should_fix = console_utils.console_ask_yes_or_no(problem.fix_prompt, default=False)
            if should_fix:
                problem.fix(project)
            else:
                problem.no_fix(project)

        # no-op if the fixes didn't do anything
        project.project_file.save()

    return project
