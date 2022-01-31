# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""The SimpleStatus type, a status with no extra info."""
from __future__ import absolute_import

from anaconda_project.status import Status


class SimpleStatus(Status):
    def __init__(self, success, description, errors=()):
        """Simple Status."""
        self._success = success
        self._description = description
        self._errors = list(errors)

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
