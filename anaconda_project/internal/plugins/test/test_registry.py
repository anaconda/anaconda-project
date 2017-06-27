# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
import os
from anaconda_project.internal.plugins import registry

try:  # py3.x
    from unittest.mock import Mock
except ImportError:
    from mock import Mock

here = os.path.dirname(__file__)
plugins_path = os.path.join(here, 'assets', 'anaconda-project-plugins')

BAD_SYNTAX_PLUGIN_CODE = """
class CommandPlugin(object)
    pass
"""

ERROR_PLUGIN_CODE = """
class CommandPlugin(object):
    pass
"""


def write_test_plugin(plugin_name, content, tmpdir, plugin_type='package'):
    tmpplugins = tmpdir.join('anaconda-project-plugins')
    if plugin_type == 'package':
        plugin_path = tmpplugins.join(plugin_name).join("plugin.py")
    else:
        plugin_path = tmpplugins.join("%s.py" % plugin_name)
    plugin_path.write("""
class CommandPlugin(object)
    pass""", ensure=True)
    return str(plugin_path)


def test_registry_init(tmpdir):
    plugins_dir = tmpdir.mkdir("test-temp").mkdir('anaconda-project-plugins')
    base_dir = plugins_dir.parts()[-2]
    paths = [base_dir.strpath]
    plugins_registry = registry.PluginRegistry(paths)
    assert plugins_registry.search_paths == paths


def test_scan_paths(monkeypatch):
    plugins = registry.scan_paths((plugins_path,))

    for plugin in plugins:
        assert plugin.name in ['valid_plugin', 'valid_package_plugin']
    assert plugins[0] != plugins[1]


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


def test_module_plugin_invalid_syntax(monkeypatch, tmpdir):
    plugin_name = 'invalid_syntax_plugin'
    # plugin_path = os.path.join(plugins_path, '%s.py' % plugin_name)
    plugin_path = write_test_plugin(plugin_name, BAD_SYNTAX_PLUGIN_CODE, tmpdir, plugin_type='module')

    plugin = registry.ModulePlugin(plugin_path)

    default_checks_failed_plugin(plugin, plugin_path, plugin_name)
    assert 'Invalid syntax in "%s.py"' % plugin_name in plugin.error
    assert 'SyntaxError: invalid syntax' in plugin.error_detail


def test_package_plugin_ok(monkeypatch):
    plugin_name = 'valid_package_plugin'
    plugin_path = os.path.join(plugins_path, plugin_name)
    plugin = registry.PackagePlugin(plugin_path)

    assert plugin
    assert plugin.path == os.path.join(plugin_path, 'plugin.py')
    assert plugin._package_path == plugin_path
    assert plugin.name == plugin_name
    assert not plugin.failed
    assert not plugin.error
    assert not plugin.error_detail


def test_package_plugin_invalid_syntax(monkeypatch, tmpdir):
    plugin_name = 'invalid_syntax_package_plugin'
    plugin_path = write_test_plugin(plugin_name, BAD_SYNTAX_PLUGIN_CODE, tmpdir)
    plugin_path = os.path.abspath(os.path.join(plugin_path, os.pardir))
    plugin = registry.PackagePlugin(plugin_path)

    check_package_plugin_that_failed(plugin, plugin_path, plugin_name)
    assert 'Invalid syntax in "plugin.py"' in plugin.error
    assert 'SyntaxError: invalid syntax' in plugin.error_detail


def default_checks_failed_plugin(plugin, plugin_path, plugin_name):
    assert plugin
    assert plugin.path == plugin_path
    assert plugin.name == plugin_name
    assert plugin.failed
    assert plugin.error
    assert plugin.error_detail


def check_package_plugin_that_failed(plugin, plugin_path, plugin_name):
    assert plugin
    assert plugin.path == os.path.join(plugin_path, 'plugin.py')
    assert plugin._package_path == plugin_path
    assert plugin.name == plugin_name
    assert plugin.failed
    assert plugin.error
    assert plugin.error_detail
