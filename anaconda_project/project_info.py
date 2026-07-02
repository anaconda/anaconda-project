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
CONDA_TOML_MANIFEST = 'conda.toml'
ANACONDA_PROJECT_MANIFEST = 'anaconda-project.yml'
PYPROJECT_MANIFEST = 'pyproject.toml'

PROJECT_TYPE_KEY = 'project_type'
PROJECT_TYPE_CONDA_WORKSPACES = 'conda-workspaces'
PROJECT_TYPE_PIXI = 'pixi'
PROJECT_TYPE_ANACONDA_PROJECT = 'anaconda-project'


def _locate_manifest(project_dir):
    """Determine which manifest is present in *project_dir*.

    Returns a tuple (manifest_kind, path_or_none) where manifest_kind is one of:
    - 'conda-toml': conda.toml present → returns path
    - 'pixi-toml': pixi.toml present → returns path
    - 'anaconda-project': anaconda-project.* present → returns path
    - 'pyproject-conda': pyproject.toml with [tool.conda.workspace] → returns path
    - 'pyproject-pixi': pyproject.toml with [tool.pixi.workspace] → returns path
    - None: no manifest found → returns None

    Checks in precedence order. For pyproject-* cases, the file is parsed to
    determine which [tool] section has a workspace table. Parse errors in
    pyproject.toml are silently treated as non-match (returns None).
    """
    # 1. Check for conda.toml
    conda_path = os.path.join(project_dir, CONDA_TOML_MANIFEST)
    if os.path.isfile(conda_path):
        return ('conda-toml', conda_path)

    # 2. Check for pixi.toml
    pixi_path = os.path.join(project_dir, PIXI_MANIFEST)
    if os.path.isfile(pixi_path):
        return ('pixi-toml', pixi_path)

    # 3. Check for anaconda-project manifest files
    from anaconda_project.project_file import possible_project_file_names
    for filename in possible_project_file_names:
        ap_path = os.path.join(project_dir, filename)
        if os.path.isfile(ap_path):
            return ('anaconda-project', ap_path)

    # 4. Check for pyproject.toml with tool.conda or tool.pixi workspace
    pyproject_path = os.path.join(project_dir, PYPROJECT_MANIFEST)
    if os.path.isfile(pyproject_path):
        try:
            with open(pyproject_path, 'rb') as f:
                data = tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError):
            # Parse error or file access error — treat as non-match, don't raise
            return (None, None)

        # Check for tool.conda.workspace first
        if data.get('tool', {}).get('conda', {}).get('workspace'):
            return ('pyproject-conda', pyproject_path)

        # Then check for tool.pixi.workspace
        if data.get('tool', {}).get('pixi', {}).get('workspace'):
            return ('pyproject-pixi', pyproject_path)

    return (None, None)


def detect_project_type(project_dir):
    """Return the project type string for *project_dir*, or ``None`` if unknown.

    Detection is by manifest presence, in precedence order:
    1. ``conda.toml`` → ``'conda-workspaces'``
    2. ``pixi.toml`` → ``'pixi'``
    3. ``anaconda-project.yml`` (or variants) → ``'anaconda-project'``
    4. ``pyproject.toml`` with ``[tool.conda.workspace]`` or ``[tool.pixi.workspace]`` →
       ``'conda-workspaces'`` or ``'pixi'`` respectively
    5. Otherwise → ``None``

    Detection errors (e.g., malformed ``pyproject.toml``) are silently treated as
    non-matches and do not raise.
    """
    manifest_kind, _path = _locate_manifest(project_dir)

    if manifest_kind == 'conda-toml':
        return PROJECT_TYPE_CONDA_WORKSPACES
    elif manifest_kind == 'pixi-toml':
        return PROJECT_TYPE_PIXI
    elif manifest_kind == 'anaconda-project':
        return PROJECT_TYPE_ANACONDA_PROJECT
    elif manifest_kind == 'pyproject-conda':
        return PROJECT_TYPE_CONDA_WORKSPACES
    elif manifest_kind == 'pyproject-pixi':
        return PROJECT_TYPE_PIXI
    else:
        return None


