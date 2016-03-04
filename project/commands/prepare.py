"""The ``prepare`` command configures a project to run, asking the user questions if necessary."""
from __future__ import absolute_import, print_function

import os
import sys

from project import prepare
from project.project import Project


def prepare_command(project_dir, ui_mode):
    """Configure the project to run.

    Returns:
        Prepare result (can be treated as True on success).
    """
    project = Project(project_dir)
    result = prepare.prepare(project, ui_mode=ui_mode, keep_going_until_success=True)

    return result


def main(project_dir='.', ui_mode=prepare.UI_MODE_BROWSER):
    """Start the prepare command."""
    project_dir = os.path.abspath(project_dir)
    if prepare_command(project_dir, ui_mode=ui_mode):
        sys.exit(0)
    else:
        sys.exit(1)
