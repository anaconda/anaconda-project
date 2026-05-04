# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Convert an anaconda-project Project to pixi.toml format."""
from __future__ import absolute_import, print_function

import os
import re

from anaconda_project.requirements_registry.requirement import EnvVarRequirement
from anaconda_project.requirements_registry.requirements.conda_env import CondaEnvRequirement
from anaconda_project.requirements_registry.requirements.download import DownloadRequirement
from anaconda_project.requirements_registry.requirements.service import ServiceRequirement


def _toml_string(value):
    escaped = value.replace('\\', '\\\\').replace('"', '\\"')
    escaped = escaped.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    return '"{}"'.format(escaped)


def _toml_inline_array(items):
    return '[{}]'.format(', '.join(_toml_string(i) for i in items))


def _conda_spec_to_pixi(spec):
    """Convert a conda package spec string to (name, version_constraint).

    Examples:
        'numpy' -> ('numpy', '*')
        'numpy>=1.20' -> ('numpy', '>=1.20')
        'numpy=1.20' -> ('numpy', '1.20.*')
        'numpy==1.20' -> ('numpy', '==1.20')
        'numpy=1.20.3=py39_0' -> ('numpy', '==1.20.3')
        'conda-forge::numpy' -> ('numpy', '*')
        'conda-forge::numpy>=1.0' -> ('numpy', '>=1.0')
    """
    # Strip channel prefix (e.g. conda-forge::numpy)
    if '::' in spec:
        spec = spec.split('::', 1)[1]

    # Match name and optional version constraint
    m = re.match(r'^([a-zA-Z0-9_][a-zA-Z0-9_.\-]*)(.*)$', spec)
    if not m:
        return spec, '*'

    name = m.group(1)
    version_part = m.group(2).strip()

    if not version_part:
        return name, '*'

    # Exact pin with build string: numpy=1.20.3=py39_0
    if re.match(r'^=[^=].*=', version_part):
        version = version_part.split('=')[1]
        return name, '=={}'.format(version)

    # Single = means glob: numpy=1.20 -> 1.20.*
    if version_part.startswith('=') and not version_part.startswith('=='):
        version = version_part.lstrip('=')
        if '*' not in version:
            version = version + '.*'
        return name, version

    # Already has operator (>=, <=, ==, !=, <, >, etc.)
    return name, version_part


def _format_dep_value(version):
    if version == '*':
        return '"*"'
    return _toml_string(version)


def _write_dependencies(lines, conda_packages, pip_packages, indent=''):
    """Write [dependencies] and [pypi-dependencies] sections."""
    if conda_packages:
        lines.append('{}[dependencies]'.format(indent))
        for spec in sorted(conda_packages, key=lambda s: _conda_spec_to_pixi(s)[0].lower()):
            name, version = _conda_spec_to_pixi(spec)
            lines.append('{}{} = {}'.format(indent, name, _format_dep_value(version)))
        lines.append('')

    if pip_packages:
        lines.append('{}[pypi-dependencies]'.format(indent))
        for spec in sorted(pip_packages):
            # pip specs are already in pip format (e.g. "package>=1.0")
            m = re.match(r'^([a-zA-Z0-9_][a-zA-Z0-9_.\-]*(?:\[[^\]]*\])?)\s*(.*)?$', spec)
            if m:
                name = m.group(1)
                version = m.group(2).strip() if m.group(2) else '*'
                lines.append('{}{} = {}'.format(indent, name, _format_dep_value(version)))
        lines.append('')


def _command_to_task(command):
    """Convert a ProjectCommand to a pixi task string or None.

    Returns (task_cmd_string, comment_or_none).
    """
    # Prefer unix command, fall back to notebook/bokeh
    if command.unix_shell_commandline:
        return command.unix_shell_commandline, None
    if command.notebook is not None:
        return 'jupyter notebook {}'.format(command.notebook), 'converted from notebook command'
    if command.bokeh_app is not None:
        return 'bokeh serve {}'.format(command.bokeh_app), 'converted from bokeh_app command'
    if command.windows_cmd_commandline:
        return command.windows_cmd_commandline, 'windows-only command'
    return None, None


