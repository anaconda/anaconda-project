# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
import os
from os.path import join

from anaconda_project.test.environ_utils import minimal_environ
from anaconda_project.test.project_utils import project_no_dedicated_env
from anaconda_project.prepare import (prepare_without_interaction)
from anaconda_project.internal.test.tmpfile_utils import (with_directory_contents_completing_project_file)
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME
from anaconda_project import project

from anaconda_project.plugins import CommandTemplate, ArgsTransformerTemplate


def test_prepare_plugin_command(monkeypatch, tmpdir):
    called_with = {}
    cmd_name = 'custom-cmd'
    assert hasattr(project.plugins_api, 'get_plugins')

    def get_plugins_mock(cmd_type):
        return {'valid_package_plugin': plugin_init_mock}

    class TestTransformer(ArgsTransformerTemplate):
        def add_args(self, results, args):
            return ['--show']

    class TestCmd(CommandTemplate):
        args_transformer_cls = TestTransformer
        command = cmd_name

        def choose_args_and_shell(self, environ, extra_args=None):
            assert extra_args is None or isinstance(extra_args, list)

            shell = False
            args = [self.command_with_conda_prefix, 'custom-sub-cmd', '--%s.TESTARG' % self.command]

            return args + extra_args, shell

    def plugin_init_mock(*args, **kws):
        called_with['args'] = args
        called_with['kws'] = kws
        return TestCmd(*args, **kws)

    def check(dirname):
        # do not use monkeypatch
        # since with_directory_contents_completing_project_file
        # monkeypatches zipfile as, that is use by entry_points
        project.plugins_api.get_plugins = get_plugins_mock

        _project = project_no_dedicated_env(dirname)
        environ = minimal_environ()
        result = prepare_without_interaction(_project, environ=environ, command_name='foo')

        cmd_path = join(os.environ['CONDA_PREFIX'], 'bin', cmd_name)
        expected = [cmd_path, 'custom-sub-cmd', '--%s.TESTARG' % cmd_name, '--show']
        assert result.errors == []
        assert result
        assert result.command_exec_info.args == expected

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
commands:
    foo:
       valid_package_plugin: foo.py
packages:
  - notebook
""",
            "foo.py": "# foo",
        }, check)
