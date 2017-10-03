# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import subprocess

from anaconda_project import verbose


def _log_args(args):
    log = verbose._verbose_logger()
    log.info("$ %s", " ".join(args))


def call(args, **kwargs):
    _log_args(args)
    return subprocess.call(args=args, **kwargs)


def Popen(args, **kwargs):
    _log_args(args)
    return subprocess.Popen(args=args, **kwargs)


def check_output(args, **kwargs):
    _log_args(args)
    return subprocess.check_output(args=args, **kwargs)
