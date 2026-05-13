# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Tests for pixi_export module."""
from __future__ import absolute_import, print_function

import os
import pytest
import tempfile

from anaconda_project.internal.pixi_export import (
    _conda_spec_to_pixi,
    _strip_conda_prefix_paths,
    _translate_command_env_vars,
    _windows_to_deno_shell,
    export_pixi_toml,
)
from anaconda_project.project import Project


class TestCondaSpecToPixi:
    def test_bare_name(self):
        assert _conda_spec_to_pixi('numpy') == ('numpy', '*')

    def test_gte(self):
        assert _conda_spec_to_pixi('numpy>=1.20') == ('numpy', '>=1.20')

    def test_exact_double_equals(self):
        assert _conda_spec_to_pixi('numpy==1.20') == ('numpy', '==1.20')

    def test_single_equals_glob(self):
        assert _conda_spec_to_pixi('numpy=1.20') == ('numpy', '1.20.*')

    def test_single_equals_with_build(self):
        assert _conda_spec_to_pixi('numpy=1.20.3=py39_0') == ('numpy', '==1.20.3')

    def test_channel_prefix(self):
        assert _conda_spec_to_pixi('conda-forge::numpy') == ('numpy', '*')

    def test_channel_prefix_with_version(self):
        assert _conda_spec_to_pixi('conda-forge::numpy>=1.0') == ('numpy', '>=1.0')

    def test_wildcard_version(self):
        assert _conda_spec_to_pixi('python=3.12.*') == ('python', '3.12.*')

    def test_less_than(self):
        assert _conda_spec_to_pixi('setuptools<82') == ('setuptools', '<82')

    def test_complex_constraint(self):
        assert _conda_spec_to_pixi('bcrypt<5') == ('bcrypt', '<5')


class TestExportPixiToml:
    def _make_project(self, yml_content):
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, 'anaconda-project.yml'), 'w') as f:
            f.write(yml_content)
        return Project(tmpdir)

    def test_simple_project(self):
        project = self._make_project("""
name: Test
description: A test project
packages:
  - numpy
  - pandas>=2.0
channels:
  - defaults
platforms:
  - linux-64
commands:
  run:
    unix: python main.py
""")
        result = export_pixi_toml(project)
        assert 'name = "Test"' in result
        assert 'description = "A test project"' in result
        assert 'numpy = "*"' in result
        assert 'pandas = ">=2.0"' in result
        assert '"defaults"' in result
        assert '"linux-64"' in result
        assert 'run = "python main.py"' in result

    def test_pip_packages(self):
        project = self._make_project("""
name: PipTest
packages:
  - pip:
    - requests>=2.28
    - flask==3.0
platforms:
  - linux-64
""")
        result = export_pixi_toml(project)
        assert '[pypi-dependencies]' in result
        assert 'requests = ">=2.28"' in result
        assert 'flask = "==3.0"' in result

    def test_multi_env(self):
        project = self._make_project("""
name: MultiEnv
packages:
  - python
channels:
  - defaults
env_specs:
  web:
    packages:
      - flask
  ml:
    packages:
      - scikit-learn
platforms:
  - linux-64
""")
        result = export_pixi_toml(project)
        assert '[feature.web.dependencies]' in result
        assert 'flask = "*"' in result
        assert '[feature.ml.dependencies]' in result
        assert 'scikit-learn = "*"' in result
        assert '[environments]' in result

    def test_variables_with_defaults(self):
        project = self._make_project("""
name: VarTest
packages: []
platforms:
  - linux-64
variables:
  DATA_DIR:
    default: /data
""")
        result = export_pixi_toml(project)
        assert '[activation.env]' in result
        assert 'DATA_DIR = "/data"' in result

    def test_bokeh_app_conversion(self):
        project = self._make_project("""
name: BokehTest
packages:
  - bokeh
platforms:
  - linux-64
commands:
  app:
    bokeh_app: myapp
""")
        result = export_pixi_toml(project)
        assert 'bokeh serve myapp' in result
        assert '# converted from bokeh_app' in result

    def test_notebook_conversion(self):
        project = self._make_project("""
name: NbTest
packages: []
platforms:
  - linux-64
commands:
  analysis:
    notebook: analysis.ipynb
""")
        result = export_pixi_toml(project)
        assert 'jupyter notebook analysis.ipynb' in result
        assert '# converted from notebook' in result

    def test_default_channels_when_empty(self):
        project = self._make_project("""
name: NoChan
packages: []
platforms:
  - linux-64
""")
        result = export_pixi_toml(project)
        assert 'channels = ["conda-forge"]' in result

    def test_downloads_as_comments(self):
        project = self._make_project("""
name: DlTest
packages: []
platforms:
  - linux-64
downloads:
  DATASET: https://example.com/data.csv
""")
        result = export_pixi_toml(project)
        assert '# Downloads from anaconda-project.yml' in result
        assert 'DATASET = https://example.com/data.csv' in result

    def test_project_dir_translated(self):
        project = self._make_project("""
name: PdTest
packages: []
platforms:
  - linux-64
commands:
  run:
    unix: python ${PROJECT_DIR}/main.py
""")
        result = export_pixi_toml(project)
        assert '${PIXI_PROJECT_ROOT}/main.py' in result
        assert '${PROJECT_DIR}' not in result

    def test_declared_var_passes_through(self):
        project = self._make_project("""
name: DeclTest
packages: []
platforms:
  - linux-64
variables:
  MY_VAR:
    default: hi
commands:
  run:
    unix: echo ${MY_VAR}
""")
        result = export_pixi_toml(project)
        assert 'echo ${MY_VAR}' in result
        assert 'unresolved env var' not in result

    def test_unknown_var_flagged(self):
        project = self._make_project("""
name: UnknownVar
packages: []
platforms:
  - linux-64
commands:
  run:
    unix: echo ${SOMETHING_RANDOM}
""")
        result = export_pixi_toml(project)
        assert 'unresolved env var(s): SOMETHING_RANDOM' in result


