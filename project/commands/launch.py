"""The ``launch`` command executes a project, by default without asking questions (fails on missing config)."""
from __future__ import absolute_import, print_function

import os
import sys

from project.prepare import prepare, UI_MODE_NOT_INTERACTIVE
from project.project import Project


def launch_command(dirname, ui_mode):
    """Run the project.

    Returns:
        Does not return if successful.
    """
    project = Project(dirname)
    result = prepare(project, ui_mode=ui_mode)

    if result.failed:
        return
    elif result.command_exec_info is None:
        print("No known launch command for project %s; try adding an 'app: entry: ' to project.yml" % dirname,
              file=sys.stderr)
    else:
        try:
            result.command_exec_info.execvpe()
        except OSError as e:
            print("Failed to execute '%s': %s" % (" ".join(result.command_exec_info.args), e.strerror), file=sys.stderr)


def main(args):
    """Start the launch command."""
    dirname = os.path.abspath(args.dirname)
    launch_command(dirname, ui_mode=UI_MODE_NOT_INTERACTIVE)
    # if we returned, we failed to launch the command and should have printed an error
    sys.exit(1)
