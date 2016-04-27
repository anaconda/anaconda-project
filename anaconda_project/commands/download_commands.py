# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Commands related to the downloads section."""
from __future__ import absolute_import, print_function

from anaconda_project.project import Project
from anaconda_project import project_ops
from anaconda_project.commands import console_utils


def add_download(project_dir, filename_variable, download_url):
    """Add an item to the downloads section."""
    project = Project(project_dir)
    status = project_ops.add_download(project, env_var=filename_variable, url=download_url)
    if status:
        print(status.status_description)
        print("Added %s to the project file." % download_url)
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def list_downloads(project_dir):
    """List the downloads present in project."""
    project = Project(project_dir)
    if console_utils.print_project_problems(project):
        return 1

    downloads = project.downloads
    if downloads:
        print("Found these downloads in project:")
        print('\n'.join(sorted(downloads)))
    else:
        print("No downloads found in project.")
    return 0


def main_add(args):
    """Start the download command and return exit status code."""
    return add_download(args.project, args.filename_variable, args.download_url)


def main_list(args):
    """Start the list download command and return exit status code."""
    return list_downloads(args.project)
