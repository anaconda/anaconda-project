# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Frontend class representing a UX."""
from __future__ import absolute_import

from abc import ABCMeta, abstractmethod

from anaconda_project.internal.metaclass import with_metaclass


class Frontend(with_metaclass(ABCMeta)):
    """A UX (CLI, GUI, etc.) for project operations."""
    def __init__(self):
        """Construct a Frontend."""
        self._info_buf = ''
        self._error_buf = ''

    def _partial(self, data, buf, line_handler):
        buf = buf + data
        (start, sep, end) = buf.partition('\n')
        while sep != '':
            # we do this instead of using os.linesep in case
            # something on windows outputs unix-style line
            # endings, we don't want to go haywire.  On unix when
            # we actually want \r to carriage return, we'll be
            # overriding this "partial" handler and not using this
            # buffering implementation.
            if start.endswith('\r'):
                start = start[:-1]
            line_handler(start)
            buf = end
            (start, sep, end) = buf.partition('\n')
        return buf

    def partial_info(self, data):
        """Log only part of an info-level line.

        The default implementation buffers this until a line separator
        and then passes the entire line to info().
        Subtypes can override this if they want to print output
        immediately as it arrives.
        """
        self._info_buf = self._partial(data, self._info_buf, self.info)

    def partial_error(self, data):
        """Log only part of an error-level line.

        The default implementation buffers this until a line separator
        and then passes the entire line to error().
        Subtypes can override this if they want to print output
        immediately as it arrives.
        """
        self._error_buf = self._partial(data, self._error_buf, self.error)

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
    def __init__(self):
        """Construct a null frontend."""
        super(NullFrontend, self).__init__()

    def partial_info(self, data):
        """Part of a log message."""
        pass

    def partial_error(self, data):
        """Part of an error message."""
        pass

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
        super(_ErrorRecordingFrontendProxy, self).__init__()
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