def publication_info(project_dir, project_type=None, env_paths=False):
    """Return a publication-info dict for the project at *project_dir*.

    With *project_type* unset (the default), auto-detects by manifest presence
    in precedence order: conda.toml, pixi.toml, anaconda-project.*, pyproject.toml.
    Pass ``project_type='conda-workspaces'``, ``'pixi'``, or ``'anaconda-project'``
    to force a specific format; explicit types now recognize both top-level manifests
    (conda.toml/pixi.toml) and pyproject.toml embedding ([tool.conda.workspace] or
    [tool.pixi.workspace]), matching auto-detect behavior. The returned dict
    always includes a ``project_type`` key identifying which manifest format was used.

    Pass ``env_paths=True`` to populate ``info['env_specs'][name]['path']``
    with the filesystem prefix for each declared environment. For
    anaconda-project this is computed from each :class:`EnvSpec` and is
    free; for pixi (whether from a top-level pixi.toml or a pyproject.toml
    ``[tool.pixi]`` embedding) we shell out to ``pixi info --json`` (so it
    costs a subprocess) and surface any error from that call. For
    conda-workspaces there is no equivalent path-resolution mechanism yet,
    so ``env_paths=True`` has no effect on conda-workspaces results.

    Raises:
        ValueError: *project_type* is not a recognized value, or a manifest
            cannot be parsed.
        FileNotFoundError: the requested manifest (or, with no
            *project_type*, any manifest) is not present.
        RuntimeError: ``env_paths=True`` was requested for a pixi project
            and ``pixi info --json`` failed.
    """
    if project_type is None:
        # Auto-detect: use _locate_manifest to find the winning manifest,
        # then re-derive the type from its kind
        manifest_kind, manifest_path = _locate_manifest(project_dir)
        if manifest_kind is None:
            raise FileNotFoundError(
                'No manifest (conda.toml, pixi.toml, anaconda-project.*, or '
                'pyproject.toml with [tool.conda.workspace] or [tool.pixi.workspace]) '
                'found in {}'.format(project_dir)
            )

        # Determine project_type from manifest_kind and load data as needed
        if manifest_kind == 'conda-toml':
            project_type = PROJECT_TYPE_CONDA_WORKSPACES
            try:
                with open(manifest_path, 'rb') as f:
                    data = tomllib.load(f)
            except (OSError, tomllib.TOMLDecodeError) as e:
                raise ValueError('Failed to parse {}: {}'.format(manifest_path, e)) from e
            info = _conda_workspaces_publication_info(project_dir, data)

        elif manifest_kind == 'pixi-toml':
            project_type = PROJECT_TYPE_PIXI
            try:
                with open(manifest_path, 'rb') as f:
                    data = tomllib.load(f)
            except (OSError, tomllib.TOMLDecodeError) as e:
                raise ValueError('Failed to parse {}: {}'.format(manifest_path, e)) from e
            info = _pixi_publication_info(project_dir, data)
            if env_paths:
                _attach_pixi_env_paths(info, project_dir)

        elif manifest_kind == 'anaconda-project':
            project_type = PROJECT_TYPE_ANACONDA_PROJECT
            info = _anaconda_project_publication_info(project_dir, env_paths=env_paths)

        elif manifest_kind == 'pyproject-conda':
            project_type = PROJECT_TYPE_CONDA_WORKSPACES
            try:
                with open(manifest_path, 'rb') as f:
                    pyproject_data = tomllib.load(f)
            except (OSError, tomllib.TOMLDecodeError) as e:
                raise ValueError('Failed to parse {}: {}'.format(manifest_path, e)) from e
            # Extract the [tool.conda] sub-tree
            data = pyproject_data.get('tool', {}).get('conda', {})
            # Also extract the full-document [tool.anaconda.commands] for pyproject-embedded override lookup
            tool_commands = pyproject_data.get('tool', {}).get('anaconda', {}).get('commands', {})
            info = _conda_workspaces_publication_info(project_dir, data, tool_commands=tool_commands)

        elif manifest_kind == 'pyproject-pixi':
            project_type = PROJECT_TYPE_PIXI
            try:
                with open(manifest_path, 'rb') as f:
                    pyproject_data = tomllib.load(f)
            except (OSError, tomllib.TOMLDecodeError) as e:
                raise ValueError('Failed to parse {}: {}'.format(manifest_path, e)) from e
            # Extract the [tool.pixi] sub-tree
            data = pyproject_data.get('tool', {}).get('pixi', {})
            # Also extract the full-document [tool.anaconda.commands] for pyproject-embedded override lookup
            tool_commands = pyproject_data.get('tool', {}).get('anaconda', {}).get('commands', {})
            info = _pixi_publication_info(project_dir, data, tool_commands=tool_commands)
            if env_paths:
                _attach_pixi_env_paths(info, project_dir)

    else:
        # Explicit project_type: recognize both top-level manifests and pyproject.toml embedding
        if project_type == PROJECT_TYPE_CONDA_WORKSPACES:
            manifest_kind, manifest_path = _locate_manifest(project_dir)
            # Accept both 'conda-toml' and 'pyproject-conda' as valid matches for explicit 'conda-workspaces' type
            if manifest_kind not in ('conda-toml', 'pyproject-conda'):
                raise FileNotFoundError(
                    'No conda.toml found in {} (and no [tool.conda.workspace] in pyproject.toml)'.format(project_dir)
                )
            try:
                with open(manifest_path, 'rb') as f:
                    pyproject_data = tomllib.load(f)
            except (OSError, tomllib.TOMLDecodeError) as e:
                raise ValueError('Failed to parse {}: {}'.format(manifest_path, e)) from e
            if manifest_kind == 'conda-toml':
                data = pyproject_data
                tool_commands = None  # Will be auto-derived
            else:  # 'pyproject-conda'
                data = pyproject_data.get('tool', {}).get('conda', {})
                tool_commands = pyproject_data.get('tool', {}).get('anaconda', {}).get('commands', {})
            info = _conda_workspaces_publication_info(project_dir, data, tool_commands=tool_commands)

        elif project_type == PROJECT_TYPE_PIXI:
            manifest_kind, manifest_path = _locate_manifest(project_dir)
            # Accept both 'pixi-toml' and 'pyproject-pixi' as valid matches for explicit 'pixi' type
            if manifest_kind not in ('pixi-toml', 'pyproject-pixi'):
                raise FileNotFoundError(
                    'No pixi.toml found in {} (and no [tool.pixi.workspace] in pyproject.toml)'.format(project_dir)
                )
            try:
                with open(manifest_path, 'rb') as f:
                    pyproject_data = tomllib.load(f)
            except (OSError, tomllib.TOMLDecodeError) as e:
                raise ValueError('Failed to parse {}: {}'.format(manifest_path, e)) from e
            if manifest_kind == 'pixi-toml':
                data = pyproject_data
                tool_commands = None  # Will be auto-derived
            else:  # 'pyproject-pixi'
                data = pyproject_data.get('tool', {}).get('pixi', {})
                tool_commands = pyproject_data.get('tool', {}).get('anaconda', {}).get('commands', {})
            info = _pixi_publication_info(project_dir, data, tool_commands=tool_commands)
            if env_paths:
                _attach_pixi_env_paths(info, project_dir)

        elif project_type == PROJECT_TYPE_ANACONDA_PROJECT:
            # Anaconda-project uses possible_project_file_names for detection
            from anaconda_project.project_file import possible_project_file_names
            ap_path = None
            for filename in possible_project_file_names:
                candidate = os.path.join(project_dir, filename)
                if os.path.isfile(candidate):
                    ap_path = candidate
                    break
            if ap_path is None:
                raise FileNotFoundError(
                    'No {} found in {}'.format(ANACONDA_PROJECT_MANIFEST, project_dir)
                )
            info = _anaconda_project_publication_info(project_dir, env_paths=env_paths)

        else:
            raise ValueError(
                'Unknown project_type {!r}; expected {!r}, {!r}, or {!r}'.format(
                    project_type, PROJECT_TYPE_CONDA_WORKSPACES,
                    PROJECT_TYPE_PIXI, PROJECT_TYPE_ANACONDA_PROJECT
                )
            )

    info[PROJECT_TYPE_KEY] = project_type
    return info


