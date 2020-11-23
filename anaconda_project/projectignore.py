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
# project-local contains your personal configuration choices and state
/anaconda-project-local.yml

# Files autocreated by Python
__pycache__/
*.pyc
*.pyo
*.pyd

# Notebook stuff
.ipynb_checkpoints/

# Spyder stuff
/.spyderproject
""".lstrip()


def add_projectignore_if_none(project_directory):
    """Add .projectignore if not found in project directory."""
    filename = os.path.join(project_directory, ".projectignore")
    if not os.path.exists(filename):
        try:
            with codecs.open(filename, 'w', 'utf-8') as f:
                f.write(_default_projectignore)
        except IOError:
            pass
