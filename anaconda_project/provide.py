# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Public API related to providing requirements."""
from __future__ import absolute_import

# "do the right thing" for prod, dev; OR just check status, don't
# do anything.
#
# In Production mode we do try to provide requirements, but not in
# ways that are likely to be nonsense in production (such as
# starting a throwaway local database).
#
# In Development mode we provide requirements that may not be
# production-suitable, such as a throwaway local database.
#
# In Check mode, we don't do anything that would start processes
# or modify the filesystem; we just see whether requirements have
# been met already.
#

PROVIDE_MODE_PRODUCTION = "production"
PROVIDE_MODE_DEVELOPMENT = "development"
PROVIDE_MODE_CHECK = "check"

_all_provide_modes = (PROVIDE_MODE_PRODUCTION, PROVIDE_MODE_DEVELOPMENT, PROVIDE_MODE_CHECK)
