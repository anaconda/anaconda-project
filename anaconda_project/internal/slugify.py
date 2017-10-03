# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from anaconda_project.internal.py2_compat import is_unicode

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

    # The complicating mess here is that "narrow" builds of Python
    # are really UTF-16, not arrays of unicode characters, so we have
    # to deal with surrogate pairs. re.sub, len(), etc. will all treat
    # surrogate pairs as multiple characters. We have to deal with that
    # by hand to avoid a different slug on different platforms.
    def replace(c):
        # ignore the first half of any surrogate pair, the
        # second half will become a hyphen.
        if 0xD800 <= ord(c[0]) <= 0xDBFF:
            return ""  # pragma: no cover (only on "narrow" python builds)
        elif _remove_chars.match(c):
            return "-"
        else:
            return c

    return "".join(map(replace, s))
