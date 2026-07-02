# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Tests for the export-conda project_ops functions (Item 5) and CLI wiring
(Item 7). Placed in a dedicated file (per Item 6's file-placement note)
because these exercise a new surface (project_ops.export_conda /
preview_conda_export, and the export-conda CLI subcommand) beyond the
exporter itself, which is covered in test_pixi_export.py::TestExportCondaToml.
"""
from __future__ import absolute_import, print_function

import os
import tempfile

import pytest

from anaconda_project.internal import pixi_export as pixi_export_module
from anaconda_project.internal.pixi_export import PixiExportStatus
from anaconda_project import project_ops
from anaconda_project.project import Project
from anaconda_project.internal.cli.main import _parse_args_and_run_subcommand


# Use a stable, fake `defaults` expansion across the suite so tests don't
# depend on the developer's local `conda config` and don't shell out to
# conda once per test. Mirrors test_pixi_export.py's autouse fixture.
FAKE_DEFAULTS = ['https://example.test/main', 'https://example.test/r']


@pytest.fixture(autouse=True)
def _stub_default_channels(monkeypatch):
    monkeypatch.setattr(
        pixi_export_module, '_resolve_default_channels',
        lambda: list(FAKE_DEFAULTS),
    )


def _make_project(yml_content):
    tmpdir = tempfile.mkdtemp()
    with open(os.path.join(tmpdir, 'anaconda-project.yml'), 'w') as f:
        f.write(yml_content)
    return Project(tmpdir)


class TestExportCondaProjectOps:
    """project_ops.export_conda / preview_conda_export (Item 5)."""

    def test_export_conda_writes_file(self, tmpdir):
        project = _make_project("""
name: Test
description: A test project
packages:
  - numpy
platforms:
  - linux-64
""")
        target = str(tmpdir.join('conda.toml'))
        status = project_ops.export_conda(project, filename=target)
        assert status
        assert isinstance(status, PixiExportStatus)
        assert os.path.isfile(target)
        with open(target) as f:
            content = f.read()
        assert 'name = "Test"' in content
        assert 'numpy = "*"' in content

    def test_export_conda_status_carries_rename_when_used(self, tmpdir):
        project = _make_project("""
name: ApiRename
packages:
  - python
platforms:
  - linux-64
env_specs:
  sampleproj: {}
""")
        target = str(tmpdir.join('conda.toml'))
        status = project_ops.export_conda(project, filename=target,
                                          use_default=True)
        assert status
        assert status.default_rename_from == 'sampleproj'

    def test_export_conda_status_rename_none_without_flag(self, tmpdir):
        project = _make_project("""
name: NoFlag
packages:
  - python
platforms:
  - linux-64
env_specs:
  sampleproj: {}
""")
        target = str(tmpdir.join('conda.toml'))
        status = project_ops.export_conda(project, filename=target)
        assert status
        assert status.default_rename_from is None

    def test_preview_conda_export_shape(self):
        project = _make_project("""
name: Preview
packages:
  - python
platforms:
  - linux-64
env_specs:
  sampleproj: {}
""")
        result = project_ops.preview_conda_export(project, use_default=True)
        # Stable contract: exactly these four keys, with conda_toml
        # (not pixi_toml) per the rename-only-where-format-differs rule.
        assert set(result) == {
            'conda_toml', 'default_rename_from',
            'current_platform_addition_target', 'warnings',
        }
        assert isinstance(result['conda_toml'], str)
        assert isinstance(result['warnings'], list)
        assert '[dependencies]' in result['conda_toml']
        assert result['default_rename_from'] == 'sampleproj'

    def test_preview_conda_export_matches_pixi_content(self):
        # Per F1, export_conda_toml delegates verbatim to export_pixi_toml,
        # so the two previews should carry identical toml content (modulo
        # the dict key rename).
        project = _make_project("""
name: SameContent
packages:
  - python
platforms:
  - linux-64
""")
        conda_result = project_ops.preview_conda_export(project)
        pixi_result = project_ops.preview_pixi_export(project)
        assert conda_result['conda_toml'] == pixi_result['pixi_toml']

    def test_export_conda_failure_status_on_bad_path(self, tmpdir):
        project = _make_project("""
name: BadPath
packages: []
platforms:
  - linux-64
""")
        # A directory that doesn't exist, so open() fails.
        target = str(tmpdir.join('nonexistent-dir', 'conda.toml'))
        status = project_ops.export_conda(project, filename=target)
        assert not status


class TestExportCondaCli:
    """`anaconda-project export-conda` CLI wiring (Item 7).

    No precedent CLI-level test for `export-pixi` exists in
    anaconda_project/internal/cli/test/ (searched; only test_main.py
    references the subcommand name in its help-text assertions, not an
    invocation test). Per Item 7's gate, a project_ops-level test for
    export_conda/preview_conda_export (above) is sufficient coverage, plus
    this argparse-smoke-test minimum bar: does `export-conda --help` exit 0,
    does the subparser exist, and does a real invocation via the CLI
    entrypoint work end to end.
    """

    def test_export_conda_help_exits_zero(self, capsys):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'export-conda', '--help'])
        assert code == 0
        out, err = capsys.readouterr()
        assert 'CONDA_TOML_FILE' in out
        assert '--use-default' in out
        assert '--add-current-platform' in out

    def test_export_conda_cli_invocation_writes_file(self, tmpdir):
        project_dir = str(tmpdir)
        with open(os.path.join(project_dir, 'anaconda-project.yml'), 'w') as f:
            f.write("""
name: CliTest
packages:
  - python
platforms:
  - linux-64
""")
        code = _parse_args_and_run_subcommand(
            ['anaconda-project', 'export-conda', '--directory', project_dir])
        assert code == 0
        target = os.path.join(project_dir, 'conda.toml')
        assert os.path.isfile(target)
        with open(target) as f:
            content = f.read()
        assert 'name = "CliTest"' in content

    def test_export_conda_cli_with_custom_filename(self, tmpdir):
        project_dir = str(tmpdir)
        with open(os.path.join(project_dir, 'anaconda-project.yml'), 'w') as f:
            f.write("""
name: CustomFile
packages: []
platforms:
  - linux-64
""")
        custom_target = str(tmpdir.join('custom-conda.toml'))
        code = _parse_args_and_run_subcommand(
            ['anaconda-project', 'export-conda', '--directory', project_dir, custom_target])
        assert code == 0
        assert os.path.isfile(custom_target)

    def test_export_conda_cli_project_problems_return_1(self, capsys, tmpdir):
        # An empty directory (no manifest at all) fails project loading /
        # problem checks, mirroring how export-pixi would behave.
        project_dir = str(tmpdir)
        code = _parse_args_and_run_subcommand(
            ['anaconda-project', 'export-conda', '--directory', project_dir])
        assert code == 1
