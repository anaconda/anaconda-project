# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""The ``main`` function chooses and runs a subcommand."""
from __future__ import absolute_import, print_function

import logging
import os
import sys
from argparse import ArgumentParser, REMAINDER

from anaconda_project.internal.cli.prepare_with_mode import (UI_MODE_TEXT_ASK_QUESTIONS,
                                                             UI_MODE_TEXT_DEVELOPMENT_DEFAULTS_OR_ASK, _all_ui_modes)
from anaconda_project import __version__ as version
from anaconda_project.verbose import push_verbose_logger, pop_verbose_logger
from anaconda_project.project import ALL_COMMAND_TYPES
from anaconda_project.docker import DEFAULT_BUILDER_IMAGE
from anaconda_project.requirements_registry.registry import RequirementsRegistry
from anaconda_project.requirements_registry.requirements.download import _hash_algorithms
import anaconda_project
from anaconda_project.internal.cli.bug_handler import handle_bugs
import anaconda_project.internal.cli.init as init
import anaconda_project.internal.cli.run as run
import anaconda_project.internal.cli.prepare as prepare
import anaconda_project.internal.cli.clean as clean
import anaconda_project.internal.cli.archive as archive
import anaconda_project.internal.cli.unarchive as unarchive
import anaconda_project.internal.cli.upload as upload
import anaconda_project.internal.cli.download as download
import anaconda_project.internal.cli.dockerize as dockerize
import anaconda_project.internal.cli.activate as activate
import anaconda_project.internal.cli.variable_commands as variable_commands
import anaconda_project.internal.cli.download_commands as download_commands
import anaconda_project.internal.cli.service_commands as service_commands
import anaconda_project.internal.cli.environment_commands as environment_commands
import anaconda_project.internal.cli.command_commands as command_commands


