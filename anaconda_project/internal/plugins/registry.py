# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""The plugin registry (used to locate plugins)."""
from __future__ import absolute_import, print_function

from collections import namedtuple

ServiceType = namedtuple('ServiceType', ['name', 'default_variable', 'description'])


class PluginCatalog(object):
    """Scans and manages plugins discoverable in a plugins path list."""
