# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""The SimpleStatus type, a status with no extra info."""
from __future__ import absolute_import

import warnings

from anaconda_project.status import Status


class SimpleStatus(Status):
    def __init__(self, success, description, logs=(), errors=()):
        self._success = success
        self._description = description
        self._errors = list(errors)
        if len(logs) > 0:
            warnings.warn("Don't pass logs to SimpleStatus", DeprecationWarning)

    def __bool__(self):
        return self._success

    def __nonzero__(self):
        return self.__bool__()  # pragma: no cover (py2 only)

    @property
    def status_description(self):
        return self._description

    @property
    def errors(self):
        return self._errors
