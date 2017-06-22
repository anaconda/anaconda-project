# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from anaconda_project.internal.plugins import registry
from unittest.mock import Mock


def test_registry_init(tmpdir):
    plugins_dir = tmpdir.mkdir("test-temp").mkdir('anaconda-project-plugins')
    base_dir = plugins_dir.parts()[-2]
    paths = [base_dir.strpath]
    plugins_registry = registry.PluginRegistry(paths)
    assert plugins_registry.search_paths == paths


def test_scan_paths(monkeypatch):
    monkeypatch.setattr(registry.Plugin, 'create', Mock())
    paths = ["a", "B", "c"]
    plugins = registry.scan_paths(paths)

    for arg in paths:
        registry.Plugin.create.assert_any_call(arg)
