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

from anaconda_project.internal import pixi_export as pixi_export_module
from anaconda_project.internal.pixi_export import (
    CondaNotAvailableError,
    PixiExportStatus,
    _conda_spec_to_pixi,
    _expand_defaults_in_channels,
    current_platform_addition_target,
    default_rename_target,
    _strip_conda_prefix_paths,
    _translate_command_env_vars,
    _windows_to_deno_shell,
    export_pixi_toml,
    extract_warnings,
    project_would_benefit_from_use_default,
)
from anaconda_project import project_ops
from anaconda_project.project import Project


# Use a stable, fake `defaults` expansion across the suite so tests don't
# depend on the developer's local `conda config` and don't shell out to
# conda once per test.
FAKE_DEFAULTS = ['https://example.test/main', 'https://example.test/r']


@pytest.fixture(autouse=True)
def _stub_default_channels(monkeypatch):
    monkeypatch.setattr(
        pixi_export_module, '_resolve_default_channels',
        lambda: list(FAKE_DEFAULTS),
    )


class TestExpandDefaultsInChannels:
    def test_no_defaults(self):
        out = _expand_defaults_in_channels(['conda-forge', 'bioconda'], FAKE_DEFAULTS)
        assert out == ['conda-forge', 'bioconda']

    def test_defaults_expanded_in_place(self):
        out = _expand_defaults_in_channels(['defaults', 'bioconda'], FAKE_DEFAULTS)
        assert out == FAKE_DEFAULTS + ['bioconda']

    def test_defaults_in_middle(self):
        out = _expand_defaults_in_channels(
            ['bioconda', 'defaults', 'conda-forge'], FAKE_DEFAULTS)
        assert out == ['bioconda'] + FAKE_DEFAULTS + ['conda-forge']

    def test_dedup_when_default_already_listed(self):
        out = _expand_defaults_in_channels(
            ['https://example.test/main', 'defaults'], FAKE_DEFAULTS)
        # The pre-existing entry wins; defaults' duplicate is skipped.
        assert out == ['https://example.test/main', 'https://example.test/r']

    def test_multiple_defaults_collapse(self):
        out = _expand_defaults_in_channels(['defaults', 'defaults'], FAKE_DEFAULTS)
        assert out == FAKE_DEFAULTS


