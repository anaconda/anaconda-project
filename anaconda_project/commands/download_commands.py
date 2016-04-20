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
from anaconda_project.commands.console_utils import print_status_errors


def add_download(project_dir, filename_variable, download_url):
    """Add an item to the downloads section."""
    project = Project(project_dir)
    status = project_ops.add_download(project, env_var=filename_variable, url=download_url)
    if status:
        print(status.status_description)
        print("Added %s to the project file." % download_url)
        return 0
    else:
        print_status_errors(status)
        return 1


def main_add(args):
    """Start the download command and return exit status code."""
    return add_download(args.project, args.filename_variable, args.download_url)
