"""The ``launch`` command executes a project, by default without asking questions (fails on missing config)."""
from __future__ import absolute_import, print_function

import os
import sys

from project.prepare import prepare, UI_MODE_NOT_INTERACTIVE
from project.project import Project


def launch_command(project_dir, ui_mode):
    """Run the project.

    Returns:
        Does not return if successful.
    """
    project = Project(project_dir)
    result = prepare(project, ui_mode=ui_mode)

    if result.failed:
        return
    elif result.command_exec_info is None:
        print("No known launch command for project %s; try adding an 'app: entry: ' to project.yml" % project_dir,
              file=sys.stderr)
    else:
        try:
            result.command_exec_info.execvpe()
        except OSError as e:
            print("Failed to execute '%s': %s" % (" ".join(result.command_exec_info.args), e.strerror), file=sys.stderr)


def main(project_dir='.', ui_mode=UI_MODE_NOT_INTERACTIVE):
    """Start the launch command."""
    project_dir = os.path.abspath(project_dir)
    launch_command(project_dir, ui_mode=ui_mode)
    # if we returned, we failed to launch the command and should have printed an error
    sys.exit(1)