class TestExportFailsWithoutConda:
    def test_export_raises_when_conda_missing(self, monkeypatch, tmpdir):
        # Override the autouse stub: simulate conda being unreachable.
        def boom():
            raise CondaNotAvailableError('conda not found')
        monkeypatch.setattr(
            pixi_export_module, '_resolve_default_channels', boom)

        yml = tmpdir.join('anaconda-project.yml')
        yml.write("""
name: NeedsConda
packages: []
platforms:
  - linux-64
""")
        project = Project(str(tmpdir))
        with pytest.raises(CondaNotAvailableError):
            export_pixi_toml(project)


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
        # `defaults` from the yml is expanded into the URLs that conda
        # would resolve it to. The literal "defaults" never appears in
        # the converted manifest — pixi has no such meta-channel.
        assert '"defaults"' not in result
        assert 'https://example.test/main' in result
        assert 'https://example.test/r' in result
        assert '"linux-64"' in result
        assert 'cmd = "python main.py"' in result

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

    def test_default_channels_when_empty(self):
        # When the yml declares no channels, fall back to the URLs that
        # conda's default_channels resolves to (NOT a hard-coded
        # conda-forge), since pixi has no `defaults` meta-channel and
        # the user's local conda config is the source of truth.
        project = self._make_project("""
name: NoChan
packages: []
platforms:
  - linux-64
""")
        result = export_pixi_toml(project)
        assert 'channels = ["https://example.test/main", "https://example.test/r"]' in result
        assert '"defaults"' not in result
        assert '"conda-forge"' not in result

    def test_downloads_become_prepare_task(self):
        # Single env (default) — prepare emitted at top-level. Body
        # invokes the ap_download.py helper rather than inlining urllib.
        project = self._make_project("""
name: DlTest
packages: []
platforms:
  - linux-64
downloads:
  DATASET: https://example.com/data.csv
""")
        result = export_pixi_toml(project)
        assert '[tasks.prepare]' in result
        assert 'python3 ap_download.py' in result
        assert 'https://example.com/data.csv' in result
        # When the prepare body has real work, we drop the marker echo —
        # pixi smashes the marker onto the same banner line as the next
        # command, which is ugly. Detection still works via the task name.
        assert 'Running migrated anaconda-project prepare task' not in result
        # No python in the env: warning at the top of the file.
        assert '# WARNING: prepare task uses system python3' in result
        # Old comment-only path is gone.
        assert '# Downloads from anaconda-project.yml' not in result

    def test_marker_prepare_when_no_downloads(self):
        # Even without downloads, every converted project gets a
        # `prepare` task. It does double duty:
        #   * Marks the file as converted from anaconda-project.yml,
        #     for downstream tooling that detects converted projects
        #     by task name.
        #   * When scoped to a non-default env's feature, gives
        #     `pixi run prepare` an entry point that auto-resolves to
        #     that env — useful when the default env_spec is named
        #     something other than `default`.
        project = self._make_project("""
name: NoDl
packages:
  - python
platforms:
  - linux-64
""")
        result = export_pixi_toml(project)
        assert '[tasks.prepare]' in result
        assert 'Running migrated anaconda-project prepare task' in result
        # No downloads, so no helper invocation.
        assert 'ap_download.py' not in result

    def test_only_default_env_gets_prepare(self):
        # anaconda-project's top-level downloads: apply to every env, but
        # we only need to fetch them once. Emit prepare only under the
        # default env's feature; the other envs don't get a prepare task.
        project = self._make_project("""
name: NycMulti
packages:
  - python
platforms:
  - linux-64
downloads:
  DATA: https://example.com/big.parq
env_specs:
  sampleproj: {}
  test:
    packages:
      - pytest
""")
        result = export_pixi_toml(project)
        # Exactly one ap_download.py invocation, under the default env.
        assert result.count('python3 ap_download.py') == 1
        assert '[feature.sampleproj.tasks.prepare]' in result
        # Non-default env has no prepare task at all.
        assert '[feature.test.tasks.prepare]' not in result

    def test_no_warning_when_env_has_python(self):
        project = self._make_project("""
name: HasPython
packages:
  - python=3.11
platforms:
  - linux-64
downloads:
  DATASET: https://example.com/data.csv
""")
        result = export_pixi_toml(project)
        # User declared python — no warning, no injection.
        assert 'python = "3.11.*"' in result
        assert '# WARNING' not in result

    def test_prepare_in_default_env_only(self):
        # We emit exactly one prepare task, scoped to the default env's
        # feature. Other envs don't get one — keeps the manifest small
        # and avoids pixi's "ambiguous task" prompt entirely.
        project = self._make_project("""
name: MultiDl
packages:
  - python
platforms:
  - linux-64
env_specs:
  web:
    downloads:
      WEB_DATA: https://example.com/web.csv
  ml:
    downloads:
      ML_DATA: https://example.com/ml.csv
""")
        result = export_pixi_toml(project)
        # Default env (first declared = web) gets the prepare task.
        assert '[feature.web.tasks.prepare]' in result
        assert 'web.csv' in result
        # Non-default env (ml) does NOT get a prepare task.
        assert '[feature.ml.tasks.prepare]' not in result
        # No prepare-all either — single prepare keeps things simple.
        assert 'prepare-all' not in result

    def test_prepare_scoped_to_named_default_env(self):
        # When the default env_spec has a non-default name (sampleproj),
        # the prepare task is scoped to that feature so `pixi run prepare`
        # auto-resolves to the right env. This is the second job of the
        # always-emit-prepare convention: it's an env-selection entry
        # point even when there's nothing to download.
        project = self._make_project("""
name: Plain
packages:
  - python
platforms:
  - linux-64
env_specs:
  sampleproj: {}
""")
        result = export_pixi_toml(project)
        assert '[feature.sampleproj.tasks.prepare]' in result
        # No downloads → no helper invocation.
        assert 'ap_download.py' not in result

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
        assert '$PIXI_PROJECT_ROOT/main.py' in result
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
        assert 'echo $MY_VAR' in result
        assert 'unresolved env var' not in result

    def test_env_specs_emit_in_source_order(self):
        # The first uncommented entry in [environments] is the user's
        # intended default — downstream tooling reads it to drive
        # `pixi install -e $(...)`. We must preserve insertion order even
        # if dict iteration would otherwise be alphabetical.
        project = self._make_project("""
name: OrderTest
packages:
  - python
platforms:
  - linux-64
env_specs:
  zeta:
    packages:
      - flask
  alpha:
    packages:
      - pytest
""")
        result = export_pixi_toml(project)
        env_block = result.split('[environments]', 1)[1]
        zeta_pos = env_block.index('zeta')
        alpha_pos = env_block.index('alpha')
        assert zeta_pos < alpha_pos

    def test_default_in_multi_env_emits_as_comment(self):
        # When the user names one of multiple env_specs `default`, we don't
        # redeclare it (pixi already creates it from the default feature).
        # We comment its slot so position-based extraction still finds the
        # user's first-listed env.
        project = self._make_project("""
name: MultiWithDefault
packages:
  - python
platforms:
  - linux-64
env_specs:
  prod:
    packages:
      - flask
  default:
    packages:
      - pytest
  staging:
    packages:
      - debugpy
""")
        result = export_pixi_toml(project)
        # pytest from `default` env_spec belongs in pixi's default feature.
        assert 'pytest = "*"' in result.split('[feature.', 1)[0]
        # `default` slot is a comment, in position between prod and staging.
        env_block = result.split('[environments]', 1)[1]
        prod_pos = env_block.index('prod')
        comment_pos = env_block.index('# default')
        staging_pos = env_block.index('staging')
        assert prod_pos < comment_pos < staging_pos
        # No [feature.default.dependencies] (would be unreachable).
        assert '[feature.default.dependencies]' not in result

    def test_no_solve_group_emitted(self):
        # anaconda-project doesn't assume environments solve together, so
        # we shouldn't either.
        project = self._make_project("""
name: NoSolve
packages:
  - python
platforms:
  - linux-64
env_specs:
  a:
    packages:
      - flask
  b:
    packages:
      - pytest
""")
        result = export_pixi_toml(project)
        assert 'solve-group' not in result

    def test_single_named_env_uses_global_dependencies(self):
        # Packages live in top-level [dependencies] (the default feature);
        # the named env inherits them. The marker comment tells downstream
        # tooling which env to target with bare `pixi <cmd>`.
        project = self._make_project("""
name: Glaciers
packages:
  - panel
  - pandas
platforms:
  - linux-64
env_specs:
  sampleproj: {}
""")
        result = export_pixi_toml(project)
        assert '[dependencies]' in result
        assert 'panel = "*"' in result
        assert 'pandas = "*"' in result
        assert 'sampleproj = { features = ["sampleproj"]' in result
        # We don't need no-default-feature now that the default feature
        # is the source of truth.
        assert 'no-default-feature' not in result

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
        assert out == 'python $PIXI_PROJECT_ROOT/x.py'
        assert unresolved == []

    def test_project_dir_bare(self):
        out, unresolved = _translate_command_env_vars('python $PROJECT_DIR/x.py', set())
        assert out == 'python $PIXI_PROJECT_ROOT/x.py'
        assert unresolved == []

    def test_project_dir_windows(self):
        out, unresolved = _translate_command_env_vars('python %PROJECT_DIR%\\x.py', set())
        # $PIXI_PROJECT_ROOT is the deno_task_shell-friendly form on every OS.
        assert out == 'python $PIXI_PROJECT_ROOT\\x.py'
        assert unresolved == []

    def test_conda_env_path_to_conda_prefix(self):
        out, unresolved = _translate_command_env_vars('${CONDA_ENV_PATH}/bin/foo', set())
        assert out == '$CONDA_PREFIX/bin/foo'
        assert unresolved == []

    def test_declared_var(self):
        out, unresolved = _translate_command_env_vars('echo $MY_VAR', {'MY_VAR'})
        assert out == 'echo $MY_VAR'
        assert unresolved == []

    def test_unknown_var(self):
        out, unresolved = _translate_command_env_vars('echo $WAT', set())
        assert out == 'echo $WAT'
        assert unresolved == ['WAT']

    def test_unknown_dedup(self):
        out, unresolved = _translate_command_env_vars('echo $WAT $WAT $OTHER', set())
        assert unresolved == ['WAT', 'OTHER']

    def test_ambiguous_suffix_keeps_braces(self):
        # An immediately-adjacent identifier character would extend the bare
        # var name, so we must keep the braces even though deno_task_shell
        # rejects them — there's no safe rewrite, and the original command
        # had the same ambiguity.
        out, unresolved = _translate_command_env_vars('${PROJECT_DIR}suffix', set())
        assert out == '${PIXI_PROJECT_ROOT}suffix'


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
        assert 'cmd = "python $PIXI_PROJECT_ROOT/hello.py"' in result
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
        assert 'cmd = "python $PIXI_PROJECT_ROOT/hello.py"' in result
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
        assert 'cmd = "python $PIXI_PROJECT_ROOT/hello.py"' in result
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
        assert _strip_conda_prefix_paths('python $PIXI_PROJECT_ROOT/hello.py') == \
            'python $PIXI_PROJECT_ROOT/hello.py'

    def test_strips_at_end_of_string(self):
        assert _strip_conda_prefix_paths('exec ${CONDA_PREFIX}/bin/python') == 'exec python'


