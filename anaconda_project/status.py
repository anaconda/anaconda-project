# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""The Status type."""
from __future__ import absolute_import

from abc import ABCMeta, abstractmethod

from anaconda_project.internal.metaclass import with_metaclass


class Status(with_metaclass(ABCMeta)):
    """Class describing a failure or success status, with logs.

    Values of this class evaluate to True in a boolean context
    if the status is successful.

    Values of this class are immutable.

    """

    def __init__(self):
        """Construct an abstract Status."""

    @property
    @abstractmethod
    def status_description(self):
        """Get a one-line-ish description of the status."""
        pass  # pragma: no cover

    @property
    @abstractmethod
    def logs(self):
        """Get logs relevant to the status."""
        pass  # pragma: no cover

    @property
    @abstractmethod
    def errors(self):
        """Get error logs relevant to the status."""
        pass  # pragma: no cover
