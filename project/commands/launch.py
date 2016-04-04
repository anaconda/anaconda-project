"""The ``launch`` command executes a project, by default without asking questions (fails on missing config)."""
from __future__ import absolute_import, print_function

import sys

from project.prepare import prepare
from project.project import Project


def launch_command(project_dir, ui_mode, conda_environment, command, extra_command_args):
    """Run the project.

    Returns:
        Does not return if successful.
    """
    project = Project(project_dir, default_conda_environment=conda_environment, command=command)
    result = prepare(project, ui_mode=ui_mode, extra_command_args=extra_command_args)

    if result.failed:
        return
    elif result.command_exec_info is None:
        print("No known launch command for project %s; try adding a 'commands:' section to project.yml" % project_dir,
              file=sys.stderr)
    else:
        try:
            result.command_exec_info.execvpe()
        except OSError as e:
            print("Failed to execute '%s': %s" % (" ".join(result.command_exec_info.args), e.strerror), file=sys.stderr)


def main(args):
    """Start the launch command and return exit status code.."""
    launch_command(args.project_dir, args.mode, args.environment, args.command, args.extra_args_for_command)
    # if we returned, we failed to launch the command and should have printed an error
    return 1