def _anaconda_project_publication_info(project_dir, env_paths=False):
    from anaconda_project.project import Project
    project = Project(project_dir)
    info = project.publication_info()
    if env_paths:
        for name, env in project.env_specs.items():
            if name in info['env_specs']:
                info['env_specs'][name]['path'] = env.path(project_dir)
    return info


def _attach_pixi_env_paths(info, project_dir):
    """Fill in ``info['env_specs'][name]['path']`` and stash the full
    ``pixi info --json`` payload at ``info['_pixi']``.

    Pixi reports prefixes in ``environments_info[].prefix``. Any failure to
    invoke pixi or parse its output raises :class:`RuntimeError` — callers
    only ask for env paths explicitly via ``env_paths=True``, so silent
    fallback would hide bugs.
    """
    import json
    import subprocess
    pixi_path = os.path.join(project_dir, PIXI_MANIFEST)
    try:
        out = subprocess.check_output(
            ['pixi', 'info', '--json', '--manifest-path', pixi_path],
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as e:
        raise RuntimeError('Failed to run `pixi info --json`: {}'.format(e)) from e
    try:
        data = json.loads(out)
    except ValueError as e:
        raise RuntimeError('Could not parse `pixi info --json` output: {}'.format(e)) from e
    for env in data.get('environments_info', []):
        name = env.get('name')
        prefix = env.get('prefix')
        if name in info['env_specs'] and prefix:
            info['env_specs'][name]['path'] = prefix
    info['_pixi'] = data


def _read_pixi_lock_envs(project_dir):
    """Return the set of environment names that appear in pixi.lock, or
    empty if the lockfile is missing, malformed, or can't be loaded.

    Failure is silent by design: lock detection is informational; the
    rest of publication_info should never break because of a corrupt
    lockfile.
    """
    lock_path = os.path.join(project_dir, 'pixi.lock')
    try:
        import yaml
        with open(lock_path, 'r') as f:
            lock = yaml.safe_load(f)
    except Exception:
        return set()
    if not isinstance(lock, dict):
        return set()
    envs = lock.get('environments')
    if not isinstance(envs, dict):
        return set()
    return set(envs.keys())


def _read_conda_lock_envs(project_dir):
    """Return the set of environment names that appear in conda.lock, or
    empty if the lockfile is missing, malformed, or can't be loaded.

    Failure is silent by design: lock detection is informational; the
    rest of publication_info should never break because of a corrupt
    lockfile.
    """
    lock_path = os.path.join(project_dir, 'conda.lock')
    try:
        import yaml
        with open(lock_path, 'r') as f:
            lock = yaml.safe_load(f)
    except Exception:
        return set()
    if not isinstance(lock, dict):
        return set()
    envs = lock.get('environments')
    if not isinstance(envs, dict):
        return set()
    return set(envs.keys())


def _pixi_publication_info(project_dir, data, tool_commands=None):
    """Return a publication-info dict for a pixi project.

    Args:
        project_dir: Path to the project directory.
        data: Pre-parsed pixi manifest dict (from tomllib.load) with top-level
              keys workspace/dependencies/feature/environments/tasks/etc.
        tool_commands: Optional dict of [tool.anaconda.commands] overrides.
              If None (the default), derives from data.get('tool', {}).get('anaconda', {}).get('commands', {}).
              When explicitly passed (even if empty dict), uses that instead of deriving.

    Returns:
        A dict with keys: name, description, commands, env_specs, variables.
    """
    locked_envs = _read_pixi_lock_envs(project_dir)

    workspace = data.get('workspace', {})
    project_meta = data.get('project', {})
    name = workspace.get('name', project_meta.get('name', os.path.basename(project_dir)))
    description = workspace.get('description', project_meta.get('description', ''))
    channels = workspace.get('channels', project_meta.get('channels', []))

    if tool_commands is None:
        tool_commands = data.get('tool', {}).get('anaconda', {}).get('commands', {})

    # Resolve the name of pixi's implicit `default` environment to the
    # user-meaningful env_spec it actually represents. Pixi always
    # materializes a `default` env from the default feature; the
    # exporter (and anaconda-project's own publication_info) report the
    # resolved name, not the placeholder. Logic mirrors the exporter:
    # a literal `default` in [environments] wins; otherwise fall back
    # to the first declared environment.
    declared_envs = data.get('environments', {})
    if 'default' in declared_envs:
        default_env_name = 'default'
    elif declared_envs:
        default_env_name = next(iter(declared_envs))
    else:
        default_env_name = 'default'

    # For tasks defined under [feature.X.tasks.Y], pixi runs them in any
    # env that includes feature X. publication_info should report a
    # specific env that "supports this task": prefer the resolved
    # default if it includes the feature, else the first declared env
    # that does, else fall back to the feature name itself (which is
    # what our own exporter uses — feature name matches env name in the
    # converted manifests).
    def _env_for_feature(feat_name):
        candidate_envs = []
        for env_name, env_def in declared_envs.items():
            features = env_def if isinstance(env_def, list) else env_def.get('features', [])
            if feat_name in features:
                candidate_envs.append(env_name)
        if not candidate_envs:
            return feat_name
        if default_env_name in candidate_envs:
            return default_env_name
        return candidate_envs[0]

    commands = {}
    state = {'first': True}

    for task_name, task_def in data.get('tasks', {}).items():
        cmd = _build_command(task_name, task_def, default_env_name, tool_commands, state)
        if cmd is not None:
            commands[task_name] = cmd

    for feat_name, feat_def in data.get('feature', {}).items():
        for task_name, task_def in feat_def.get('tasks', {}).items():
            if task_name in commands:
                continue
            cmd = _build_command(task_name, task_def,
                                 _env_for_feature(feat_name),
                                 tool_commands, state)
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

    # Pixi always materializes a `default` env, even when [environments]
    # only declares others. Surface it unconditionally; honor the user's
    # declaration if one exists.
    env_specs = {
        'default': {
            'packages': _packages_for_env(declared_envs.get('default')),
            'channels': channels,
            'locked': default_env_name in locked_envs,
        },
    }
    for env_name, env_def in declared_envs.items():
        if env_name == 'default':
            continue
        env_specs[env_name] = {
            'packages': _packages_for_env(env_def),
            'channels': channels,
            'locked': env_name in locked_envs,
        }

    variables = dict(data.get('activation', {}).get('env', {}))

    return {
        'name': name,
        'description': description,
        'commands': commands,
        'env_specs': env_specs,
        'variables': variables,
    }


def _conda_workspaces_publication_info(project_dir, data, tool_commands=None):
    """Return a publication-info dict for a conda-workspaces project.

    Args:
        project_dir: Path to the project directory.
        data: Pre-parsed conda manifest dict (from tomllib.load) with top-level
              keys workspace/dependencies/feature/environments/tasks/etc.
              Same shape as pixi.toml: this may be either a top-level conda.toml
              or the sub-dict from pyproject.toml's [tool.conda].
        tool_commands: Optional dict of [tool.anaconda.commands] overrides.
              If None (the default), derives from data.get('tool', {}).get('anaconda', {}).get('commands', {}).
              When explicitly passed (even if empty dict), uses that instead of deriving.

    Returns:
        A dict with keys: name, description, commands, env_specs, variables.

    Note: PEP 621 [project] name/description fallback (which upstream
    conda-workspaces itself uses for pyproject.toml) is not read; only
    workspace.name/workspace.description are considered, falling back to the
    directory basename. This is a deliberate omission for this plan's scope
    (uniform read-side summary), not a gap.
    """
    locked_envs = _read_conda_lock_envs(project_dir)

    workspace = data.get('workspace', {})
    # Conda.toml has no [project] legacy-alias table; skip that fallback
    name = workspace.get('name', os.path.basename(project_dir))
    description = workspace.get('description', '')
    channels = workspace.get('channels', [])

    if tool_commands is None:
        tool_commands = data.get('tool', {}).get('anaconda', {}).get('commands', {})

    # Resolve the default environment name (same logic as pixi)
    declared_envs = data.get('environments', {})
    if 'default' in declared_envs:
        default_env_name = 'default'
    elif declared_envs:
        default_env_name = next(iter(declared_envs))
    else:
        default_env_name = 'default'

    # For tasks defined under [feature.X.tasks.Y], conda-workspaces runs them in any
    # env that includes feature X. Same logic as pixi.
    def _env_for_feature(feat_name):
        candidate_envs = []
        for env_name, env_def in declared_envs.items():
            features = env_def if isinstance(env_def, list) else env_def.get('features', [])
            if feat_name in features:
                candidate_envs.append(env_name)
        if not candidate_envs:
            return feat_name
        if default_env_name in candidate_envs:
            return default_env_name
        return candidate_envs[0]

    commands = {}
    state = {'first': True}

    for task_name, task_def in data.get('tasks', {}).items():
        cmd = _build_command(task_name, task_def, default_env_name, tool_commands, state)
        if cmd is not None:
            commands[task_name] = cmd

    for feat_name, feat_def in data.get('feature', {}).items():
        for task_name, task_def in feat_def.get('tasks', {}).items():
            if task_name in commands:
                continue
            cmd = _build_command(task_name, task_def,
                                 _env_for_feature(feat_name),
                                 tool_commands, state)
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

    # Conda-workspaces always materializes a `default` env, even when [environments]
    # only declares others. Surface it unconditionally; honor the user's
    # declaration if one exists.
    env_specs = {
        'default': {
            'packages': _packages_for_env(declared_envs.get('default')),
            'channels': channels,
            'locked': default_env_name in locked_envs,
        },
    }
    for env_name, env_def in declared_envs.items():
        if env_name == 'default':
            continue
        env_specs[env_name] = {
            'packages': _packages_for_env(env_def),
            'channels': channels,
            'locked': env_name in locked_envs,
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
        raw_args = []
    elif isinstance(task_def, dict):
        cmd_str = task_def.get('cmd', '')
        if task_def.get('environment'):
            env_spec = task_def['environment']
        raw_args = task_def.get('args') or []
    else:
        return None

    # Pixi `args` entries are inline tables like { arg = "port", default = "" }
    # or bare strings like "name". Pull just the names, in declaration order;
    # downstream tooling uses this to know which positional values to supply
    # to `pixi run <task>`.
    args = []
    for entry in raw_args:
        if isinstance(entry, dict):
            name = entry.get('arg')
        elif isinstance(entry, str):
            name = entry
        else:
            name = None
        if name:
            args.append(name)

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
        'args': args,
    }


def _format_dep(name, spec):
    # Pixi inline-table specs like `numpy = { version = ">=2.0" }` arrive
    # as a dict; pull the version out so the round-trip keeps the
    # constraint instead of dropping to a bare package name. Other dict
    # keys (channel, build, etc.) don't have a place in the conda spec
    # string form we emit, so we ignore them.
    if isinstance(spec, dict):
        spec = spec.get('version')
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
