# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2026, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Tests for anaconda_project.project_info."""
from __future__ import absolute_import, print_function

import os
import tempfile
import textwrap

import pytest

from anaconda_project.project_info import (
    PROJECT_TYPE_ANACONDA_PROJECT,
    PROJECT_TYPE_KEY,
    PROJECT_TYPE_PIXI,
    _format_dep,
    _infer_notebook,
    _looks_like_http,
    detect_project_type,
    publication_info,
)


def _write_pixi_toml(tmpdir, content):
    path = os.path.join(tmpdir, 'pixi.toml')
    with open(path, 'w') as f:
        f.write(content)
    return tmpdir


def _write_anaconda_project(tmpdir, content):
    path = os.path.join(tmpdir, 'anaconda-project.yml')
    with open(path, 'w') as f:
        f.write(content)
    return tmpdir


class TestFormatDep:
    def test_wildcard(self):
        assert _format_dep('numpy', '*') == 'numpy'

    def test_version_with_operator(self):
        assert _format_dep('python', '>=3.12') == 'python>=3.12'

    def test_version_with_equals(self):
        assert _format_dep('pandas', '==2.1.0') == 'pandas==2.1.0'

    def test_bare_version_number(self):
        assert _format_dep('flask', '3.0.*') == 'flask=3.0.*'

    def test_dict_spec(self):
        assert _format_dep('torch', {'version': '>=2.0'}) == 'torch'

    def test_none_spec(self):
        assert _format_dep('requests', None) == 'requests'

    def test_empty_string(self):
        assert _format_dep('pkg', '') == 'pkg'


class TestInferNotebook:
    def test_jupyter_notebook_detected(self):
        assert _infer_notebook('jupyter notebook analysis.ipynb') == 'analysis.ipynb'

    def test_jupyter_lab_detected(self):
        assert _infer_notebook('jupyter lab notebooks/demo.ipynb') == 'notebooks/demo.ipynb'

    def test_jupyter_notebook_dash_form(self):
        assert _infer_notebook('jupyter-notebook foo.ipynb') == 'foo.ipynb'

    def test_panel_serve_ipynb_is_not_a_notebook(self):
        # panel serve consumes the .ipynb but renders a web app, not a
        # notebook view. Only commands that explicitly launch Jupyter
        # should be classified as notebooks.
        assert _infer_notebook('panel serve glaciers.ipynb') is None

    def test_voila_ipynb_is_not_a_notebook(self):
        # voila publishes notebooks as web apps. Same rule: not a
        # notebook command in the publication-info sense.
        assert _infer_notebook('voila notebooks/demo.ipynb') is None

    def test_python_script_not_a_notebook(self):
        assert _infer_notebook('python app.py') is None

    def test_ipynb_substring_not_matched(self):
        assert _infer_notebook('echo ipynb_files') is None


class TestLooksLikeHttp:
    def test_panel_serve(self):
        assert _looks_like_http('panel serve dashboard.py') is True

    def test_bokeh_serve(self):
        assert _looks_like_http('bokeh serve app') is True

    def test_flask_run(self):
        assert _looks_like_http('flask run --port 8080') is True

    def test_uvicorn(self):
        assert _looks_like_http('uvicorn main:app') is True

    def test_gunicorn(self):
        assert _looks_like_http('gunicorn app:app') is True

    def test_streamlit(self):
        assert _looks_like_http('streamlit run app.py') is True

    def test_voila(self):
        assert _looks_like_http('voila notebook.ipynb') is True

    def test_plain_python(self):
        assert _looks_like_http('python app.py') is False

    def test_python_http_server(self):
        assert _looks_like_http('python -m http.server 8000') is True


