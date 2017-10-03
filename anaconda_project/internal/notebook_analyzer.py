# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2017, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Analyze notebook files."""
from __future__ import absolute_import

import codecs
import json
import re

from anaconda_project.internal.py2_compat import is_string

_comment_re = re.compile("#.*$", re.MULTILINE)
_fusion_register_re = re.compile(r"^\s*@fusion\.register", re.MULTILINE)


# see if some source has @fusion.register. This is
# obviously sort of heuristic, but without executing
# the python we can only do so much.
def _has_fusion_register(source):
    # dump comments so commenting out fusion.register
    # would work as expected
    source = re.sub(_comment_re, "", source)
    return re.match(_fusion_register_re, source) is not None


def extras(filename, errors):
    try:
        with codecs.open(filename, encoding='utf-8') as f:
            json_string = f.read()
            parsed = json.loads(json_string)
    except Exception as e:
        errors.append("Failed to read or parse %s: %s" % (filename, str(e)))
        return None

    extras = dict()
    found_fusion = False

    if isinstance(parsed, dict) and \
       'cells' in parsed and \
       isinstance(parsed['cells'], list):
        for cell in parsed['cells']:
            if 'source' in cell:
                if isinstance(cell['source'], list):
                    source = "".join([s for s in cell['source'] if is_string(s)])
                    if _has_fusion_register(source):
                        found_fusion = True

    if found_fusion:
        extras['registers_fusion_function'] = True

    return extras
