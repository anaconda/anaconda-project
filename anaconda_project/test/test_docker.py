# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2021, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import subprocess

from anaconda_project.docker import build_image

try:
    FileNotFoundError  # noqa
except NameError:
    # python 2
    FileNotFoundError = OSError


def test_build_image_pass(monkeypatch):
    def mock_check_call(*args, **kwargs):
        return

    monkeypatch.setattr('subprocess.check_call', mock_check_call)

    status = build_image('.', 'tag', 'default')
    assert status


def test_build_image_extra_args(monkeypatch):
    def mock_check_call(*args, **kwargs):
        return

    monkeypatch.setattr('subprocess.check_call', mock_check_call)

    status = build_image('.', 'tag', 'default', build_args={'-f': 'Dockerfile'})
    assert status


def test_build_image_failed(monkeypatch):
    def mock_check_call(*args, **kwargs):
        raise subprocess.CalledProcessError(1, 's2i', 'failed to build')

    monkeypatch.setattr('subprocess.check_call', mock_check_call)

    status = build_image('.', 'tag', 'default')
    assert len(status.errors) == 1


def test_build_image_not_found(monkeypatch):
    def mock_check_call(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr('subprocess.check_call', mock_check_call)

    status = build_image('.', 'tag', 'default')
    assert len(status.errors) == 1
