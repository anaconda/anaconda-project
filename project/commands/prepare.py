"""The ``prepare`` command configures a project to run, asking the user questions if necessary."""
from __future__ import absolute_import, print_function

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


def main(args):
    """Start the prepare command and return exit status code."""
    if prepare_command(args.project_dir, args.mode):
        return 0
    else:
        return 1
