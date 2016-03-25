"""The ``main`` function chooses and runs a subcommand."""
from __future__ import absolute_import, print_function

import os
import sys
from argparse import ArgumentParser

from project.prepare import UI_MODE_BROWSER, UI_MODE_NOT_INTERACTIVE

import project.commands.launch as launch
import project.commands.prepare as prepare
import project.commands.activate as activate


def _parse_args_and_run_subcommand(argv):
    parser = ArgumentParser(prog="anaconda-project", description="Actions on Anaconda projects.")

    # future: make setup.py store our version in a version.py then use that here
    # parser.add_argument('-v', '--version', action='version', version='0.1')

    subparsers = parser.add_subparsers(help="Sub-commands")

    preset = subparsers.add_parser('launch', help="Runs the project, setting up requirements first.")
    preset.add_argument('project_dir', metavar='PROJECT_DIR', default='.', nargs='?')
    preset.set_defaults(main=launch.main, ui_mode=UI_MODE_NOT_INTERACTIVE)

    preset = subparsers.add_parser('prepare', help="Sets up project requirements but does not run the project.")
    preset.add_argument('project_dir', metavar='PROJECT_DIR', default='.', nargs='?')
    preset.set_defaults(main=prepare.main, ui_mode=UI_MODE_BROWSER)

    preset = subparsers.add_parser('activate',
                                   help="Sets up project and outputs shell export commands reflecting the setup.")
    preset.add_argument('project_dir', metavar='PROJECT_DIR', default='.', nargs='?')
    preset.set_defaults(main=activate.main, ui_mode=UI_MODE_NOT_INTERACTIVE)

    # argparse doesn't do this for us for whatever reason
    if len(argv) < 2:
        print("Must specify a subcommand.", file=sys.stderr)
        parser.print_usage(file=sys.stderr)
        return 2  # argparse exits with 2 on bad args, copy that

    try:
        args = parser.parse_args(argv[1:])
    except SystemExit as e:
        return e.code

    # 'project_dir' is used for all subcommands now, but may not be always
    if 'project_dir' in args:
        args.project_dir = os.path.abspath(args.project_dir)

    return args.main(args)


def main():
    """anaconda-project command line tool Conda-style entry point.

    Conda expects us to take no args and return an exit code.
    """
    return _parse_args_and_run_subcommand(sys.argv)
