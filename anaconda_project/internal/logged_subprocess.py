# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
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
