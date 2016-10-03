# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from conda_kapsel.internal.py2_compat import is_unicode

import re
import unicodedata

_remove_chars = re.compile('[^A-Za-z0-9-_]', re.UNICODE)


def slugify(s):
    """A simple slugifier.

    This keeps ascii alphanumerics, -, and _, but replaces
    everything else with hyphen.
    """
    if not is_unicode(s):
        # normalize() requires a unicode string
        s = s.decode(encoding='utf-8', errors='replace')
    s = unicodedata.normalize('NFC', s)

    # Using `re.sub(_remove_chars, '-', s)` results in
    # a different number of hyphens on OS X vs. Linux,
    # maybe due to some Python re code confusing bytes vs. chars?
    # So we manually do our own replacement.
    def replace(c):
        if _remove_chars.match(c):
            return "-"
        else:
            return c

    return "".join(map(replace, s))