def _parse_args_and_run_subcommand(argv):
    parser = ArgumentParser(prog="anaconda-project", description="Actions on projects (runnable projects).")

    subparsers = parser.add_subparsers(help="Sub-commands")

    parser.add_argument('-v', '--version', action='version', version=version)
    parser.add_argument('--verbose', action='store_true', default=False, help="show verbose debugging details")

    def add_directory_arg(preset):
        preset.add_argument('--directory',
                            metavar='PROJECT_DIR',
                            default='.',
                            help="Project directory containing anaconda-project.yml (defaults to current directory)")

    def add_env_spec_arg(preset):
        preset.add_argument('--env-spec',
                            metavar='ENVIRONMENT_SPEC_NAME',
                            default=None,
                            action='store',
                            help="An environment spec name from anaconda-project.yml")

    def add_prepare_args(preset, include_command=True):
        add_directory_arg(preset)
        add_env_spec_arg(preset)
        all_supported_modes = list(_all_ui_modes)
        # we don't support "ask about every single thing" mode yet.
        all_supported_modes.remove(UI_MODE_TEXT_ASK_QUESTIONS)
        preset.add_argument('--mode',
                            metavar='MODE',
                            default=UI_MODE_TEXT_DEVELOPMENT_DEFAULTS_OR_ASK,
                            choices=_all_ui_modes,
                            action='store',
                            help="One of " + ", ".join(_all_ui_modes))
        if include_command:
            preset.add_argument(
                '--command',
                metavar='COMMAND_NAME',
                default=None,
                action='store',
                help="A command name from anaconda-project.yml (env spec for this command will be used)")

    def add_env_spec_name_arg(preset, required):
        preset.add_argument('-n',
                            '--name',
                            metavar='ENVIRONMENT_SPEC_NAME',
                            required=required,
                            action='store',
                            help="Name of the environment spec from anaconda-project.yml")

    preset = subparsers.add_parser('init', help="Initialize a directory with default project configuration")
    add_directory_arg(preset)
    preset.add_argument('--with-anaconda-package',
                        action='store_true',
                        help="Add the 'anaconda' metapackage to the packages list.",
                        default=None)
    preset.add_argument('--empty-environment',
                        action='store_true',
                        help="[DEPRECATED] Do not add the default package set to the environment.",
                        default=None)
    preset.add_argument('-y', '--yes', action='store_true', help="Assume yes to all confirmation prompts", default=None)
    preset.set_defaults(main=init.main)

    preset = subparsers.add_parser('run', help="Run the project, setting up requirements first")
    add_prepare_args(preset, include_command=False)
    preset.add_argument('command',
                        metavar='COMMAND_NAME',
                        default=None,
                        nargs='?',
                        help="A command name from anaconda-project.yml")
    preset.add_argument('extra_args_for_command', metavar='EXTRA_ARGS_FOR_COMMAND', default=None, nargs=REMAINDER)
    preset.set_defaults(main=run.main)

    preset = subparsers.add_parser('prepare', help="Set up the project requirements, but does not run the project")
    preset.add_argument('--all', action='store_true', help="Prepare all environments", default=None)
    preset.add_argument('--refresh', action='store_true', help='Remove and recreate the environment', default=None)
    add_prepare_args(preset)
    preset.set_defaults(main=prepare.main)

    preset = subparsers.add_parser('clean',
                                   help="Removes generated state (stops services, deletes environment files, etc)")
    add_directory_arg(preset)
    preset.set_defaults(main=clean.main)

    if not anaconda_project._beta_test_mode:
        preset = subparsers.add_parser('activate',
                                       help="Set up the project and output shell export commands reflecting the setup")
        add_prepare_args(preset)
        preset.set_defaults(main=activate.main)

    preset = subparsers.add_parser('archive',
                                   help="Create a .zip, .tar.gz, or .tar.bz2 archive with project files in it")
    add_directory_arg(preset)
    preset.add_argument('filename', metavar='ARCHIVE_FILENAME')
    preset.add_argument('--pack-envs',
                        action='store_true',
                        help='Experimental: Package env_specs into the archive'
                        ' using conda-pack')

    preset.set_defaults(main=archive.main)

    preset = subparsers.add_parser('unarchive',
                                   help="Unpack a .zip, .tar.gz, or .tar.bz2 archive with project files in it")
    preset.add_argument('filename', metavar='ARCHIVE_FILENAME')
    preset.add_argument('directory', metavar='DESTINATION_DIRECTORY', default=None, nargs='?')

    preset.set_defaults(main=unarchive.main)

    preset = subparsers.add_parser('upload', help="Upload the project to Anaconda Cloud")
    add_directory_arg(preset)
    preset.add_argument('-p', '--private', action='store_true', help="Upload a private project", default=None)
    preset.add_argument('-s', '--site', metavar='SITE', help='Select site to use')
    preset.add_argument('-t', '--token', metavar='TOKEN', help='Auth token or a path to a file containing a token')
    preset.add_argument('-u', '--user', metavar='USERNAME', help='User account, defaults to the current user')
    preset.add_argument('--suffix',
                        metavar='SUFFIX',
                        help='Project archive suffix (.tar.gz, .tar.bz2, .zip)',
                        default='.tar.bz2',
                        choices=['.tar.gz', '.tar.bz2', '.zip'])
    preset.set_defaults(main=upload.main)

    preset = subparsers.add_parser('download', help="Download the project from Anaconda Cloud")
    add_directory_arg(preset)
    preset.add_argument('project',
                        help='The project to download as <username>/<projectname>. If <projectname>' +
                        'has spaces inclose everything in quotes "<username>/<project name>".' +
                        'If specified as <projectname> then the logged-in username is used.')
    preset.add_argument('--no-unpack', action='store_true', help='Do not unpack the project archive.')
    preset.add_argument(
        '--parent_dir',
        default=None,
        help='Download archive to specific directory, otherwise downloaded to current working directory.')
    preset.add_argument('-s', '--site', metavar='SITE', help='Select site to use')
    preset.add_argument('-t', '--token', metavar='TOKEN', help='Auth token or a path to a file containing a token')
    preset.add_argument('-u', '--user', metavar='USERNAME', help='User account, defaults to the current user')
    preset.set_defaults(main=download.main)

    preset = subparsers.add_parser('dockerize', help="Build a docker image of the Anaconda Project.")
    add_directory_arg(preset)
    preset.add_argument('-t',
                        '--tag',
                        default=None,
                        help='Tag of the output docker image in the format name:tag. '
                        'Default: "<project-name>:latest", where <project-name> is taken from '
                        'the name tag in the anaconda-project.yml file.')
    preset.add_argument(
        '--command',
        default='default',
        help='Select the command to run. If unspecified the "default" command is run.\nThe default command '
        'is defined as either the command named "default" (if any) or (otherwise)  '
        'the first command specified in the anaconda-project.yml file.')
    preset.add_argument('--builder-image',
                        default='{}:latest'.format(DEFAULT_BUILDER_IMAGE),
                        help='The s2i builder image')
    preset.add_argument('build_args',
                        default=None,
                        nargs="*",
                        help='Optional arguments for the s2i build command. '
                        'See the output of "s2i build --help" for the available arguments. '
                        'It is recommended to include a -- separator before supplying these arguments.')
    preset.set_defaults(main=dockerize.main)

    preset = subparsers.add_parser('add-variable', help="Add a required environment variable to the project")
    add_env_spec_arg(preset)
    preset.add_argument('vars_to_add', metavar='VARS_TO_ADD', default=None, nargs=REMAINDER)
    preset.add_argument('--default',
                        metavar='DEFAULT_VALUE',
                        default=None,
                        help='Default value if environment variable is unset')
    add_directory_arg(preset)
    preset.set_defaults(main=variable_commands.main_add)

    preset = subparsers.add_parser('remove-variable', help="Remove an environment variable from the project")
    add_env_spec_arg(preset)
    add_directory_arg(preset)
    preset.add_argument('vars_to_remove', metavar='VARS_TO_REMOVE', default=None, nargs=REMAINDER)
    preset.set_defaults(main=variable_commands.main_remove)

    preset = subparsers.add_parser('list-variables', help="List all variables on the project")
    add_env_spec_arg(preset)
    add_directory_arg(preset)
    preset.set_defaults(main=variable_commands.main_list)

    preset = subparsers.add_parser('set-variable',
                                   help="Set an environment variable value in anaconda-project-local.yml")
    add_env_spec_arg(preset)
    preset.add_argument('vars_and_values', metavar='VARS_AND_VALUES', default=None, nargs=REMAINDER)
    add_directory_arg(preset)
    preset.set_defaults(main=variable_commands.main_set)

    preset = subparsers.add_parser('unset-variable',
                                   help="Unset an environment variable value from anaconda-project-local.yml")
    add_env_spec_arg(preset)
    add_directory_arg(preset)
    preset.add_argument('vars_to_unset', metavar='VARS_TO_UNSET', default=None, nargs=REMAINDER)
    preset.set_defaults(main=variable_commands.main_unset)

    preset = subparsers.add_parser('add-download', help="Add a URL to be downloaded before running commands")
    add_directory_arg(preset)
    add_env_spec_arg(preset)
    preset.add_argument('filename_variable', metavar='ENV_VAR_FOR_FILENAME', default=None)
    preset.add_argument('download_url', metavar='DOWNLOAD_URL', default=None)
    preset.add_argument('--filename', help="The name to give the file/folder after downloading it", default=None)
    preset.add_argument('--hash-algorithm',
                        help="Defines which hash algorithm to use",
                        default=None,
                        choices=_hash_algorithms)
    preset.add_argument('--hash-value', help="The expected checksum hash of the downloaded file", default=None)
    preset.set_defaults(main=download_commands.main_add)

    preset = subparsers.add_parser('remove-download', help="Remove a download from the project and from the filesystem")
    add_directory_arg(preset)
    add_env_spec_arg(preset)
    preset.add_argument('filename_variable', metavar='ENV_VAR_FOR_FILENAME', default=None)
    preset.set_defaults(main=download_commands.main_remove)

    preset = subparsers.add_parser('list-downloads', help="List all downloads on the project")
    add_directory_arg(preset)
    add_env_spec_arg(preset)
    preset.set_defaults(main=download_commands.main_list)

    service_types = RequirementsRegistry().list_service_types()
    service_choices = list(map(lambda s: s.name, service_types))

    def add_service_variable_name(preset):
        preset.add_argument('--variable', metavar='ENV_VAR_FOR_SERVICE_ADDRESS', default=None)

    preset = subparsers.add_parser('add-service', help="Add a service to be available before running commands")
    add_directory_arg(preset)
    add_env_spec_arg(preset)
    add_service_variable_name(preset)
    preset.add_argument('service_type', metavar='SERVICE_TYPE', default=None, choices=service_choices)
    preset.set_defaults(main=service_commands.main_add)

    preset = subparsers.add_parser('remove-service', help="Remove a service from the project")
    add_directory_arg(preset)
    add_env_spec_arg(preset)
    preset.add_argument('variable', metavar='SERVICE_REFERENCE', default=None)
    preset.set_defaults(main=service_commands.main_remove)

    preset = subparsers.add_parser('list-services', help="List services present in the project")
    add_directory_arg(preset)
    add_env_spec_arg(preset)
    preset.set_defaults(main=service_commands.main_list)

    def add_package_args(preset):
        preset.add_argument('--pip', action='store_true', help='Install the requested packages using pip.')
        preset.add_argument('-c',
                            '--channel',
                            metavar='CHANNEL',
                            action='append',
                            help='Channel to search for packages')
        preset.add_argument('packages', metavar='PACKAGES', default=None, nargs=REMAINDER)

    preset = subparsers.add_parser('add-env-spec', help="Add a new environment spec to the project")
    add_directory_arg(preset)
    add_package_args(preset)
    add_env_spec_name_arg(preset, required=True)
    preset.set_defaults(main=environment_commands.main_add)

    preset = subparsers.add_parser('remove-env-spec', help="Remove an environment spec from the project")
    add_directory_arg(preset)
    add_env_spec_name_arg(preset, required=True)
    preset.set_defaults(main=environment_commands.main_remove)

    preset = subparsers.add_parser('list-env-specs', help="List all environment specs for the project")
    add_directory_arg(preset)
    preset.set_defaults(main=environment_commands.main_list_env_specs)

    preset = subparsers.add_parser('export-env-spec', help="Save an environment spec as a conda environment file")
    add_directory_arg(preset)
    add_env_spec_name_arg(preset, required=False)
    preset.add_argument('filename', metavar='ENVIRONMENT_FILE')
    preset.set_defaults(main=environment_commands.main_export)

    preset = subparsers.add_parser('lock', help="Lock all packages at their current versions")
    add_directory_arg(preset)
    add_env_spec_name_arg(preset, required=False)
    preset.set_defaults(main=environment_commands.main_lock)

    preset = subparsers.add_parser('unlock', help="Remove locked package versions")
    add_directory_arg(preset)
    add_env_spec_name_arg(preset, required=False)
    preset.set_defaults(main=environment_commands.main_unlock)

    preset = subparsers.add_parser('update', help="Update all packages to their latest versions")
    add_directory_arg(preset)
    add_env_spec_name_arg(preset, required=False)
    preset.set_defaults(main=environment_commands.main_update)

    preset = subparsers.add_parser('add-packages', help="Add packages to one or all project environments")
    add_directory_arg(preset)
    add_env_spec_arg(preset)
    add_package_args(preset)
    preset.set_defaults(main=environment_commands.main_add_packages)

    preset = subparsers.add_parser('remove-packages', help="Remove packages from one or all project environments")
    add_directory_arg(preset)
    add_env_spec_arg(preset)
    preset.add_argument('--pip', action='store_true', help='Uninstall the requested packages using pip.')
    preset.add_argument('packages', metavar='PACKAGE_NAME', default=None, nargs='+')
    preset.set_defaults(main=environment_commands.main_remove_packages)

    preset = subparsers.add_parser('list-packages', help="List packages for an environment on the project")
    add_directory_arg(preset)
    add_env_spec_arg(preset)
    preset.set_defaults(main=environment_commands.main_list_packages)

    def add_platforms_list(preset):
        preset.add_argument('platforms', metavar='PLATFORM_NAME', default=None, nargs='+')

    preset = subparsers.add_parser('add-platforms', help="Add platforms to one or all project environments")
    add_directory_arg(preset)
    add_env_spec_arg(preset)
    add_platforms_list(preset)
    preset.set_defaults(main=environment_commands.main_add_platforms)

    preset = subparsers.add_parser('remove-platforms', help="Remove platforms from one or all project environments")
    add_directory_arg(preset)
    add_env_spec_arg(preset)
    add_platforms_list(preset)
    preset.set_defaults(main=environment_commands.main_remove_platforms)

    preset = subparsers.add_parser('list-platforms', help="List platforms for an environment on the project")
    add_directory_arg(preset)
    add_env_spec_arg(preset)
    preset.set_defaults(main=environment_commands.main_list_platforms)

    def add_command_name_arg(preset):
        preset.add_argument('name', metavar="NAME", help="Command name used to invoke it")

    preset = subparsers.add_parser('add-command', help="Add a new command to the project")
    add_directory_arg(preset)
    command_choices = list(ALL_COMMAND_TYPES) + ['ask']
    command_choices.remove("conda_app_entry")  # conda_app_entry is sort of silly and may go away
    preset.add_argument('--type', action="store", choices=command_choices, help="Command type to add")
    add_command_name_arg(preset)
    add_env_spec_arg(preset)
    preset.add_argument('--supports-http-options',
                        dest='supports_http_options',
                        action="store_true",
                        help="The command supports project's HTTP server options")
    preset.add_argument('--no-supports-http-options',
                        dest='supports_http_options',
                        action="store_false",
                        help=" The command does not support project's HTTP server options")
    preset.add_argument('command', metavar="COMMAND", help="Command line or app filename to add")
    preset.set_defaults(main=command_commands.main, supports_http_options=None)

    preset = subparsers.add_parser('remove-command', help="Remove a command from the project")
    add_directory_arg(preset)
    add_command_name_arg(preset)
    preset.set_defaults(main=command_commands.main_remove)

    preset = subparsers.add_parser('list-default-command', help="List only the default command on the project")
    add_directory_arg(preset)
    preset.set_defaults(main=command_commands.main_default)

    preset = subparsers.add_parser('list-commands', help="List the commands on the project")
    add_directory_arg(preset)
    preset.set_defaults(main=command_commands.main_list)

    # argparse doesn't do this for us for whatever reason
    if len(argv) < 2:
        print("Must specify a subcommand.", file=sys.stderr)
        parser.print_usage(file=sys.stderr)
        return 2  # argparse exits with 2 on bad args, copy that

    try:
        args = parser.parse_args(argv[1:])
    except SystemExit as e:
        return e.code

    if args.verbose:
        logger = (logging.getLoggerClass())(name="anaconda_project_verbose")
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(stream=sys.stderr)
        logger.addHandler(handler)
        push_verbose_logger(logger)

    try:
        # '--directory' is used for most subcommands; for unarchive,
        # args.directory is positional and may be None
        if 'directory' in args and args.directory is not None:
            args.directory = os.path.realpath(os.path.abspath(args.directory))
        return args.main(args)
    finally:
        if args.verbose:
            pop_verbose_logger()


def _main_without_bug_handler():
    anaconda_project._enter_beta_test_mode()
    return _parse_args_and_run_subcommand(sys.argv)


def main():
    """anaconda-project command line tool Conda-style entry point.

    Conda expects us to take no args and return an exit code.
    """
    details = {'version': version}
    return handle_bugs(_main_without_bug_handler, program_name='anaconda-project', details_dict=details)
