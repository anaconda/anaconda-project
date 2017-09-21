# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import

from anaconda_project.frontend import Frontend


class FakeFrontend(Frontend):
    def __init__(self):
        super(FakeFrontend, self).__init__()
        self.logs = []
        self.errors = []

    def info(self, message):
        self.logs.append(message)

    def error(self, message):
        self.errors.append(message)

    def reset(self):
        self.logs = []
        self.errors = []
