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
    _conda_spec_to_pixi,
    _expand_defaults_in_channels,
    _strip_conda_prefix_paths,
    _translate_command_env_vars,
    _windows_to_deno_shell,
    export_pixi_toml,
)
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

    def test_no_prepare_task_when_no_downloads(self):
        # If there's no real work for prepare to do, omit it entirely.
        # Downstream tooling looks for `prepare` and runs it when
        # present; an absent task is the same signal as "nothing to
        # prepare for this project," and skipping it costs no logic on
        # the consumer side.
        project = self._make_project("""
name: NoDl
packages:
  - python
platforms:
  - linux-64
""")
        result = export_pixi_toml(project)
        assert 'prepare' not in result

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

    def test_no_prepare_when_yml_has_no_downloads(self):
        # Mirror of test_no_prepare_task_when_no_downloads but at this
        # level of the suite — keeping coverage close to the related
        # single-named-env test below.
        project = self._make_project("""
name: Plain
packages:
  - python
platforms:
  - linux-64
""")
        result = export_pixi_toml(project)
        assert 'prepare' not in result
        # And no helper invocation either, of course.
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
