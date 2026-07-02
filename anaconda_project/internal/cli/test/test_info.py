# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2026, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Tests for `anaconda-project info`."""
from __future__ import absolute_import, print_function

import json
import os
import tempfile
import textwrap

from anaconda_project.internal.cli.main import _parse_args_and_run_subcommand


def _write_pixi_toml(d, content):
    path = os.path.join(d, 'pixi.toml')
    with open(path, 'w') as f:
        f.write(content)


def _write_anaconda_project(d, content):
    path = os.path.join(d, 'anaconda-project.yml')
    with open(path, 'w') as f:
        f.write(content)


def _write_conda_toml(d, content):
    path = os.path.join(d, 'conda.toml')
    with open(path, 'w') as f:
        f.write(content)


_PIXI_TOML = textwrap.dedent("""\
    [workspace]
    name = "demo"
    description = "A demo project"
    channels = ["conda-forge"]
    platforms = ["linux-64", "osx-arm64"]

    [dependencies]
    python = ">=3.12"
    flask = "*"

    [tasks]
    serve = "flask run"
""")


class TestInfoText:
    def test_pixi_text_output(self, capsys):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, _PIXI_TOML)
            code = _parse_args_and_run_subcommand(
                ['anaconda-project', 'info', '--directory', td])
            assert code == 0
            out, err = capsys.readouterr()
            assert err == ''
            # Section headers and a few key fields are present.
            assert 'Project' in out
            assert 'Type: pixi' in out
            assert 'Name: demo' in out
            assert 'Description: A demo project' in out
            assert 'Commands' in out
            assert 'Command: serve' in out
            assert 'Environments' in out
            assert 'Environment: default' in out
            assert 'flask' in out
            # No JSON braces leak through.
            assert '{' not in out

    def test_anaconda_project_text_output(self, capsys):
        with tempfile.TemporaryDirectory() as td:
            _write_anaconda_project(td, textwrap.dedent("""\
                name: yml-project
                description: An anaconda-project sample
                env_specs:
                  default:
                    channels: [defaults]
                    packages: [python=3.12, requests]
            """))
            code = _parse_args_and_run_subcommand(
                ['anaconda-project', 'info', '--directory', td])
            assert code == 0
            out, _ = capsys.readouterr()
            assert 'Type: anaconda-project' in out
            assert 'Name: yml-project' in out
            assert 'requests' in out

    def test_missing_manifest_returns_1(self, capsys):
        with tempfile.TemporaryDirectory() as td:
            code = _parse_args_and_run_subcommand(
                ['anaconda-project', 'info', '--directory', td])
            assert code == 1
            _, err = capsys.readouterr()
            assert 'pixi.toml' in err or 'anaconda-project.yml' in err


class TestInfoJson:
    def test_pixi_json_output(self, capsys):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, _PIXI_TOML)
            code = _parse_args_and_run_subcommand(
                ['anaconda-project', 'info', '--directory', td, '--json'])
            assert code == 0
            out, _ = capsys.readouterr()
            data = json.loads(out)
            assert data['name'] == 'demo'
            assert data['project_type'] == 'pixi'
            assert 'serve' in data['commands']
            assert '_pixi' not in data  # only with --env-paths

    def test_json_is_indented(self, capsys):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, _PIXI_TOML)
            _parse_args_and_run_subcommand(
                ['anaconda-project', 'info', '--directory', td, '--json'])
            out, _ = capsys.readouterr()
            # Indented output has at least one '\n  ' (two-space indent).
            assert '\n  ' in out


class TestInfoProjectType:
    def test_force_anaconda_project_when_both_present(self, capsys):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, '[workspace]\nname = "from-pixi"\n')
            _write_anaconda_project(td, 'name: from-yml\n')
            code = _parse_args_and_run_subcommand(
                ['anaconda-project', 'info', '--directory', td,
                 '--project-type', 'anaconda-project', '--json'])
            assert code == 0
            data = json.loads(capsys.readouterr().out)
            assert data['project_type'] == 'anaconda-project'
            assert data['name'] == 'from-yml'

    def test_force_pixi_without_pixi_toml(self, capsys):
        with tempfile.TemporaryDirectory() as td:
            _write_anaconda_project(td, 'name: t\n')
            code = _parse_args_and_run_subcommand(
                ['anaconda-project', 'info', '--directory', td,
                 '--project-type', 'pixi'])
            assert code == 1
            _, err = capsys.readouterr()
            assert 'pixi.toml' in err

    def test_project_type_conda_workspaces_accepted_by_argparse(self, capsys):
        with tempfile.TemporaryDirectory() as td:
            _write_conda_toml(td, '[workspace]\nname = "from-conda"\n')
            code = _parse_args_and_run_subcommand(
                ['anaconda-project', 'info', '--directory', td,
                 '--project-type', 'conda-workspaces', '--json'])
            assert code == 0
            data = json.loads(capsys.readouterr().out)
            assert data['project_type'] == 'conda-workspaces'
            assert data['name'] == 'from-conda'


class TestInfoEnvPaths:
    def test_anaconda_project_env_paths_text(self, capsys):
        with tempfile.TemporaryDirectory() as td:
            _write_anaconda_project(td, textwrap.dedent("""\
                name: t
                env_specs:
                  default:
                    channels: [defaults]
                    packages: [python=3.12]
            """))
            code = _parse_args_and_run_subcommand(
                ['anaconda-project', 'info', '--directory', td, '--env-paths'])
            assert code == 0
            out, _ = capsys.readouterr()
            assert 'Prefix location' in out

    def test_pixi_env_paths_includes_pixi_field(self, capsys, monkeypatch):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, _PIXI_TOML)
            fake_json = json.dumps({
                'platform': 'osx-arm64',
                'environments_info': [
                    {'name': 'default', 'prefix': os.path.join(td, '.pixi/envs/default')},
                ],
            }).encode('utf-8')
            import subprocess
            monkeypatch.setattr(subprocess, 'check_output',
                                lambda cmd, stderr=None: fake_json)
            code = _parse_args_and_run_subcommand(
                ['anaconda-project', 'info', '--directory', td,
                 '--env-paths', '--json'])
            assert code == 0
            data = json.loads(capsys.readouterr().out)
            assert data['env_specs']['default']['path'].endswith('.pixi/envs/default')
            assert data['_pixi']['platform'] == 'osx-arm64'

    def test_pixi_env_paths_subprocess_failure_returns_1(self, capsys, monkeypatch):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, _PIXI_TOML)
            import subprocess

            def boom(cmd, stderr=None):
                raise subprocess.CalledProcessError(1, cmd, stderr=b'pixi: bad manifest')

            monkeypatch.setattr(subprocess, 'check_output', boom)
            code = _parse_args_and_run_subcommand(
                ['anaconda-project', 'info', '--directory', td, '--env-paths'])
            assert code == 1
            _, err = capsys.readouterr()
            assert 'pixi info' in err
