# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""The ``main`` function chooses and runs a subcommand."""
from __future__ import absolute_import, print_function

# the point of this file is to make the internal main() into a public
# entry point.
import anaconda_project.internal.cli.main as cli_main


def main():
    """anaconda-project command line tool Conda-style entry point.

    Conda expects us to take no args and return an exit code.
    """
    return cli_main.main()


if __name__ == '__main__':
    main()
