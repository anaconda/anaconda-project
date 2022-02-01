# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2017, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# (See LICENSE.txt for details)
# -----------------------------------------------------------------------------
import functools

import pytest


@pytest.fixture(params=["packages", "dependencies"])
def pkg_key(request):
    """Ensure equivalence between `dependencies` and `packages`"""
    yield request.param


def _change_default_pkg_key(test_function):
    from anaconda_project.yaml_file import YamlFile

    @functools.wraps(test_function)
    def wrapper(*v, **kw):
        old_pkg_key, YamlFile.pkg_key = YamlFile.pkg_key, kw['pkg_key']
        try:
            return test_function(*v, **kw)
        finally:
            YamlFile.pkg_key = old_pkg_key

    return wrapper


pytest._change_default_pkg_key = _change_default_pkg_key
