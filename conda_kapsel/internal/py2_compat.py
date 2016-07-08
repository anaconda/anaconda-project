# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import platform
import sys

_PY2 = sys.version_info[0] == 2


def is_string(s):
    if _PY2:  # pragma: no cover (py2/py3)
        return isinstance(s, basestring)  # pragma: no cover (py2/py3) # noqa
    else:  # pragma: no cover (py2/py3)
        return isinstance(s, str)  # pragma: no cover (py2/py3)


def env_without_unicode(environ):
    # On Windows / Python 2.7, Popen explodes if given unicode strings in the environment.
    if _PY2 and platform.system() == 'Windows':  # pragma: no cover (py2/py3)
        environ_copy = dict()
        for key, value in environ.items():
            assert isinstance(key, basestring)  # noqa
            assert isinstance(key, str)
            if isinstance(value, unicode):  # noqa
                environ_copy[key] = value.encode()
                assert isinstance(environ_copy[key], str)
            elif not isinstance(value, str):
                raise TypeError("Environment contains non-unicode non-str value %r" % value)
            else:
                environ_copy[key] = value
        return environ_copy
    else:  # pragma: no cover (py2/py3)
        return environ
