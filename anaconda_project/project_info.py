# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2026, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Unified publication-info extraction for anaconda-project and pixi projects.

The top-level :func:`publication_info` accepts a project directory, detects
whether it is a pixi project (``pixi.toml`` present) or an anaconda-project
(``anaconda-project.yml``), parses the relevant file, and returns a metadata
dict with a shape compatible with :meth:`Project.publication_info`.

The pixi branch reads ``pixi.toml`` directly rather than materializing a
full :class:`Project` — anaconda-project is an established library for the
legacy ``.yml`` format, and this module deliberately avoids expanding
:class:`Project` to cover pixi. Consumers that need uniform metadata (e.g.
anaconda-platform's publishing pipeline) get one entry point that works
across both formats.

The pixi branch also exposes a handful of pixi-native capabilities that
anaconda-project does not support — TOML ``[feature.*]`` sections,
``[environments]`` composition, and ``[activation.env]`` variables.
"""
from __future__ import absolute_import, print_function

import os

try:
    import tomllib
except ImportError:  # Python < 3.11
    import tomli as tomllib


PIXI_MANIFEST = 'pixi.toml'
ANACONDA_PROJECT_MANIFEST = 'anaconda-project.yml'

PROJECT_TYPE_KEY = 'project_type'
PROJECT_TYPE_PIXI = 'pixi'
PROJECT_TYPE_ANACONDA_PROJECT = 'anaconda-project'


def detect_project_type(project_dir):
    """Return the project type string for *project_dir*, or ``None`` if unknown.

    Detection is by manifest presence; ``pixi.toml`` wins when both are present,
    matching the dispatch used by :func:`publication_info`.
    """
    if os.path.isfile(os.path.join(project_dir, PIXI_MANIFEST)):
        return PROJECT_TYPE_PIXI
    if os.path.isfile(os.path.join(project_dir, ANACONDA_PROJECT_MANIFEST)):
        return PROJECT_TYPE_ANACONDA_PROJECT
    return None


def publication_info(project_dir):
    """Return a publication-info dict for the project at *project_dir*.

    If ``pixi.toml`` is present, the pixi manifest is parsed directly. Otherwise
    ``anaconda-project.yml`` is loaded through :class:`Project`. The returned
    dict always includes a ``project_type`` key identifying which manifest
    format was used.

    Raises:
        ValueError: the pixi manifest cannot be parsed.
        FileNotFoundError: neither manifest is present.
    """
    project_type = detect_project_type(project_dir)
    if project_type == PROJECT_TYPE_PIXI:
        info = _pixi_publication_info(project_dir)
    elif project_type == PROJECT_TYPE_ANACONDA_PROJECT:
        info = _anaconda_project_publication_info(project_dir)
    else:
        raise FileNotFoundError(
            'No {} or {} found in {}'.format(
                PIXI_MANIFEST, ANACONDA_PROJECT_MANIFEST, project_dir
            )
        )
    info[PROJECT_TYPE_KEY] = project_type
    return info


def _anaconda_project_publication_info(project_dir):
    from anaconda_project.project import Project
    return Project(project_dir).publication_info()


def _pixi_publication_info(project_dir):
    pixi_path = os.path.join(project_dir, PIXI_MANIFEST)
    try:
        with open(pixi_path, 'rb') as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ValueError('Failed to parse {}: {}'.format(pixi_path, e)) from e

    workspace = data.get('workspace', {})
    project_meta = data.get('project', {})
    name = workspace.get('name', project_meta.get('name', os.path.basename(project_dir)))
    description = workspace.get('description', project_meta.get('description', ''))
    channels = workspace.get('channels', project_meta.get('channels', []))

    tool_commands = data.get('tool', {}).get('anaconda', {}).get('commands', {})

    commands = {}
    state = {'first': True}

    for task_name, task_def in data.get('tasks', {}).items():
        cmd = _build_command(task_name, task_def, 'default', tool_commands, state)
        if cmd is not None:
            commands[task_name] = cmd

    for feat_name, feat_def in data.get('feature', {}).items():
        for task_name, task_def in feat_def.get('tasks', {}).items():
            if task_name in commands:
                continue
            cmd = _build_command(task_name, task_def, feat_name, tool_commands, state)
            if cmd is not None:
                commands[task_name] = cmd

    top_packages = [
        _format_dep(pkg, spec) for pkg, spec in data.get('dependencies', {}).items()
    ]

    def _packages_for_env(env_def):
        """Resolve effective package list for a declared env: top-level
        [dependencies] (the default feature) plus each feature listed in
        the env's `features = [...]`. An env declared with
        `no-default-feature = true` does not inherit the default feature."""
        if env_def is None:
            return list(top_packages)
        features = env_def if isinstance(env_def, list) else env_def.get('features', [])
        no_default = (
            isinstance(env_def, dict) and env_def.get('no-default-feature', False)
        )
        pkgs = [] if no_default else list(top_packages)
        for feat in features:
            feat_deps = data.get('feature', {}).get(feat, {}).get('dependencies', {})
            pkgs.extend(_format_dep(n, s) for n, s in feat_deps.items())
        return pkgs

    # Pixi always materializes a `default` env, even when not declared in
    # [environments]. Surface it unconditionally; honor the user's
    # declaration if one exists.
    declared_envs = data.get('environments', {})
    env_specs = {
        'default': {
            'packages': _packages_for_env(declared_envs.get('default')),
            'channels': channels,
        },
    }
    for env_name, env_def in declared_envs.items():
        if env_name == 'default':
            continue
        env_specs[env_name] = {
            'packages': _packages_for_env(env_def),
            'channels': channels,
        }

    variables = dict(data.get('activation', {}).get('env', {}))

    return {
        'name': name,
        'description': description,
        'commands': commands,
        'env_specs': env_specs,
        'variables': variables,
    }


def _build_command(task_name, task_def, env_spec, tool_commands, state):
    if isinstance(task_def, str):
        cmd_str = task_def
    elif isinstance(task_def, dict):
        cmd_str = task_def.get('cmd', '')
        if task_def.get('environment'):
            env_spec = task_def['environment']
    else:
        return None

    tool_meta = tool_commands.get(task_name, {})

    notebook = tool_meta.get('notebook')
    if notebook is None:
        notebook = _infer_notebook(cmd_str)

    supports_http = tool_meta.get('supports_http_options')
    if supports_http is None:
        supports_http = notebook is not None or _looks_like_http(cmd_str)

    is_default = tool_meta.get('default', state['first'])

    description = tool_meta.get('description', '')
    if not description:
        description = 'Notebook %s' % notebook if notebook else cmd_str

    state['first'] = False

    return {
        'unix': cmd_str,
        'env_spec': env_spec,
        'supports_http_options': supports_http,
        'notebook': notebook,
        'default': is_default,
        'description': description,
    }


def _format_dep(name, spec):
    if isinstance(spec, str) and spec not in ('*', ''):
        if spec[0].isdigit():
            return '{}={}'.format(name, spec)
        return '{}{}'.format(name, spec)
    return name


# Commands we recognize as actual Jupyter notebook launchers. Anything
# else that mentions an .ipynb file (e.g. `panel serve foo.ipynb`,
# `voila foo.ipynb`, `streamlit run foo.ipynb`) is a different kind of
# app — it happens to consume an .ipynb as its source but isn't
# something a notebook viewer should render.
_NOTEBOOK_LAUNCHERS = (
    'jupyter notebook',
    'jupyter lab',
    'jupyter-lab',
    'jupyter-notebook',
)


def _infer_notebook(cmd_str):
    cmd_lower = cmd_str.lower()
    if not any(launcher in cmd_lower for launcher in _NOTEBOOK_LAUNCHERS):
        return None
    for token in cmd_str.split():
        if token.endswith('.ipynb'):
            return token
    return None


def _looks_like_http(cmd_str):
    http_indicators = [
        'bokeh serve', 'panel serve', 'streamlit run',
        'flask run', 'uvicorn', 'gunicorn',
        'python -m http.server', 'voila',
    ]
    cmd_lower = cmd_str.lower()
    return any(ind in cmd_lower for ind in http_indicators)