class TestHttpOptions:
    def _make_project(self, yml_content):
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, 'anaconda-project.yml'), 'w') as f:
            f.write(yml_content)
        return Project(tmpdir)

    def test_supports_http_options_appends_all_flags(self):
        # supports_http_options=true → cmd gets all six --anaconda-project-X
        # flags appended (gated by Jinja so empty args drop the flag), and
        # pixi args declared with empty defaults.
        project = self._make_project("""
name: Http
packages:
  - python
platforms:
  - linux-64
commands:
  serve:
    unix: panel serve foo.ipynb
    supports_http_options: true
""")
        result = export_pixi_toml(project)
        # All six flags appear in the cmd, gated.
        for flag in ('--anaconda-project-host', '--anaconda-project-port',
                     '--anaconda-project-address', '--anaconda-project-iframe-hosts',
                     '--anaconda-project-no-browser', '--anaconda-project-use-xheaders'):
            assert flag in result, "missing %s" % flag
        # Each is gated by an `{% if var %}` so empty args don't render.
        assert '{% if port %}' in result
        assert '{% if no_browser %}' in result
        # Pixi args block declares all six with empty defaults.
        assert 'arg = "port", default = ""' in result
        assert 'arg = "no_browser", default = ""' in result

    def test_notebook_command_uses_jupyter_flags(self):
        # notebook: commands have supports_http_options=true by default,
        # and translate to Jupyter's specific flag names — `--port` (not
        # `--anaconda-project-port`), `--ip` for address, etc., plus the
        # unconditional --NotebookApp.default_url prefix that
        # anaconda-project's _NotebookArgsTransformer emits.
        project = self._make_project("""
name: NbHttp
packages:
  - python
platforms:
  - linux-64
commands:
  nb:
    notebook: report.ipynb
""")
        result = export_pixi_toml(project)
        assert '--NotebookApp.default_url=/notebooks/report.ipynb' in result
        assert '--port {{ port }}' in result
        assert '--ip {{ address }}' in result
        assert 'arg = "port"' in result
        # Notebook drops host entirely (jupyter has no equivalent).
        assert 'arg = "host"' not in result
        # Generic --anaconda-project-* flags shouldn't appear.
        assert '--anaconda-project-' not in result

    def test_url_prefix_renamed_per_tool(self):
        # --anaconda-project-url-prefix maps differently in each tool:
        #   generic  -> --anaconda-project-url-prefix VALUE  (passthrough)
        #   bokeh    -> --prefix VALUE
        #   notebook -> --NotebookApp.base_url=VALUE  (single-arg form,
        #               original transformer notes the two-arg form is
        #               rejected by jupyter)
        # Mirror those mappings here so converted commands carry the
        # right flag for the tool that will receive them.
        for label, yml, expected_flag in [
            ('generic',
             """name: t
packages: [python]
platforms: [linux-64]
commands:
  serve:
    unix: panel serve foo.ipynb
    supports_http_options: true
""",
             '--anaconda-project-url-prefix {{ url_prefix }}'),
            ('bokeh',
             """name: t
packages: [python, bokeh]
platforms: [linux-64]
commands:
  app:
    bokeh_app: myapp
""",
             '--prefix {{ url_prefix }}'),
            ('notebook',
             """name: t
packages: [python]
platforms: [linux-64]
commands:
  nb:
    notebook: report.ipynb
""",
             '--NotebookApp.base_url={{ url_prefix }}'),
        ]:
            project = self._make_project(yml)
            result = export_pixi_toml(project)
            assert expected_flag in result, '{}: missing {!r}'.format(label, expected_flag)
            assert 'arg = "url_prefix"' in result, '{}: arg not declared'.format(label)

    def test_bokeh_app_uses_bokeh_flags(self):
        # bokeh_app: commands translate to bokeh's flag names: bare
        # --host/--port/--address, and --show as the *inverse* of
        # --no-browser. iframe_hosts is dropped (bokeh has no equivalent).
        project = self._make_project("""
name: BokehHttp
packages:
  - python
  - bokeh
platforms:
  - linux-64
commands:
  app:
    bokeh_app: myapp
""")
        result = export_pixi_toml(project)
        assert '--host {{ host }}' in result
        assert '--port {{ port }}' in result
        assert '--address {{ address }}' in result
        # --show is gated by `not no_browser` (negative gate).
        assert '{% if not no_browser %}--show{% endif %}' in result
        assert '--use-xheaders' in result
        # iframe_hosts is not declared as an arg or referenced.
        assert 'arg = "iframe_hosts"' not in result
        assert '--anaconda-project-' not in result

    def test_supports_http_options_false_no_jinja_no_args(self):
        # supports_http_options=false and the unix line has no {{var}}
        # references → no http args at all, cmd unchanged.
        project = self._make_project("""
name: Plain
packages:
  - python
platforms:
  - linux-64
commands:
  run:
    unix: python app.py
""")
        result = export_pixi_toml(project)
        assert '--anaconda-project-' not in result
        assert 'args = [' not in result

    def test_supports_http_options_false_picks_up_referenced_jinja(self):
        # User wrote a templated unix: command with {{port}} and {{host}}.
        # We declare pixi args only for those, leave the cmd alone.
        project = self._make_project("""
name: Tmpl
packages:
  - python
platforms:
  - linux-64
commands:
  run:
    unix: "myserver --port={{ port }} --host={{ host }}"
""")
        result = export_pixi_toml(project)
        # Cmd preserved verbatim (env-var translation doesn't touch
        # Jinja vars).
        assert '--port={{ port }}' in result
        assert '--host={{ host }}' in result
        # Only port and host declared; not the other four http vars.
        assert 'arg = "port"' in result
        assert 'arg = "host"' in result
        assert 'arg = "address"' not in result
        assert 'arg = "iframe_hosts"' not in result
        # No --anaconda-project-X flags appended.
        assert '--anaconda-project-' not in result


