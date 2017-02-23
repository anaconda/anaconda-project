# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""The SimpleStatus type, a status with no extra info."""
from __future__ import absolute_import

from anaconda_project.status import Status


class SimpleStatus(Status):
    def __init__(self, success, description, logs=(), errors=()):
        self._success = success
        self._description = description
        self._logs = list(logs)
        self._errors = list(errors)

    def __bool__(self):
        return self._success

    def __nonzero__(self):
        return self.__bool__()  # pragma: no cover (py2 only)

    @property
    def status_description(self):
        return self._description

    @property
    def logs(self):
        return self._logs

    @property
    def errors(self):
        return self._errors
