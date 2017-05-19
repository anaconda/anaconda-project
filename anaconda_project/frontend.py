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
        """Log an error-level message."""
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