class TestTranslateCommandEnvVars:
    def test_project_dir_braced(self):
        out, unresolved = _translate_command_env_vars('python ${PROJECT_DIR}/x.py', set())
        assert out == 'python ${PIXI_PROJECT_ROOT}/x.py'
        assert unresolved == []

    def test_project_dir_bare(self):
        out, unresolved = _translate_command_env_vars('python $PROJECT_DIR/x.py', set())
        assert out == 'python ${PIXI_PROJECT_ROOT}/x.py'
        assert unresolved == []

    def test_project_dir_windows(self):
        out, unresolved = _translate_command_env_vars('python %PROJECT_DIR%\\x.py', set())
        # ${PIXI_PROJECT_ROOT} is the deno_task_shell-friendly form on every OS.
        assert out == 'python ${PIXI_PROJECT_ROOT}\\x.py'
        assert unresolved == []

    def test_conda_env_path_to_conda_prefix(self):
        out, unresolved = _translate_command_env_vars('${CONDA_ENV_PATH}/bin/foo', set())
        assert out == '${CONDA_PREFIX}/bin/foo'
        assert unresolved == []

    def test_declared_var(self):
        out, unresolved = _translate_command_env_vars('echo $MY_VAR', {'MY_VAR'})
        assert out == 'echo ${MY_VAR}'
        assert unresolved == []

    def test_unknown_var(self):
        out, unresolved = _translate_command_env_vars('echo $WAT', set())
        assert out == 'echo ${WAT}'
        assert unresolved == ['WAT']

    def test_unknown_dedup(self):
        out, unresolved = _translate_command_env_vars('echo $WAT $WAT $OTHER', set())
        assert unresolved == ['WAT', 'OTHER']


class TestWindowsToDenoShell:
    def test_path_with_var(self):
        assert _windows_to_deno_shell('python %PROJECT_DIR%\\hello.py') == \
            'python %PROJECT_DIR%/hello.py'

    def test_dot_relative(self):
        assert _windows_to_deno_shell('python .\\hello.py') == 'python ./hello.py'

    def test_leaves_non_path_tokens_alone(self):
        # A regex literal containing backslashes shouldn't be touched.
        assert _windows_to_deno_shell('grep "a\\nb"') == 'grep "a\\nb"'