def export_pixi_toml(project):
    """Convert an anaconda-project Project to pixi.toml content.

    Args:
        project: an anaconda_project.project.Project instance

    Returns:
        A string containing the pixi.toml file content.
    """
    lines = []

    # -- [project] metadata
    lines.append('[project]')
    lines.append('name = {}'.format(_toml_string(project.name)))
    if project.description:
        lines.append('description = {}'.format(_toml_string(project.description)))
    lines.append('')

    # -- [workspace] channels and platforms
    # Collect channels from all env specs (union, preserving order)
    all_channels = []
    seen_channels = set()
    for env in project.env_specs.values():
        for ch in env.channels:
            if ch not in seen_channels:
                all_channels.append(ch)
                seen_channels.add(ch)

    # Collect platforms (union)
    all_platforms = set()
    for env in project.env_specs.values():
        all_platforms.update(env.platforms)
    if not all_platforms:
        all_platforms = {'linux-64'}

    lines.append('[workspace]')
    if all_channels:
        lines.append('channels = {}'.format(_toml_inline_array(all_channels)))
    else:
        lines.append('channels = ["conda-forge"]')
    lines.append('platforms = {}'.format(_toml_inline_array(sorted(all_platforms))))
    lines.append('')

    # -- Determine if we need features (multiple env specs)
    env_specs = project.env_specs
    has_multiple_envs = len(env_specs) > 1 or (len(env_specs) == 1 and 'default' not in env_specs)

    # -- Collect global (inherited by all) packages
    # The anonymous base spec's packages are the global ones.
    # In the project model, these are the top-level packages/channels.
    # env_spec.conda_packages includes inherited, so we find the common set.
    if has_multiple_envs:
        # Find packages common to all env specs (the global/inherited ones)
        all_conda = None
        all_pip = None
        for env in env_specs.values():
            conda_set = set(env.conda_packages)
            pip_set = set(env.pip_packages)
            if all_conda is None:
                all_conda = conda_set
                all_pip = pip_set
            else:
                all_conda &= conda_set
                all_pip &= pip_set

        global_conda = sorted(all_conda) if all_conda else []
        global_pip = sorted(all_pip) if all_pip else []
    elif env_specs:
        # Single env — everything is global
        env = list(env_specs.values())[0]
        global_conda = list(env.conda_packages)
        global_pip = list(env.pip_packages)
    else:
        global_conda = []
        global_pip = []

    # Write global dependencies
    _write_dependencies(lines, global_conda, global_pip)

    # -- [activation] for variables
    variables_with_defaults = {}
    for req in project.requirements(project.default_env_spec_name):
        if isinstance(req, (CondaEnvRequirement, DownloadRequirement, ServiceRequirement)):
            continue
        if isinstance(req, EnvVarRequirement):
            default = req.default_as_string
            if default is not None:
                variables_with_defaults[req.env_var] = default

    if variables_with_defaults:
        lines.append('[activation.env]')
        for var_name in sorted(variables_with_defaults):
            lines.append('{} = {}'.format(var_name, _toml_string(variables_with_defaults[var_name])))
        lines.append('')

    # -- Features for non-default env specs
    if has_multiple_envs:
        global_conda_set = set(global_conda)
        global_pip_set = set(global_pip)

        for env_name, env in sorted(env_specs.items()):
            if env_name == 'default' and not (set(env.conda_packages) - global_conda_set):
                continue

            extra_conda = [p for p in env.conda_packages if p not in global_conda_set]
            extra_pip = [p for p in env.pip_packages if p not in global_pip_set]

            if extra_conda or extra_pip:
                if extra_conda:
                    lines.append('[feature.{}.dependencies]'.format(env_name))
                    for spec in sorted(extra_conda, key=lambda s: _conda_spec_to_pixi(s)[0].lower()):
                        name, version = _conda_spec_to_pixi(spec)
                        lines.append('{} = {}'.format(name, _format_dep_value(version)))
                    lines.append('')

                if extra_pip:
                    lines.append('[feature.{}.pypi-dependencies]'.format(env_name))
                    for spec in sorted(extra_pip):
                        m = re.match(r'^([a-zA-Z0-9_][a-zA-Z0-9_.\-]*(?:\[[^\]]*\])?)\s*(.*)?$', spec)
                        if m:
                            name = m.group(1)
                            version = m.group(2).strip() if m.group(2) else '*'
                            lines.append('{} = {}'.format(name, _format_dep_value(version)))
                    lines.append('')

        # -- [environments] section
        lines.append('[environments]')
        for env_name in sorted(env_specs):
            if env_name == 'default':
                lines.append('default = { solve-group = "default" }')
            else:
                lines.append('{name} = {{ features = ["{name}"], solve-group = "default" }}'.format(name=env_name))
        lines.append('')

    # -- [tasks] from commands
    commands = project.commands
    if commands:
        # Only emit [tasks] header if there are global (non-feature) tasks
        global_tasks = []
        feature_tasks = []
        for cmd_name, command in sorted(commands.items()):
            env_spec_name = command.default_env_spec_name
            if has_multiple_envs and env_spec_name and env_spec_name != 'default':
                feature_tasks.append((cmd_name, command))
            else:
                global_tasks.append((cmd_name, command))

        if global_tasks:
            lines.append('[tasks]')
            for cmd_name, command in global_tasks:
                task_cmd, comment = _command_to_task(command)
                if task_cmd is None:
                    lines.append('# {} — could not convert (no unix command)'.format(cmd_name))
                    continue
                desc = command.description
                has_desc = desc and desc != cmd_name and desc != task_cmd
                if comment:
                    lines.append('# {}'.format(comment))
                if has_desc:
                    lines.append('{} = {{ cmd = {}, description = {} }}'.format(
                        cmd_name, _toml_string(task_cmd), _toml_string(desc)))
                else:
                    lines.append('{} = {}'.format(cmd_name, _toml_string(task_cmd)))
            lines.append('')

        for cmd_name, command in feature_tasks:
            task_cmd, comment = _command_to_task(command)
            if task_cmd is None:
                lines.append('# {} — could not convert (no unix command)'.format(cmd_name))
                continue
            desc = command.description
            env_spec_name = command.default_env_spec_name
            has_desc = desc and desc != cmd_name and desc != task_cmd
            section = 'feature.{}.tasks.{}'.format(env_spec_name, cmd_name)
            lines.append('[{}]'.format(section))
            lines.append('cmd = {}'.format(_toml_string(task_cmd)))
            if has_desc:
                lines.append('description = {}'.format(_toml_string(desc)))
            if comment:
                lines.append('# {}'.format(comment))
            lines.append('')

    # -- Downloads as comments (no pixi equivalent)
    downloads = {}
    for env_name in env_specs:
        for req in project.requirements(env_name):
            if isinstance(req, DownloadRequirement):
                downloads[req.env_var] = req.url

    if downloads:
        lines.append('# Downloads from anaconda-project.yml (no pixi equivalent).')
        lines.append('# Consider adding setup tasks to fetch these:')
        for var_name, url in sorted(downloads.items()):
            lines.append('#   {} = {}'.format(var_name, url))
        lines.append('')

    # -- Services as comments
    services = {}
    for env_name in env_specs:
        for req in project.requirements(env_name):
            if isinstance(req, ServiceRequirement):
                services[req.env_var] = req.service_type

    if services:
        lines.append('# Services from anaconda-project.yml (no pixi equivalent):')
        for var_name, svc_type in sorted(services.items()):
            lines.append('#   {} = {}'.format(var_name, svc_type))
        lines.append('')

    # -- Variables without defaults as comments
    vars_without_defaults = {}
    for req in project.requirements(project.default_env_spec_name):
        if isinstance(req, (CondaEnvRequirement, DownloadRequirement, ServiceRequirement)):
            continue
        if isinstance(req, EnvVarRequirement) and req.default_as_string is None:
            vars_without_defaults[req.env_var] = req.description or ''

    if vars_without_defaults:
        lines.append('# Required environment variables (set these before running):')
        for var_name, desc in sorted(vars_without_defaults.items()):
            if desc:
                lines.append('#   {} — {}'.format(var_name, desc))
            else:
                lines.append('#   {}'.format(var_name))
        lines.append('')

    return '\n'.join(lines).rstrip() + '\n'
