"""The ``main`` function chooses and runs a subcommand."""
from __future__ import absolute_import, print_function

import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter

import project.commands.launch as launch
import project.commands.prepare as prepare
import project.commands.activate as activate

def main(argv):
    """Start the launch command."""
    parser = ArgumentParser(
        "Anaconda project tool",
        epilog=__doc__,
        formatter_class=RawDescriptionHelpFormatter)

    subparsers = parser.add_subparsers()

    preset = subparsers.add_parser('launch', description=launch.launch_command.__doc__)
    preset.add_argument('dirname')
    # preset.add_argument('ui_mode')
    preset.set_defaults(main=launch.main)

    preset = subparsers.add_parser('prepare', description=prepare.prepare_command.__doc__)
    preset.add_argument('dirname', default='.')
    preset.set_defaults(main=prepare.main)

    preset = subparsers.add_parser('activate', description=activate.activate.__doc__)
    preset.add_argument('dirname', default='.')
    preset.set_defaults(main=activate.main)

    args = parser.parse_args()

    args.main(args)
    # the various sub-mains exit(0) if they succeed, if we get here
    # we must not have called one of them
    sys.exit(1)
