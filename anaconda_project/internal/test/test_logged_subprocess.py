# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import logging

from anaconda_project import verbose
from anaconda_project.internal import logged_subprocess


class ArrayHandler(logging.Handler):
    def __init__(self):
        super(ArrayHandler, self).__init__(level=logging.DEBUG)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.msg % record.args)


def _test_logger():
    logger = (logging.getLoggerClass())(name="test_logged_subprocess")
    logger.setLevel(logging.DEBUG)
    handler = ArrayHandler()
    logger.addHandler(handler)
    logger.messages = handler.messages
    return logger


def test_log_subprocess_call(monkeypatch):
    recorded = dict(args=(), kwargs=())

    def mock_call(*args, **kwargs):
        recorded['args'] = args
        recorded['kwargs'] = kwargs

    monkeypatch.setattr('subprocess.call', mock_call)

    logged_subprocess.call(['a', 'b'], foo='bar')

    assert recorded == dict(args=(), kwargs=dict(args=['a', 'b'], foo='bar'))


def test_log_subprocess_call_with_logging(monkeypatch):
    logger = _test_logger()
    verbose.push_verbose_logger(logger)
    try:

        recorded = dict(args=(), kwargs=())

        def mock_call(*args, **kwargs):
            recorded['args'] = args
            recorded['kwargs'] = kwargs

        monkeypatch.setattr('subprocess.call', mock_call)

        logged_subprocess.call(['a', 'b'], foo='bar')

        assert recorded == dict(args=(), kwargs=dict(args=['a', 'b'], foo='bar'))

        assert logger.messages == ['$ a b']
    finally:
        verbose.pop_verbose_logger()


def test_log_subprocess_Popen(monkeypatch):
    recorded = dict(args=(), kwargs=())

    def mock_Popen(*args, **kwargs):
        recorded['args'] = args
        recorded['kwargs'] = kwargs

    monkeypatch.setattr('subprocess.Popen', mock_Popen)

    logged_subprocess.Popen(['a', 'b'], foo='bar')

    assert recorded == dict(args=(), kwargs=dict(args=['a', 'b'], foo='bar'))


def test_log_subprocess_Popen_with_logging(monkeypatch):
    logger = _test_logger()
    verbose.push_verbose_logger(logger)
    try:

        recorded = dict(args=(), kwargs=())

        def mock_Popen(*args, **kwargs):
            recorded['args'] = args
            recorded['kwargs'] = kwargs

        monkeypatch.setattr('subprocess.Popen', mock_Popen)

        logged_subprocess.Popen(['a', 'b'], foo='bar')

        assert recorded == dict(args=(), kwargs=dict(args=['a', 'b'], foo='bar'))

        assert logger.messages == ['$ a b']
    finally:
        verbose.pop_verbose_logger()


def test_log_subprocess_check_output(monkeypatch):
    recorded = dict(args=(), kwargs=())

    def mock_check_output(*args, **kwargs):
        recorded['args'] = args
        recorded['kwargs'] = kwargs

    monkeypatch.setattr('subprocess.check_output', mock_check_output)

    logged_subprocess.check_output(['a', 'b'], foo='bar')

    assert recorded == dict(args=(), kwargs=dict(args=['a', 'b'], foo='bar'))


def test_log_subprocess_check_output_with_logging(monkeypatch):
    logger = _test_logger()
    verbose.push_verbose_logger(logger)
    try:

        recorded = dict(args=(), kwargs=())

        def mock_check_output(*args, **kwargs):
            recorded['args'] = args
            recorded['kwargs'] = kwargs

        monkeypatch.setattr('subprocess.check_output', mock_check_output)

        logged_subprocess.check_output(['a', 'b'], foo='bar')

        assert recorded == dict(args=(), kwargs=dict(args=['a', 'b'], foo='bar'))

        assert logger.messages == ['$ a b']
    finally:
        verbose.pop_verbose_logger()
