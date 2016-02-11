"""The ``main`` function chooses and runs a subcommand."""
from __future__ import absolute_import, print_function

import sys


def main(argv):
    """Start the launch command."""
    # future: real arg parser
    if len(argv) < 2:
        print("Please specify a subcommand.", file=sys.stderr)
    else:
        subcommand = argv[1]
        if subcommand == 'launch':
            import project.commands.launch as launch
            launch.main(argv[1:])
        elif subcommand == 'prepare':
            import project.commands.prepare as prepare
            prepare.main(argv[1:])
        elif subcommand == 'activate':
            import project.commands.activate as activate
            activate.main(argv[1:])
        else:
            print("Unknown subcommand '%s'." % subcommand, file=sys.stderr)

    # the various sub-mains exit(0) if they succeed, if we get here
    # we must not have called one of them
    sys.exit(1)
