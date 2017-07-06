# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
import os
from os.path import join

from anaconda_project.test.environ_utils import minimal_environ
from anaconda_project.test.project_utils import project_no_dedicated_env
from anaconda_project.prepare import (prepare_without_interaction)
from anaconda_project.internal.test.tmpfile_utils import (with_directory_contents_completing_project_file)
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME
from anaconda_project import project

from anaconda_project.internal.plugins import registry
from anaconda_project.plugins import CommandTemplate, ArgsTrasformerTemplate

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
    plugins = registry.scan_paths((plugins_path, ))

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

    # Tests related to specific Plugins API implementation
    assert plugin._module.ArgsTransformer
    assert plugin._module.ProjectCommand
    assert plugin._module.ProjectCommand.command == 'custom-cmd'


def test_package_plugin_invalid_syntax(monkeypatch, tmpdir):
    plugin_name = 'invalid_syntax_package_plugin'
    plugin_path = write_test_plugin(plugin_name, BAD_SYNTAX_PLUGIN_CODE, tmpdir)
    plugin_path = os.path.abspath(os.path.join(plugin_path, os.pardir))
    plugin = registry.PackagePlugin(plugin_path)

    check_package_plugin_that_failed(plugin, plugin_path, plugin_name)
    assert 'Invalid syntax in "plugin.py"' in plugin.error
    assert 'SyntaxError: invalid syntax' in plugin.error_detail


def test_prepare_plugin_command(monkeypatch, tmpdir):
    called_with = {}

    def get_plugins_mock():
        return {'valid_package_plugin': plugin_init_mock}

    class TestTransformer(ArgsTrasformerTemplate):
        def add_args(self, results, args):
            return ['--show']

    class TestCmd(CommandTemplate):
        args_transformer_cls = TestTransformer
        command = 'custom-cmd'

        def choose_args_and_shell(self, environ, extra_args=None):
            assert extra_args is None or isinstance(extra_args, list)

            shell = False
            args = [self.command_with_conda_prefix, 'custom-sub-cmd', '--%s.TESTARG' % self.command]

            return args + extra_args, shell

    def plugin_init_mock(*args, **kws):
        called_with['args'] = args
        called_with['kws'] = kws
        return TestCmd(*args, **kws)

    monkeypatch.setattr(project, 'get_plugins', get_plugins_mock)

    def check(dirname):
        project = project_no_dedicated_env(dirname)
        environ = minimal_environ()
        result = prepare_without_interaction(project, environ=environ, command_name='foo')

        cmd_name = 'custom-cmd'
        cmd_path = join(os.environ['CONDA_PREFIX'], 'bin', cmd_name)
        expected = [cmd_path, 'custom-sub-cmd', '--%s.TESTARG' % cmd_name, '--show']
        assert result.errors == []
        assert result
        assert result.command_exec_info.args == expected

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
commands:
    foo:
       valid_package_plugin: foo.py
packages:
  - notebook
""",
         "foo.py": "# foo", }, check)


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
