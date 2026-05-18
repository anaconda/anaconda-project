# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2026, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""`anaconda-project info` — human-readable summary of publication_info."""
from __future__ import absolute_import, print_function

import json
import sys

from anaconda_project.project_info import (
    PROJECT_TYPE_PIXI,
    PROJECT_TYPE_KEY,
    publication_info,
)


def _format_section(title):
    return '{}\n{}'.format(title, '-' * 12)


def _format_label_value(label, value, width=18):
    return '{:>{w}}: {}'.format(label, value, w=width)


def _format_label_continuation(value, width=18):
    return '{:>{w}}: {}'.format('', value, w=width)


def _format_list(label, items, width=18):
    """Format a label with a list of values, one per line, joined by ', '
    on overflow. Mirrors `pixi info`'s layout for `Dependencies:`."""
    if not items:
        return _format_label_value(label, '', width=width)
    return _format_label_value(label, ', '.join(items), width=width)


def _print_text(info, project_dir):
    """Render info as text, modeled on `pixi info`."""
    project_type = info.get(PROJECT_TYPE_KEY, '<unknown>')
    print(_format_section('Project'))
    print(_format_label_value('Type', project_type))
    print(_format_label_value('Name', info.get('name', '')))
    if info.get('description'):
        print(_format_label_value('Description', info['description']))
    print(_format_label_value('Directory', project_dir))
    print()

    commands = info.get('commands') or {}
    if commands:
        print(_format_section('Commands'))
        for name, cmd in commands.items():
            tags = []
            if cmd.get('default'):
                tags.append('default')
            if cmd.get('notebook'):
                tags.append('notebook')
            elif cmd.get('bokeh_app'):
                tags.append('bokeh_app')
            if cmd.get('supports_http_options'):
                tags.append('http')
            header = name
            if tags:
                header = '{}  [{}]'.format(name, ', '.join(tags))
            print(_format_label_value('Command', header))
            if cmd.get('env_spec'):
                print(_format_label_continuation('env_spec: {}'.format(cmd['env_spec'])))
            run_line = cmd.get('unix') or cmd.get('windows') or cmd.get('notebook') or cmd.get('bokeh_app') or ''
            if run_line:
                print(_format_label_continuation('cmd: {}'.format(run_line)))
            if cmd.get('args'):
                print(_format_label_continuation('args: {}'.format(', '.join(cmd['args']))))
            if cmd.get('description') and cmd['description'] != run_line:
                print(_format_label_continuation('desc: {}'.format(cmd['description'])))
            print()

    env_specs = info.get('env_specs') or {}
    if env_specs:
        print(_format_section('Environments'))
        for name, env in env_specs.items():
            print(_format_label_value('Environment', name))
            channels = env.get('channels') or []
            print(_format_list('Channels', channels))
            packages = env.get('packages') or []
            print(_format_label_value('Dependency count', len(packages)))
            if packages:
                print(_format_list('Dependencies', packages))
            platforms = env.get('platforms')
            if platforms:
                print(_format_list('Target platforms', platforms))
            print(_format_label_value('Locked', 'yes' if env.get('locked') else 'no'))
            if 'path' in env:
                print(_format_label_value('Prefix location', env['path']))
            print()

    variables = info.get('variables') or {}
    if variables:
        print(_format_section('Variables'))
        for name, value in variables.items():
            if isinstance(value, dict):
                # anaconda-project shape: {title, description, encrypted, default}
                rendered = value.get('default', '')
            else:
                rendered = value
            print(_format_label_value(name, rendered))
        print()


def info_main(project_dir, as_json, env_paths, project_type):
    """Show a human-readable view of `publication_info(project_dir)`.

    With ``as_json``, emit the indented JSON instead.
    """
    try:
        info = publication_info(
            project_dir,
            project_type=project_type,
            env_paths=env_paths,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print('{}'.format(e), file=sys.stderr)
        return 1

    if as_json:
        # Match `pixi info --json`: indented, sorted-keys-off so order
        # reflects insertion order (env_specs in declared order, etc).
        print(json.dumps(info, indent=2, default=str))
        return 0

    _print_text(info, project_dir)
    return 0


def main(args):
    """Argparse entry point for `anaconda-project info`."""
    return info_main(
        project_dir=args.directory,
        as_json=args.json,
        env_paths=args.env_paths,
        project_type=args.project_type,
    )