class TestUnixWindowsUnification:
    def _make_project(self, yml_content):
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, 'anaconda-project.yml'), 'w') as f:
            f.write(yml_content)
        return Project(tmpdir)

    def test_matching_unix_and_windows_emit_one_task(self):
        project = self._make_project("""
name: Match
packages: []
platforms:
  - linux-64
commands:
  run:
    unix: python ${PROJECT_DIR}/hello.py
    windows: python %PROJECT_DIR%\\hello.py
""")
        result = export_pixi_toml(project)
        assert 'run = "python ${PIXI_PROJECT_ROOT}/hello.py"' in result
        assert 'windows command differs' not in result

    def test_diverging_unix_and_windows_flags_comment(self):
        project = self._make_project("""
name: Diverge
packages: []
platforms:
  - linux-64
commands:
  run:
    unix: python ${PROJECT_DIR}/hello.py
    windows: python %PROJECT_DIR%\\hello_win.py
""")
        result = export_pixi_toml(project)
        assert 'run = "python ${PIXI_PROJECT_ROOT}/hello.py"' in result
        assert 'windows command differs from unix' in result
        assert 'hello_win.py' in result

    def test_windows_only_command_translates(self):
        project = self._make_project("""
name: WinOnly
packages: []
platforms:
  - linux-64
commands:
  run:
    windows: python %PROJECT_DIR%\\hello.py
""")
        result = export_pixi_toml(project)
        assert 'run = "python ${PIXI_PROJECT_ROOT}/hello.py"' in result
        assert 'translated from windows-only command' in result


class TestStripCondaPrefixPaths:
    def test_unix_bin(self):
        assert _strip_conda_prefix_paths('${CONDA_PREFIX}/bin/python x.py') == 'python x.py'

    def test_windows_root_exe(self):
        assert _strip_conda_prefix_paths('${CONDA_PREFIX}/python.exe x.py') == 'python x.py'

    def test_windows_scripts(self):
        assert _strip_conda_prefix_paths('${CONDA_PREFIX}/Scripts/jupyter notebook') == \
            'jupyter notebook'

    def test_windows_library_bin(self):
        assert _strip_conda_prefix_paths('${CONDA_PREFIX}/Library/bin/openssl version') == \
            'openssl version'

    def test_unix_root_without_extension_left_alone(self):
        # ${CONDA_PREFIX}/something — without bin/Scripts/Library and without
        # a .exe-style extension — could be a data file; don't touch it.
        assert _strip_conda_prefix_paths('cat ${CONDA_PREFIX}/conda-meta/history') == \
            'cat ${CONDA_PREFIX}/conda-meta/history'

    def test_pixi_project_root_left_alone(self):
        assert _strip_conda_prefix_paths('python ${PIXI_PROJECT_ROOT}/hello.py') == \
            'python ${PIXI_PROJECT_ROOT}/hello.py'

    def test_strips_at_end_of_string(self):
        assert _strip_conda_prefix_paths('exec ${CONDA_PREFIX}/bin/python') == 'exec python'


class TestEndToEndCondaPrefixUnification:
    def _make_project(self, yml_content):
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, 'anaconda-project.yml'), 'w') as f:
            f.write(yml_content)
        return Project(tmpdir)

    def test_explicit_conda_prefix_paths_unify_across_platforms(self):
        # ${CONDA_PREFIX}/bin/python on unix and %CONDA_PREFIX%\python.exe on
        # windows should both reduce to bare `python`, so we emit one task
        # with no divergence comment.
        project = self._make_project("""
name: PrefixUnify
packages: []
platforms:
  - linux-64
commands:
  run:
    unix: ${CONDA_PREFIX}/bin/python ${PROJECT_DIR}/hello.py
    windows: '%CONDA_PREFIX%\\python.exe %PROJECT_DIR%\\hello.py'
""")
        result = export_pixi_toml(project)
        assert 'run = "python ${PIXI_PROJECT_ROOT}/hello.py"' in result
        assert 'windows command differs' not in result
