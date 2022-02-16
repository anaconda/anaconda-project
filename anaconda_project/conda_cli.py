# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""The entry points for conda- commands"""
from __future__ import absolute_import, print_function


import logging
import sys
from argparse import ArgumentParser, REMAINDER

from anaconda_project import __version__ as version
from anaconda_project.verbose import push_verbose_logger
from anaconda_project.internal.conda_cli.init import main as conda_init
from anaconda_project.internal.cli.environment_commands import main_add_packages as conda_add


def _make_parser(name, description, with_dependencies=False):
    """Initialize a parser with standard flags"""
    parser = ArgumentParser(prog="conda-{name}".format(name=name), description=description)
    parser.add_argument('-v', '--version', action='version', version=version)
    parser.add_argument('--verbose', action='store_true', default=False, help="show verbose debugging details")
    parser.add_argument('--directory',
                        metavar='PROJECT_DIR',
                        default='.',
                        help="Project directory containing (defaults to current directory)")

    if with_dependencies:
        # parser.add_argument('--pip', action='store_true', help='Install the requested dependencies using pip.')
        parser.add_argument('-c',
                            '--channel',
                            metavar='CHANNEL',
                            action='append',
                            help='Channel to search for dependencies')
        parser.add_argument('dependencies', metavar='DEPENDENCIES', default=None, nargs=REMAINDER)

    return parser


def init(argv=None):
    parser = _make_parser('init', description='Initialize a Conda project.', with_dependencies=True)
    parser.add_argument('--name', action='store', default=None, help='name of project')
    parser.add_argument('--no-install', action='store_true', default=False, help='disable creation of env')

    parser.set_defaults(func=conda_init)

    args = parser.parse_args(argv)

    if args.verbose:
        logger = (logging.getLoggerClass())(name="anaconda_project_verbose")
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(stream=sys.stderr)
        logger.addHandler(handler)
        push_verbose_logger(logger)

    return args.func(args)


def add(argv=None):
    parser = _make_parser('add', description='Add a dependency to the project', with_dependencies=True)
    parser.add_argument('--env-spec', action='store', default=None, help='Env spec to add dependencies.'
                                                                         ' Will add to "default" env by default.')

    parser.set_defaults(func=conda_add)

    args = parser.parse_args(argv)

    return args.func(args)