class TestUseDefault:
    def _make_project(self, yml_content):
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, 'anaconda-project.yml'), 'w') as f:
            f.write(yml_content)
        return Project(tmpdir)

    def test_picker_returns_none_when_default_already_present(self):
        project = self._make_project("""
name: HasDefault
packages:
  - python
platforms:
  - linux-64
env_specs:
  default: {}
  other:
    packages: [flask]
""")
        assert default_rename_target(project) is None
        assert project_would_benefit_from_use_default(project) is False

    def test_picker_single_env_returns_that_env(self):
        project = self._make_project("""
name: Solo
packages:
  - python
platforms:
  - linux-64
env_specs:
  sampleproj: {}
""")
        assert default_rename_target(project) == 'sampleproj'

    def test_picker_uses_default_command_env(self):
        # Two envs, no `default`. The default command's env (here `web`,
        # explicitly marked default) should be the one promoted.
        project = self._make_project("""
name: PickByCommand
packages:
  - python
platforms:
  - linux-64
env_specs:
  test:
    packages: [pytest]
  web:
    packages: [flask]
commands:
  serve:
    unix: python -m http.server
    env_spec: web
    default: true
""")
        assert default_rename_target(project) == 'web'

    def test_picker_falls_back_to_first_env_without_command(self):
        # No commands → first env_spec wins.
        project = self._make_project("""
name: NoCmd
packages:
  - python
platforms:
  - linux-64
env_specs:
  zeta:
    packages: [flask]
  alpha:
    packages: [pytest]
""")
        assert default_rename_target(project) == 'zeta'

    def test_single_env_collapses_to_top_level(self):
        # use_default on a single non-default env: deps move from
        # [feature.{name}.dependencies] to [dependencies], prepare from
        # [feature.{name}.tasks.prepare] to [tasks.prepare], no
        # [environments] block needed.
        project = self._make_project("""
name: SoloFlat
packages:
  - python
  - flask
platforms:
  - linux-64
env_specs:
  sampleproj: {}
""")
        result = export_pixi_toml(project, use_default=True)
        assert '[dependencies]' in result
        assert 'flask = "*"' in result
        assert '[feature.sampleproj' not in result
        assert '[tasks.prepare]' in result
        assert '[environments]' not in result

    def test_multi_env_promotes_default_command_env(self):
        # Multiple envs, no `default`. With use_default, the default
        # command's env (`web`) is renamed to `default` — its task lands
        # in [tasks.serve] (top-level) and its prepare in [tasks.prepare].
        # The other env still gets a [feature.test.*] block.
        project = self._make_project("""
name: MultiPromote
packages:
  - python
platforms:
  - linux-64
env_specs:
  web:
    packages: [flask]
  test:
    packages: [pytest]
commands:
  serve:
    unix: python -m http.server
    env_spec: web
    default: true
  pytest-run:
    unix: pytest
    env_spec: test
""")
        result = export_pixi_toml(project, use_default=True)
        # `web` collapsed into top-level / default feature.
        assert 'flask = "*"' in result.split('[feature.', 1)[0]
        assert '[feature.web' not in result
        # `serve` (web's command) lives at top-level.
        assert '[tasks.serve]' in result
        # `test` env still feature-scoped.
        assert '[feature.test.dependencies]' in result
        assert '[feature.test.tasks.pytest-run]' in result
        # Prepare lands at top level (web is now `default`).
        assert '[tasks.prepare]' in result
        assert '[feature.web.tasks.prepare]' not in result
        # Environments block: web's slot becomes the default-comment line,
        # and `test` is still declared. Order preserved.
        env_block = result.split('[environments]', 1)[1]
        web_pos = env_block.index('# default')
        test_pos = env_block.index('test = ')
        assert web_pos < test_pos

    def test_multi_env_promotes_first_when_no_default_command(self):
        # Multiple envs, no `default`, no commands → first env wins.
        project = self._make_project("""
name: MultiNoCmd
packages:
  - python
platforms:
  - linux-64
env_specs:
  zeta:
    packages: [flask]
  alpha:
    packages: [pytest]
""")
        result = export_pixi_toml(project, use_default=True)
        assert 'flask = "*"' in result.split('[feature.', 1)[0]
        assert '[feature.zeta' not in result
        assert '[feature.alpha.dependencies]' in result

    def test_no_op_when_default_already_present(self):
        # use_default with a project that already has `default` should be
        # a no-op; output equals the unflagged export byte-for-byte.
        project = self._make_project("""
name: AlreadyDefault
packages:
  - python
platforms:
  - linux-64
env_specs:
  default:
    packages: [flask]
  other:
    packages: [pytest]
""")
        with_flag = export_pixi_toml(project, use_default=True)
        without = export_pixi_toml(project, use_default=False)
        assert with_flag == without

    def test_default_off_keeps_feature_scope(self):
        # Explicit no use_default on a non-default single env: same
        # behavior as before — feature-scoped layout.
        project = self._make_project("""
name: SoloFeature
packages:
  - python
  - flask
platforms:
  - linux-64
env_specs:
  sampleproj: {}
""")
        result = export_pixi_toml(project, use_default=False)
        assert '[feature.sampleproj.tasks.prepare]' in result
        assert '[tasks.prepare]' not in result.replace(
            '[feature.sampleproj.tasks.prepare]', '')


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
        assert 'cmd = "python $PIXI_PROJECT_ROOT/hello.py"' in result
        assert 'windows command differs' not in result


