# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import sys

_PY2 = sys.version_info[0] == 2


def is_string(s):
    if _PY2:  # pragma: no cover (py2/py3)
        return isinstance(s, basestring)  # pragma: no cover (py2/py3) # noqa
    else:  # pragma: no cover (py2/py3)
        return isinstance(s, str)  # pragma: no cover (py2/py3)
