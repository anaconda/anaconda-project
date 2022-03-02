# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2017, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------

try:
    from entrypoints import get_group_named
except ImportError:  # py 2.7
    from pkg_resources import iter_entry_points

    def get_group_named(group_name):
        """Facade function to align old entry_points api to new one."""
        return {plugin.name: plugin for plugin in iter_entry_points(group_name)}


def _get_entry_points_plugins(entry_point_group):
    """Return all the entry points plugins registered."""
    return {name: plugin.load() for name, plugin in sorted(get_group_named(entry_point_group).items())}


def get_plugins(plugin_hook_type):
    """Return all the entry points plugins registered that implement that hook.

    The function will return all the plugins that implement the specified
    type of hook.

    Args:
        - plugin_hook_type(str): type of hook

    Output:
        (dict) with plugin name as key and plugin generator function as value
    """
    command_type = 'anaconda_project.plugins.%s' % plugin_hook_type
    entry_point_plugins = _get_entry_points_plugins(entry_point_group=command_type)

    return entry_point_plugins
