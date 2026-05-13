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