class TestPublicationInfoBasic:
    def test_minimal_project(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(
                td,
                '[workspace]\nname = "test"\nchannels = ["conda-forge"]\nplatforms = ["linux-64"]\n',
            )
            info = publication_info(td)
            assert info['name'] == 'test'
            assert info['description'] == ''
            assert info['commands'] == {}
            assert info['env_specs'] == {
                'default': {'packages': [], 'channels': ['conda-forge'], 'locked': False},
            }
            assert info['variables'] == {}
            assert info[PROJECT_TYPE_KEY] == PROJECT_TYPE_PIXI

    def test_name_from_project_section(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(
                td,
                '[project]\nname = "from-project"\n\n[workspace]\nchannels = ["conda-forge"]\nplatforms = ["linux-64"]\n',
            )
            info = publication_info(td)
            assert info['name'] == 'from-project'

    def test_workspace_name_takes_precedence(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(
                td,
                '[project]\nname = "project-name"\n\n[workspace]\nname = "workspace-name"\nchannels = ["conda-forge"]\nplatforms = ["linux-64"]\n',
            )
            info = publication_info(td)
            assert info['name'] == 'workspace-name'

    def test_fallback_to_directory_name(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(
                td, '[workspace]\nchannels = ["conda-forge"]\nplatforms = ["linux-64"]\n'
            )
            info = publication_info(td)
            assert info['name'] == os.path.basename(td)

    def test_description(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(
                td,
                '[project]\nname = "x"\ndescription = "A test project"\n\n[workspace]\nchannels = ["conda-forge"]\nplatforms = ["linux-64"]\n',
            )
            info = publication_info(td)
            assert info['description'] == 'A test project'


class TestPublicationInfoDependencies:
    def test_simple_deps(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(
                td,
                '[workspace]\nname = "t"\nchannels = ["conda-forge"]\nplatforms = ["linux-64"]\n\n[dependencies]\npython = ">=3.12"\nnumpy = "*"\n',
            )
            info = publication_info(td)
            pkgs = info['env_specs']['default']['packages']
            assert 'python>=3.12' in pkgs
            assert 'numpy' in pkgs

    def test_channels(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(
                td,
                '[workspace]\nname = "t"\nchannels = ["defaults", "conda-forge"]\nplatforms = ["linux-64"]\n',
            )
            info = publication_info(td)
            assert info['env_specs']['default']['channels'] == ['defaults', 'conda-forge']


class TestPublicationInfoTasks:
    def test_string_task(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(
                td,
                '[workspace]\nname = "t"\nchannels = ["conda-forge"]\nplatforms = ["linux-64"]\n\n[tasks]\nhello = "echo hi"\n',
            )
            info = publication_info(td)
            assert 'hello' in info['commands']
            assert info['commands']['hello']['unix'] == 'echo hi'
            assert info['commands']['hello']['default'] is True

    def test_dict_task(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(
                td,
                '[workspace]\nname = "t"\nchannels = ["conda-forge"]\nplatforms = ["linux-64"]\n\n[tasks.serve]\ncmd = "flask run"\n',
            )
            info = publication_info(td)
            assert info['commands']['serve']['unix'] == 'flask run'
            assert info['commands']['serve']['supports_http_options'] is True

    def test_args_extracted_from_pixi_task(self):
        # The exporter emits `args = [{ arg = "host", default = "" }, ...]`
        # for tasks that take http options. publication_info should
        # surface those arg names (in declaration order) so callers can
        # know what positional values `pixi run <task>` expects.
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, textwrap.dedent("""\
                [workspace]
                name = "t"
                channels = ["conda-forge"]
                platforms = ["linux-64"]

                [tasks.serve]
                cmd = "panel serve foo.ipynb {% if port %}--port {{ port }}{% endif %}"
                args = [{ arg = "host", default = "" }, { arg = "port", default = "" }]
            """))
            info = publication_info(td)
            assert info['commands']['serve']['args'] == ['host', 'port']

    def test_args_empty_for_string_task(self):
        # A bare string task (no `args` key) gets an empty `args` list,
        # not a missing key — keeps the schema uniform for callers.
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(
                td,
                '[workspace]\nname = "t"\nchannels = ["conda-forge"]\nplatforms = ["linux-64"]\n\n[tasks]\nrun = "echo hi"\n',
            )
            info = publication_info(td)
            assert info['commands']['run']['args'] == []

    def test_first_task_is_default(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(
                td,
                '[workspace]\nname = "t"\nchannels = ["conda-forge"]\nplatforms = ["linux-64"]\n\n[tasks]\nfirst = "echo 1"\nsecond = "echo 2"\n',
            )
            info = publication_info(td)
            assert info['commands']['first']['default'] is True
            assert info['commands']['second']['default'] is False

    def test_notebook_inference_jupyter(self):
        # Direct conversions of `notebook:` commands become
        # `jupyter notebook ...`; those are what publication_info should
        # report as a notebook.
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(
                td,
                '[workspace]\nname = "t"\nchannels = ["conda-forge"]\nplatforms = ["linux-64"]\n\n[tasks]\nnb = "jupyter notebook report.ipynb"\n',
            )
            info = publication_info(td)
            assert info['commands']['nb']['notebook'] == 'report.ipynb'
            assert info['commands']['nb']['supports_http_options'] is True

    def test_app_serving_ipynb_is_not_a_notebook(self):
        # `panel serve foo.ipynb` happens to consume an .ipynb but is a
        # web app, not a notebook view. The publication info should
        # reflect that — supports_http_options stays True (it IS an HTTP
        # service), but `notebook` must be None.
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(
                td,
                '[workspace]\nname = "t"\nchannels = ["conda-forge"]\nplatforms = ["linux-64"]\n\n[tasks]\ndashboard = "panel serve glaciers.ipynb"\n',
            )
            info = publication_info(td)
            assert info['commands']['dashboard']['notebook'] is None
            assert info['commands']['dashboard']['supports_http_options'] is True

    def test_task_with_environment(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(
                td,
                '[workspace]\nname = "t"\nchannels = ["conda-forge"]\nplatforms = ["linux-64"]\n\n[tasks.serve]\ncmd = "python app.py"\nenvironment = "prod"\n',
            )
            info = publication_info(td)
            assert info['commands']['serve']['env_spec'] == 'prod'


class TestPublicationInfoEnvResolution:
    """env_spec should always name an env that supports the task — never
    a placeholder like 'default' when the project's only env has another
    name, and never the bare feature name when a real env carries it."""

    def test_top_level_task_resolves_to_first_env_when_no_default(self):
        # Single declared env named 'sampleproj'. Top-level [tasks.X] runs
        # in the resolved default env, which is the first declared.
        # `default` is also surfaced unconditionally because pixi
        # materializes it at runtime regardless.
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, textwrap.dedent("""\
                [workspace]
                name = "t"
                channels = ["conda-forge"]
                platforms = ["linux-64"]

                [environments]
                sampleproj = { features = ["sampleproj"] }

                [tasks.run]
                cmd = "echo hi"
            """))
            info = publication_info(td)
            assert info['commands']['run']['env_spec'] == 'sampleproj'
            assert set(info['env_specs']) == {'default', 'sampleproj'}

    def test_top_level_task_keeps_default_when_explicitly_declared(self):
        # When the user *does* declare `default` in [environments], use
        # that name verbatim — don't promote a sibling env.
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, textwrap.dedent("""\
                [workspace]
                name = "t"
                channels = ["conda-forge"]
                platforms = ["linux-64"]

                [environments]
                default = { features = [] }
                ml = { features = ["ml"] }

                [tasks.run]
                cmd = "echo hi"
            """))
            info = publication_info(td)
            assert info['commands']['run']['env_spec'] == 'default'
            assert 'default' in info['env_specs']
            assert 'ml' in info['env_specs']

    def test_feature_task_resolves_to_env_carrying_feature(self):
        # [feature.ml.tasks.train] should report env_spec='ml' because
        # the env named `ml` includes feature `ml`. The exporter's
        # convention (feature name == env name) makes this trivial, but
        # the resolution logic doesn't assume that — it walks
        # [environments] entries to find which envs include the feature.
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, textwrap.dedent("""\
                [workspace]
                name = "t"
                channels = ["conda-forge"]
                platforms = ["linux-64"]

                [environments]
                ml = { features = ["ml"] }

                [feature.ml.tasks.train]
                cmd = "python train.py"
            """))
            info = publication_info(td)
            assert info['commands']['train']['env_spec'] == 'ml'

    def test_feature_task_picks_default_env_when_multiple_match(self):
        # If the same feature is included in multiple envs, the resolved
        # default wins (so `pixi run task` matches the env publication
        # picks).
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, textwrap.dedent("""\
                [workspace]
                name = "t"
                channels = ["conda-forge"]
                platforms = ["linux-64"]

                [environments]
                primary = { features = ["common"] }
                secondary = { features = ["common"] }

                [feature.common.tasks.run]
                cmd = "echo hi"
            """))
            info = publication_info(td)
            # primary is first declared → resolved default → wins.
            assert info['commands']['run']['env_spec'] == 'primary'

    def test_default_env_always_surfaced_alongside_named_envs(self):
        # Pixi always materializes a `default` env at runtime, so
        # publication_info surfaces it unconditionally. Default-feature
        # packages flow into the `default` env_spec; feature-specific
        # deps flow into the named env. Each env carries the right
        # packages (no cross-pollination).
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, textwrap.dedent("""\
                [workspace]
                name = "t"
                channels = ["conda-forge"]
                platforms = ["linux-64"]

                [dependencies]
                python = "*"

                [feature.sampleproj.dependencies]
                pandas = "*"

                [environments]
                sampleproj = { features = ["sampleproj"] }
            """))
            info = publication_info(td)
            assert set(info['env_specs']) == {'default', 'sampleproj'}
            # `default` carries only the default-feature packages.
            assert info['env_specs']['default']['packages'] == ['python']
            # `sampleproj` inherits the default feature plus its own.
            sample = info['env_specs']['sampleproj']['packages']
            assert 'python' in sample
            assert 'pandas' in sample
            # Both default-feature and sampleproj-feature packages roll up.
            assert 'python' in info['env_specs']['sampleproj']['packages']
            assert 'pandas' in info['env_specs']['sampleproj']['packages']


class TestPublicationInfoLocked:
    def test_locked_false_when_no_lockfile(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, textwrap.dedent("""\
                [workspace]
                name = "t"
                channels = ["conda-forge"]
                platforms = ["linux-64"]

                [environments]
                sampleproj = { features = ["sampleproj"] }
            """))
            info = publication_info(td)
            assert info['env_specs']['sampleproj']['locked'] is False

    def test_locked_true_when_env_in_pixi_lock(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, textwrap.dedent("""\
                [workspace]
                name = "t"
                channels = ["conda-forge"]
                platforms = ["linux-64"]

                [environments]
                sampleproj = { features = ["sampleproj"] }
                test = { features = ["test"] }
            """))
            with open(os.path.join(td, 'pixi.lock'), 'w') as f:
                f.write(textwrap.dedent("""\
                    version: 6
                    environments:
                      sampleproj:
                        channels:
                        - url: https://example/
                        packages: {}
                """))
            info = publication_info(td)
            # sampleproj is in the lock — locked. test is not — unlocked.
            assert info['env_specs']['sampleproj']['locked'] is True
            assert info['env_specs']['test']['locked'] is False

    def test_malformed_lockfile_falls_back_to_unlocked(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, textwrap.dedent("""\
                [workspace]
                name = "t"
                channels = ["conda-forge"]
                platforms = ["linux-64"]

                [environments]
                sampleproj = { features = ["sampleproj"] }
            """))
            with open(os.path.join(td, 'pixi.lock'), 'w') as f:
                # Not valid YAML — should silently fall back, not raise.
                f.write('this is not: { valid yaml: at all\n')
            info = publication_info(td)
            assert info['env_specs']['sampleproj']['locked'] is False


class TestPublicationInfoFeatures:
    def test_feature_tasks_included(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, textwrap.dedent("""\
                [workspace]
                name = "multi"
                channels = ["conda-forge"]
                platforms = ["linux-64"]

                [tasks]
                serve = "panel serve app.py"

                [feature.ml.tasks.train]
                cmd = "python train.py"

                [feature.ml.dependencies]
                scikit-learn = "*"

                [environments]
                default = { solve-group = "default" }
                ml = { features = ["ml"], solve-group = "default" }
            """))
            info = publication_info(td)
            assert 'serve' in info['commands']
            assert 'train' in info['commands']
            assert info['commands']['train']['env_spec'] == 'ml'
            assert info['commands']['train']['unix'] == 'python train.py'

    def test_global_task_not_overridden_by_feature(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, textwrap.dedent("""\
                [workspace]
                name = "t"
                channels = ["conda-forge"]
                platforms = ["linux-64"]

                [tasks]
                run = "echo global"

                [feature.alt.tasks.run]
                cmd = "echo feature"
            """))
            info = publication_info(td)
            assert info['commands']['run']['unix'] == 'echo global'
            assert info['commands']['run']['env_spec'] == 'default'

    def test_feature_env_specs(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, textwrap.dedent("""\
                [workspace]
                name = "t"
                channels = ["conda-forge"]
                platforms = ["linux-64"]

                [dependencies]
                python = ">=3.12"

                [feature.gpu.dependencies]
                pytorch = "*"

                [environments]
                default = { solve-group = "default" }
                gpu = { features = ["gpu"], solve-group = "default" }
            """))
            info = publication_info(td)
            assert 'gpu' in info['env_specs']
            assert 'pytorch' in info['env_specs']['gpu']['packages']
            assert 'python>=3.12' in info['env_specs']['gpu']['packages']

    def test_no_default_feature_excludes_top_level_deps(self):
        # An env declared with `no-default-feature = true` must not inherit
        # the top-level [dependencies] (the default feature).
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, textwrap.dedent("""\
                [workspace]
                name = "t"
                channels = ["conda-forge"]
                platforms = ["linux-64"]

                [dependencies]
                pandas = "*"
                python = ">=3.12"

                [feature.testenv.dependencies]
                ipykernel = "*"
                pandas = "*"

                [environments]
                sampleproj = { features = ["testenv"] }
                testenv = { features = ["testenv"], no-default-feature = true }
            """))
            info = publication_info(td)
            sample = info['env_specs']['sampleproj']['packages']
            test = info['env_specs']['testenv']['packages']
            # sampleproj inherits the default feature -> python is present
            assert 'python>=3.12' in sample
            assert 'pandas' in sample
            assert 'ipykernel' in sample
            # testenv opts out of the default feature -> python is absent
            assert 'python>=3.12' not in test
            assert 'ipykernel' in test
            assert 'pandas' in test

    def test_default_env_always_present(self):
        # Pixi always materializes a `default` env. publication_info must
        # surface it even when [environments] only declares other envs.
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, textwrap.dedent("""\
                [workspace]
                name = "t"
                channels = ["conda-forge"]
                platforms = ["linux-64"]

                [dependencies]
                python = ">=3.12"

                [feature.alt.dependencies]
                numpy = "*"

                [environments]
                alt = { features = ["alt"] }
            """))
            info = publication_info(td)
            assert 'default' in info['env_specs']
            assert 'python>=3.12' in info['env_specs']['default']['packages']

    def test_default_env_honors_declaration(self):
        # When the user explicitly declares `default = { features = [...] }`,
        # the resulting default env_spec must include those feature deps.
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, textwrap.dedent("""\
                [workspace]
                name = "t"
                channels = ["conda-forge"]
                platforms = ["linux-64"]

                [dependencies]
                python = ">=3.12"

                [feature.extras.dependencies]
                requests = "*"

                [environments]
                default = { features = ["extras"] }
            """))
            info = publication_info(td)
            assert 'requests' in info['env_specs']['default']['packages']
            assert 'python>=3.12' in info['env_specs']['default']['packages']


class TestPublicationInfoVariables:
    def test_activation_env(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(
                td,
                '[workspace]\nname = "t"\nchannels = ["conda-forge"]\nplatforms = ["linux-64"]\n\n[activation.env]\nDATA_DIR = "./data"\nDEBUG = "1"\n',
            )
            info = publication_info(td)
            assert info['variables'] == {'DATA_DIR': './data', 'DEBUG': '1'}


class TestPublicationInfoToolAnaconda:
    def test_tool_anaconda_overrides(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, textwrap.dedent("""\
                [workspace]
                name = "t"
                channels = ["conda-forge"]
                platforms = ["linux-64"]

                [tasks]
                serve = "python app.py"

                [tool.anaconda.commands.serve]
                supports_http_options = true
                description = "Run the web app"
                default = true
                notebook = "app.ipynb"
            """))
            info = publication_info(td)
            cmd = info['commands']['serve']
            assert cmd['supports_http_options'] is True
            assert cmd['description'] == 'Run the web app'
            assert cmd['notebook'] == 'app.ipynb'


class TestPublicationInfoErrors:
    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as td:
            with pytest.raises(FileNotFoundError):
                publication_info(td)

    def test_invalid_toml(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, 'pixi.toml')
            with open(path, 'w') as f:
                f.write('this is not valid toml [[[')
            with pytest.raises(ValueError, match='Failed to parse'):
                publication_info(td)

    def test_empty_file(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, '')
            info = publication_info(td)
            assert info['name'] == os.path.basename(td)
            assert info['commands'] == {}


class TestDetectProjectType:
    def test_detects_pixi(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, '[workspace]\nname = "t"\n')
            assert detect_project_type(td) == PROJECT_TYPE_PIXI

    def test_detects_anaconda_project(self):
        with tempfile.TemporaryDirectory() as td:
            _write_anaconda_project(td, 'name: t\n')
            assert detect_project_type(td) == PROJECT_TYPE_ANACONDA_PROJECT

    def test_pixi_wins_when_both_present(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, '[workspace]\nname = "t"\n')
            _write_anaconda_project(td, 'name: t\n')
            assert detect_project_type(td) == PROJECT_TYPE_PIXI

    def test_neither_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            assert detect_project_type(td) is None


class TestAnacondaProjectBranch:
    def test_anaconda_project_publication_info(self):
        with tempfile.TemporaryDirectory() as td:
            _write_anaconda_project(td, textwrap.dedent("""\
                name: sample
                description: An anaconda-project sample

                commands:
                  run:
                    unix: python app.py

                env_specs:
                  default:
                    channels:
                      - defaults
                    packages:
                      - python=3.12
                      - flask
            """))
            info = publication_info(td)
            assert info[PROJECT_TYPE_KEY] == PROJECT_TYPE_ANACONDA_PROJECT
            assert info['name'] == 'sample'
            assert info['description'] == 'An anaconda-project sample'
            assert 'run' in info['commands']
            assert info['commands']['run']['unix'] == 'python app.py'
            assert 'default' in info['env_specs']
            assert 'flask' in info['env_specs']['default']['packages']


class TestProjectTypeKey:
    def test_pixi_tagged(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, '[workspace]\nname = "t"\n')
            assert publication_info(td)[PROJECT_TYPE_KEY] == PROJECT_TYPE_PIXI


class TestExplicitProjectType:
    """Caller-supplied `project_type` overrides the pixi-wins-by-default
    detection. Asking for a format whose manifest is absent is an error."""

    def test_force_anaconda_project_when_both_present(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, '[workspace]\nname = "from-pixi"\n')
            _write_anaconda_project(td, textwrap.dedent("""\
                name: from-yml
                env_specs:
                  default:
                    channels: [defaults]
                    packages: [python=3.12]
            """))
            info = publication_info(td, project_type=PROJECT_TYPE_ANACONDA_PROJECT)
            assert info[PROJECT_TYPE_KEY] == PROJECT_TYPE_ANACONDA_PROJECT
            assert info['name'] == 'from-yml'

    def test_force_pixi_when_both_present(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, '[workspace]\nname = "from-pixi"\n')
            _write_anaconda_project(td, 'name: from-yml\n')
            info = publication_info(td, project_type=PROJECT_TYPE_PIXI)
            assert info[PROJECT_TYPE_KEY] == PROJECT_TYPE_PIXI
            assert info['name'] == 'from-pixi'

    def test_force_pixi_without_pixi_toml_raises(self):
        with tempfile.TemporaryDirectory() as td:
            _write_anaconda_project(td, 'name: t\n')
            with pytest.raises(FileNotFoundError) as exc:
                publication_info(td, project_type=PROJECT_TYPE_PIXI)
            assert 'pixi.toml' in str(exc.value)

    def test_force_anaconda_project_without_yml_raises(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, '[workspace]\nname = "t"\n')
            with pytest.raises(FileNotFoundError) as exc:
                publication_info(td, project_type=PROJECT_TYPE_ANACONDA_PROJECT)
            assert 'anaconda-project.yml' in str(exc.value)

    def test_unknown_project_type_raises(self):
        with tempfile.TemporaryDirectory() as td:
            _write_pixi_toml(td, '[workspace]\nname = "t"\n')
            with pytest.raises(ValueError) as exc:
                publication_info(td, project_type='conda-workspaces')
            assert 'conda-workspaces' in str(exc.value)
