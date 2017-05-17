# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""The ``main`` function chooses and runs a subcommand."""
from __future__ import absolute_import, print_function

# the point of this file is to make the internal main() into a public
# entry point.
from anaconda_project.internal.cli.main import main  # noqa: F401
