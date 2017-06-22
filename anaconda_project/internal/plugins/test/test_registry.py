# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
import os
from anaconda_project.internal.plugins import registry
from unittest.mock import Mock

here = os.path.dirname(__file__)
plugins_path = os.path.join(here, 'assets', 'anaconda-project-plugins')

def test_registry_init(tmpdir):
    plugins_dir = tmpdir.mkdir("test-temp").mkdir('anaconda-project-plugins')
    base_dir = plugins_dir.parts()[-2]
    paths = [base_dir.strpath]
    plugins_registry = registry.PluginRegistry(paths)
    assert plugins_registry.search_paths == paths

def test_scan_paths(monkeypatch):
    create_mock = Mock()
    create_mock.side_effect = ["PluginA", None, "PluginC"]
    monkeypatch.setattr(registry.Plugin, 'create', create_mock)
    paths = ["a", "B", "c"]
    plugins = registry.scan_paths(paths)

    assert plugins == ["PluginA", "PluginC"]
    for arg in paths:
        registry.Plugin.create.assert_any_call(arg)

def test_module_plugin_ok(monkeypatch):
    plugin_name = 'valid_plugin'
    plugin_path = os.path.join(plugins_path, '%s.py' % plugin_name)
    plugin = registry.ModulePlugin(plugin_path)

    assert plugin
    assert plugin.path == plugin_path
    assert plugin.name == plugin_name
    assert not plugin.failed
    assert not plugin.error
    assert not plugin.error_detail

def test_module_plugin_invalid_syntax(monkeypatch):
    plugin_name = 'invalid_syntax_plugin'
    plugin_path = os.path.join(plugins_path, '%s.py' % plugin_name)
    plugin = registry.ModulePlugin(plugin_path)

    default_checks_failed_plugin(plugin, plugin_path, plugin_name)
    assert 'Invalid syntax in "invalid_syntax_plugin.py"' in plugin.error
    assert 'SyntaxError: invalid syntax' in plugin.error_detail

def default_checks_failed_plugin(plugin, plugin_path, plugin_name):
    assert plugin
    assert plugin.path == plugin_path
    assert plugin.name == plugin_name
    assert plugin.failed
    assert plugin.error
    assert plugin.error_detail