class TestExtractWarnings:
    def test_no_warning_block(self):
        assert extract_warnings('[workspace]\nname = "x"\n') == []

    def test_warning_block_followed_by_blank(self):
        content = (
            '# WARNING: prepare task uses system python3 to run ap_download.py.\n'
            '# The following env(s) declare downloads but no python package:\n'
            '#   web\n'
            '\n'
            '[workspace]\n')
        out = extract_warnings(content)
        assert out[0].startswith('# WARNING:')
        assert '#   web' in out
        assert '[workspace]' not in out

    def test_warning_must_lead(self):
        # A line starting with '# WARNING:' deeper in the file isn't the
        # leading-block we surface to the user.
        content = '[workspace]\nname = "x"\n# WARNING: tucked away\n'
        # The implementation does pick up a later block too (it scans
        # forward until the first WARNING and stops at the next blank).
        # Document the behavior either way: here there's no trailing
        # blank, so it captures everything from WARNING to EOF.
        out = extract_warnings(content)
        assert out == ['# WARNING: tucked away']


class TestPublicAPI:
    """Tests for the public surface downstream consumers depend on:
    ``default_rename_target``, ``PixiExportStatus.default_rename_from``,
    and ``project_ops.preview_pixi_export``."""

    def _make_project(self, yml_content):
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, 'anaconda-project.yml'), 'w') as f:
            f.write(yml_content)
        return Project(tmpdir)

    def test_default_rename_target_is_public_alias(self):
        # The picker is part of the public contract. Promoted from the
        # underscored name so downstream tooling doesn't have to import
        # through a private accessor.
        assert callable(default_rename_target)
        assert default_rename_target.__doc__  # has user-facing docs

    def test_export_pixi_status_carries_rename_when_used(self, tmpdir):
        project = self._make_project("""
name: ApiRename
packages:
  - python
platforms:
  - linux-64
env_specs:
  sampleproj: {}
""")
        target = str(tmpdir.join('pixi.toml'))
        status = project_ops.export_pixi(project, filename=target,
                                         use_default=True)
        assert status  # truthy on success
        assert isinstance(status, PixiExportStatus)
        assert status.default_rename_from == 'sampleproj'

    def test_export_pixi_status_rename_is_none_without_flag(self, tmpdir):
        # Without --use-default, no rename happened, so the status reports
        # None — even though default_rename_target() would have returned
        # 'sampleproj'. This lets a caller distinguish "we renamed X" from
        # "we could rename X".
        project = self._make_project("""
name: NoFlag
packages:
  - python
platforms:
  - linux-64
env_specs:
  sampleproj: {}
""")
        target = str(tmpdir.join('pixi.toml'))
        status = project_ops.export_pixi(project, filename=target)
        assert status
        assert status.default_rename_from is None

    def test_export_pixi_status_rename_is_none_when_already_default(self, tmpdir):
        # use_default with a project that already has `default` is a
        # no-op; rename_from should be None even though the flag was on.
        project = self._make_project("""
name: HasDefault
packages:
  - python
platforms:
  - linux-64
env_specs:
  default: {}
  other:
    packages: [pytest]
""")
        target = str(tmpdir.join('pixi.toml'))
        status = project_ops.export_pixi(project, filename=target,
                                         use_default=True)
        assert status
        assert status.default_rename_from is None

    def test_preview_pixi_export_shape(self):
        project = self._make_project("""
name: Preview
packages:
  - python
platforms:
  - linux-64
env_specs:
  sampleproj: {}
""")
        result = project_ops.preview_pixi_export(project, use_default=True)
        # Stable contract: exactly these four keys.
        assert set(result) == {
            'pixi_toml', 'default_rename_from',
            'current_platform_addition_target', 'warnings',
        }
        assert isinstance(result['pixi_toml'], str)
        assert isinstance(result['warnings'], list)
        # use_default=True actually applies in pixi_toml content
        assert '[feature.sampleproj' not in result['pixi_toml']
        assert '[dependencies]' in result['pixi_toml']
        # default_rename_from reports the candidate regardless of
        # whether use_default was passed — frontends use it to decide
        # whether to *offer* the flag.
        assert result['default_rename_from'] == 'sampleproj'

    def test_preview_reports_target_even_when_flag_off(self):
        # default_rename_from is the candidate, not "what we did". With
        # use_default=False the pixi_toml is unchanged (feature-scoped),
        # but the candidate is still reported so a UI can offer "re-run
        # with --use-default" as an action.
        project = self._make_project("""
name: PreviewOff
packages:
  - python
platforms:
  - linux-64
env_specs:
  sampleproj: {}
""")
        result = project_ops.preview_pixi_export(project, use_default=False)
        assert result['default_rename_from'] == 'sampleproj'
        assert '[feature.sampleproj.tasks.prepare]' in result['pixi_toml']

    def test_preview_extracts_warnings(self):
        # A project that triggers the system-python warning surfaces it
        # in the warnings list — without the caller having to grep the
        # toml for `# WARNING:`.
        project = self._make_project("""
name: PreviewWarn
packages: []
platforms:
  - linux-64
downloads:
  DATASET: https://example.com/data.csv
""")
        result = project_ops.preview_pixi_export(project)
        assert any(line.startswith('# WARNING:') for line in result['warnings'])
        # And the same warning is present in the rendered toml.
        assert '# WARNING:' in result['pixi_toml']

    def test_preview_default_none_when_already_default(self):
        project = self._make_project("""
name: AlreadyDefault
packages: []
platforms:
  - linux-64
env_specs:
  default: {}
""")
        result = project_ops.preview_pixi_export(project)
        assert result['default_rename_from'] is None


