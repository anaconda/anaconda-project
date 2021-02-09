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
# This file contains a list of matching patterns to instruct
# anaconda-project to ignore files/directories when building a
# project archive, such as downloaded data sets. A subset of 
# the .gitignore file format is supported; see the documentation
# for details. In fact, if your project already has a .gitignore
# file, these patterns can be merged into it and this file removed.

/anaconda-project-local.yml

# Python caching
*.pyc
*.pyd
*.pyo
__pycache__/

# nodejs caching
.cache/

# Jupyter & Spyder stuff
.ipynb_checkpoints/
.Trash-*/
/.spyderproject

# Anaconda-project work directories
/tmp/
/envs/
""".lstrip()


def add_projectignore_if_none(project_directory):
    """Add .projectignore if not found in project directory."""
    filename = os.path.join(project_directory, ".projectignore")
    gfile = os.path.join(project_directory, ".gitignore")
    if not os.path.exists(filename) and not os.path.exists(gfilename):
        try:
            with codecs.open(filename, 'w', 'utf-8') as f:
                f.write(_default_projectignore)
        except IOError:
            pass
