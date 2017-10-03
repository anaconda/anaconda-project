# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Control verbose output."""
from __future__ import absolute_import

import logging

_verbose_loggers = []


def push_verbose_logger(logger):
    """Push a logger to log verbose messgaes."""
    global _verbose_loggers
    _verbose_loggers.append(logger)


def pop_verbose_logger():
    """Remove the most recently-pushed verbose logger."""
    global _verbose_loggers
    assert len(_verbose_loggers) > 0
    _verbose_loggers.pop()


_cached_null_logger = None


def _null_logger():
    global _cached_null_logger
    if _cached_null_logger is None:
        logger = logging.getLogger(name='anaconda_project_null')
        logger.addHandler(logging.NullHandler())
        _cached_null_logger = logger
    return _cached_null_logger


def _verbose_logger():
    """Used internal to anaconda-project library to get the current verbose logger."""
    if len(_verbose_loggers) > 0:
        return _verbose_loggers[-1]
    else:
        return _null_logger()
