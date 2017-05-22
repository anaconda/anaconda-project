# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
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
