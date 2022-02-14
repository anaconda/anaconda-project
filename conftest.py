# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2017, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# (See LICENSE.txt for details)
# -----------------------------------------------------------------------------

import pytest


@pytest.fixture(params=["packages", "dependencies"])
def pkg_key(request, monkeypatch):
    """Ensure equivalence between `dependencies` and `packages`"""
    monkeypatch.setattr('anaconda_project.yaml_file.YamlFile.pkg_key', request.param)
    return request.param
