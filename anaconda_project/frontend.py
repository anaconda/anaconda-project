# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Frontend class representing a UX."""
from __future__ import absolute_import

from abc import ABCMeta, abstractmethod

from anaconda_project.internal.metaclass import with_metaclass


class Frontend(with_metaclass(ABCMeta)):
    """A UX (CLI, GUI, etc.) for project operations."""

    @abstractmethod
    def info(self, message):
        """Log an info-level message."""
        pass  # pragma: no cover

    @abstractmethod
    def error(self, message):
        """Log an error-level message.

        A rule of thumb is that if a function also returns a
        ``Status``, this message should also be appended to the
        ``errors`` field on that status.
        """
        pass  # pragma: no cover

    # @abstractmethod
    # def new_progress(self):
    #    """Create an appropriate subtype of Progress."""
    #    pass  # pragma: no cover


class NullFrontend(Frontend):
    """A frontend that doesn't do anything."""

    def info(self, message):
        """Log an info-level message."""
        pass

    def error(self, message):
        """Log an error-level message."""
        pass


_singleton_null_frontend = None


def _null_frontend():
    global _singleton_null_frontend
    if _singleton_null_frontend is None:
        _singleton_null_frontend = NullFrontend()
    return _singleton_null_frontend


class _ErrorRecordingFrontendProxy(Frontend):
    def __init__(self, underlying):
        self._errors = []
        self.underlying = underlying

    def info(self, message):
        """Log an info-level message."""
        self.underlying.info(message)

    def error(self, message):
        """Log an error-level message."""
        self._errors.append(message)
        self.underlying.error(message)

    def pop_errors(self):
        result = self._errors
        self._errors = []
        return result


def _new_error_recorder(frontend):
    return _ErrorRecordingFrontendProxy(frontend)
