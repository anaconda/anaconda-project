"""The ``prepare`` command configures a project to run, asking the user questions if necessary."""
from __future__ import absolute_import, print_function

import os
import sys

from project import prepare
from project.project import Project


def prepare_command(dirname, ui_mode):
    """Configure the project to run.

    Returns:
        Prepare result (can be treated as True on success).
    """
    project = Project(dirname)
    result = prepare.prepare(project, ui_mode=ui_mode, keep_going_until_success=True)

    return result


def main(args):
    """Start the prepare command."""
    dirname = os.path.abspath(args.project_dir)
    if prepare_command(dirname, ui_mode=prepare.UI_MODE_BROWSER):
        sys.exit(0)
    else:
        sys.exit(1)
