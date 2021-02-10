# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2019, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Utilities for .projectignore file."""

import os
import codecs

_default_projectignore = """
# This file contains a list of match patterns that instructs
# anaconda-project to exclude certain files or directories when
# building a project archive. The file format is a simplfied
# version of Git's .gitignore file format. In fact, if the
# project is hosted in a Git repository, these patterns can be
# merged into the .gitignore file and this file removed.
# See the anaconda-project documentation for more details.

# Python caching
*.pyc
*.pyd
*.pyo
__pycache__/

# Jupyter & Spyder stuff
.ipynb_checkpoints/
.Trash-*/
/.spyderproject
""".lstrip()


def add_projectignore_if_none(project_directory):
    """Add .projectignore if not found in project directory."""
    filename = os.path.join(project_directory, ".projectignore")
    gfilename = os.path.join(project_directory, ".gitignore")
    if not os.path.exists(filename) and not os.path.exists(gfilename):
        try:
            with codecs.open(filename, 'w', 'utf-8') as f:
                f.write(_default_projectignore)
        except IOError:
            pass
