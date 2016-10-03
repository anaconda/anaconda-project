# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import re

_remove_chars = re.compile('[^A-Za-z0-9-_]', re.UNICODE)


def slugify(s):
    """A simple slugifier.

    This keeps ascii alphanumerics, -, and _, but replaces
    everything else with hyphen.
    """
    return re.sub(_remove_chars, '-', s)
