# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""The ``main`` function chooses and runs a subcommand."""
from __future__ import absolute_import, print_function

import os
import sys
from argparse import ArgumentParser, REMAINDER

from project.prepare import UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT, _all_ui_modes

import project.commands.launch as launch
import project.commands.prepare as prepare
import project.commands.activate as activate


def _parse_args_and_run_subcommand(argv):
    parser = ArgumentParser(prog="anaconda-project", description="Actions on Anaconda projects.")

    # future: make setup.py store our version in a version.py then use that here
    # parser.add_argument('-v', '--version', action='version', version='0.1')

    subparsers = parser.add_subparsers(help="Sub-commands")

    def add_common_args(preset):
        preset.add_argument('--project', metavar='PROJECT_DIR', default='.', nargs='?')
        preset.add_argument('--environment',
                            metavar='ENVIRONMENT_NAME',
                            default=None,
                            action='store',
                            help="An environment name from project.yml")
        preset.add_argument('--mode',
                            metavar='MODE',
                            default=UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT,
                            choices=_all_ui_modes,
                            action='store',
                            help="One of " + ", ".join(_all_ui_modes))

    preset = subparsers.add_parser('launch', help="Runs the project, setting up requirements first.")
    add_common_args(preset)
    preset.add_argument('--command',
                        metavar="COMMAND_NAME",
                        default=None,
                        action="store",
                        help="A command name from project.yml")
    preset.add_argument('extra_args_for_command', metavar='EXTRA_ARGS_FOR_COMMAND', default=None, nargs=REMAINDER)
    preset.set_defaults(main=launch.main)

    preset = subparsers.add_parser('prepare', help="Sets up project requirements but does not run the project.")
    add_common_args(preset)
    preset.set_defaults(main=prepare.main)

    preset = subparsers.add_parser('activate',
                                   help="Sets up project and outputs shell export commands reflecting the setup.")
    add_common_args(preset)
    preset.set_defaults(main=activate.main)

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
    if 'project' in args:
        args.project = os.path.abspath(args.project)
    return args.main(args)


def main():
    """anaconda-project command line tool Conda-style entry point.

    Conda expects us to take no args and return an exit code.
    """
    return _parse_args_and_run_subcommand(sys.argv)