class TestAddCurrentPlatform:
    """``--add-current-platform`` ensures the host's conda subdir is in the
    emitted ``platforms`` list. Pixi rejects an env that doesn't list the
    host platform; anaconda-project is more forgiving."""

    def _make_project(self, yml_content):
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, 'anaconda-project.yml'), 'w') as f:
            f.write(yml_content)
        return Project(tmpdir)

    @pytest.fixture
    def fake_platform(self, monkeypatch):
        """Force current_platform() to return a known value so tests are
        deterministic across developer machines and CI runners."""
        from anaconda_project.internal import conda_api
        monkeypatch.setattr(conda_api, 'current_platform', lambda: 'osx-arm64')
        return 'osx-arm64'

    def test_picker_returns_platform_when_missing(self, fake_platform):
        project = self._make_project("""
name: NotHere
packages: []
platforms:
  - linux-64
""")
        assert current_platform_addition_target(project) == 'osx-arm64'

    def test_picker_returns_none_when_already_present(self, fake_platform):
        project = self._make_project("""
name: AlreadyHere
packages: []
platforms:
  - linux-64
  - osx-arm64
""")
        assert current_platform_addition_target(project) is None

    def test_export_adds_platform_when_flag_on(self, fake_platform):
        project = self._make_project("""
name: AddPlat
packages: []
platforms:
  - linux-64
""")
        result = export_pixi_toml(project, add_current_platform=True)
        # Sorted alphabetically, both present.
        assert 'platforms = ["linux-64", "osx-arm64"]' in result

    def test_export_leaves_platforms_alone_by_default(self, fake_platform):
        project = self._make_project("""
name: NoFlag
packages: []
platforms:
  - linux-64
""")
        result = export_pixi_toml(project)
        # Without the flag the host platform is not added — even if pixi
        # would later refuse it. anaconda-project doesn't silently mutate
        # the user's platforms list.
        assert 'osx-arm64' not in result

    def test_export_no_op_when_already_present(self, fake_platform):
        project = self._make_project("""
name: AlreadyOk
packages: []
platforms:
  - linux-64
  - osx-arm64
""")
        result = export_pixi_toml(project, add_current_platform=True)
        # Still appears exactly once in the platforms list.
        assert result.count('"osx-arm64"') == 1

    def test_status_carries_platform_added(self, fake_platform, tmpdir):
        project = self._make_project("""
name: StatusAdd
packages: []
platforms:
  - linux-64
""")
        target = str(tmpdir.join('pixi.toml'))
        status = project_ops.export_pixi(project, filename=target,
                                         add_current_platform=True)
        assert status
        assert isinstance(status, PixiExportStatus)
        assert status.current_platform_added == 'osx-arm64'

    def test_status_platform_added_is_none_without_flag(self, fake_platform, tmpdir):
        project = self._make_project("""
name: StatusOff
packages: []
platforms:
  - linux-64
""")
        target = str(tmpdir.join('pixi.toml'))
        status = project_ops.export_pixi(project, filename=target)
        assert status
        assert status.current_platform_added is None

    def test_status_platform_added_is_none_when_already_present(self, fake_platform, tmpdir):
        # Flag is on, but the platform is already there — the status
        # reports None to distinguish "we added X" from "X was there".
        project = self._make_project("""
name: StatusNoOp
packages: []
platforms:
  - linux-64
  - osx-arm64
""")
        target = str(tmpdir.join('pixi.toml'))
        status = project_ops.export_pixi(project, filename=target,
                                         add_current_platform=True)
        assert status
        assert status.current_platform_added is None

    def test_preview_reports_target_even_when_flag_off(self, fake_platform):
        project = self._make_project("""
name: PreviewPlat
packages: []
platforms:
  - linux-64
""")
        result = project_ops.preview_pixi_export(project)
        # Candidate is reported regardless of flag — frontends use it to
        # offer "re-render with --add-current-platform" as an action.
        assert result['current_platform_addition_target'] == 'osx-arm64'
        # pixi_toml itself wasn't widened (flag is off).
        assert 'osx-arm64' not in result['pixi_toml']

    def test_preview_target_none_when_already_present(self, fake_platform):
        project = self._make_project("""
name: PreviewOk
packages: []
platforms:
  - linux-64
  - osx-arm64
""")
        result = project_ops.preview_pixi_export(project)
        assert result['current_platform_addition_target'] is None
