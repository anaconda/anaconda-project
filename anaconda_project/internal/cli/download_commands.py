# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Commands related to the downloads section."""
from __future__ import absolute_import, print_function

import sys

from anaconda_project.internal.cli.project_load import load_project
from anaconda_project import project_ops
from anaconda_project.internal.cli import console_utils
from anaconda_project.prepare import prepare_without_interaction
from anaconda_project.provide import PROVIDE_MODE_CHECK


def add_download(project_dir, env_spec_name, filename_variable, download_url, filename, hash_algorithm, hash_value):
    """Add an item to the downloads section."""
    project = load_project(project_dir)
    if (hash_algorithm or hash_value) and not bool(hash_algorithm and hash_value):
        print("Error: mutually dependant parameters: --hash-algorithm and --hash-value.", file=sys.stderr)
        return 1
    status = project_ops.add_download(project,
                                      env_spec_name=env_spec_name,
                                      env_var=filename_variable,
                                      url=download_url,
                                      filename=filename,
                                      hash_algorithm=hash_algorithm,
                                      hash_value=hash_value)
    if status:
        print(status.status_description)
        print("Added %s to the project file." % download_url)
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def remove_download(project_dir, env_spec_name, filename_variable):
    """Remove a download requirement from project and from file system."""
    project = load_project(project_dir)
    # we can remove a download even if prepare fails, so disable
    # printing errors in the frontend.
    with project.null_frontend():
        result = prepare_without_interaction(project, env_spec_name=env_spec_name, mode=PROVIDE_MODE_CHECK)
    status = project_ops.remove_download(project,
                                         env_spec_name=env_spec_name,
                                         env_var=filename_variable,
                                         prepare_result=result)
    if status:
        print(status.status_description)
        print("Removed {} from the project file.".format(filename_variable))
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def list_downloads(project_dir, env_spec_name):
    """List the downloads present in project."""
    project = load_project(project_dir)
    if console_utils.print_project_problems(project):
        return 1

    if project.downloads(env_spec_name):
        print("Downloads for project: {}\n".format(project_dir))
        console_utils.print_names_and_descriptions(project.download_requirements(env_spec_name), name_attr='title')
    else:
        print("No downloads found in project.")
    return 0


def main_add(args):
    """Start the download command and return exit status code."""
    return add_download(args.directory, args.env_spec, args.filename_variable, args.download_url, args.filename,
                        args.hash_algorithm, args.hash_value)


def main_remove(args):
    """Start the remove download command and return exit status code."""
    return remove_download(args.directory, args.env_spec, args.filename_variable)


def main_list(args):
    """Start the list download command and return exit status code."""
    return list_downloads(args.directory, args.env_spec)
