# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import errno
import os


def makedirs_ok_if_exists(path):
    try:
        os.makedirs(path)
    except IOError as e:  # pragma: no cover (py3 only)
        if e.errno != errno.EEXIST:
            raise e
    except OSError as e:  # pragma: no cover (py2 only)
        if e.errno != errno.EEXIST:
            raise e
    return path
