# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import platform
import sys

try:  # pragma: no cover
    from collections.abc import Mapping, Sequence
except ImportError:
    from collections import Mapping, Sequence

_PY2 = sys.version_info[0] == 2


def is_unicode(s):
    if _PY2:  # pragma: no cover (py2/py3)
        return isinstance(s, unicode)  # pragma: no cover (py2/py3) # noqa
    else:  # pragma: no cover (py2/py3)
        return isinstance(s, str)  # pragma: no cover (py2/py3)


def is_string(s):
    if _PY2:  # pragma: no cover (py2/py3)
        return isinstance(s, basestring)  # pragma: no cover (py2/py3) # noqa
    else:  # pragma: no cover (py2/py3)
        return isinstance(s, str)  # pragma: no cover (py2/py3)


def is_list(v):
    return isinstance(v, Sequence) and not is_string(v)


def is_dict(v):
    return isinstance(v, Mapping)


def env_without_unicode(environ):
    # On Windows / Python 2.7, Popen explodes if given unicode strings in the environment.
    if _PY2 and platform.system() == 'Windows':  # pragma: no cover (py2/py3)
        environ_copy = dict()
        for key, value in environ.items():
            if isinstance(key, unicode):  # noqa
                key = key.encode()
            if isinstance(value, unicode):  # noqa
                value = value.encode()
            assert isinstance(key, str)
            assert isinstance(value, str)
            environ_copy[key] = value
        return environ_copy
    else:  # pragma: no cover (py2/py3)
        return environ
