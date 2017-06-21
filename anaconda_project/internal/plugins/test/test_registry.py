# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from anaconda_project.internal.plugins.registry import PluginRegistry


def test_registry_init(tmpdir):
    plugins_dir = tmpdir.mkdir("test-temp").mkdir('anaconda-project-plugins')
    base_dir = plugins_dir.parts()[-2]
    paths = [base_dir.strpath]
    registry = PluginRegistry(paths)
    assert registry.search_paths == paths
