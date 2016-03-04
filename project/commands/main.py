"""The ``main`` function chooses and runs a subcommand."""
from __future__ import absolute_import, print_function

import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter

import project.commands.launch as launch
import project.commands.prepare as prepare
import project.commands.activate as activate


def _run_parser(args):
    """Internal function to run the parsing of params and run the commands. Allows mocking."""
    parser = ArgumentParser("Anaconda project tool", epilog=__doc__, formatter_class=RawDescriptionHelpFormatter)

    subparsers = parser.add_subparsers()

    preset = subparsers.add_parser('launch', description="Runs the project")
    preset.add_argument('project_dir', default='.')
    # preset.add_argument('ui_mode')
    preset.set_defaults(main=launch.main)

    preset = subparsers.add_parser('prepare', description="Configure the project to run.")
    preset.add_argument('project_dir', default='.')
    preset.set_defaults(main=prepare.main)

    preset = subparsers.add_parser('activate', "Prepare project and outputs lines to be sourced.")
    preset.add_argument('project_dir', default='.')
    preset.set_defaults(main=activate.main)

    args = parser.parse_args(args)

    args.main(args.project_dir)


def main(argv):
    """Start the launch command."""
    _run_parser(argv)
    # the various sub-mains exit(0) if they succeed, if we get here
    # we must not have called one of them
    sys.exit(1)
