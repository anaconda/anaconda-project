# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Plugins base classes and functions."""
import os
from os.path import join
from anaconda_project.project_commands import (_ArgsTransformer, ProjectCommand, _http_specs)

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


class ArgsTrasformerTemplate(_ArgsTransformer):
    """Template class for plugins args trasformers.

    Plugins args transformers should subclass it and redefine add_class
    to implement custom arguments mapping.
    """

    def __init__(self, command):
        """Construct an ArgTransformer for the given command.

        Args:
            command (ProjectCommand): command that maps to the ArgsTransformer
        """
        super(ArgsTrasformerTemplate, self).__init__(_http_specs)
        self.command = command

    def add_args(self, results, args):
        """Overwrite this method to add custom arguments transformation.

        It should forwarding the arguments that are custom to the
        specific command served by this trasformer (
            i.e., '--anaconda-project-host' --> 'host'
        )

        Inputs:
            - results [list(tuples)]: list of 2 element tuples (option, values):
                           * option (str): name of the option
                            * values (lst(str)): list of the values passed
                                        for the option
            - args [list]: list of the args already passed in

        Returns:
            (list) list of the transformed args (that should include args)
        """
        raise RuntimeError("not implemented")  # pragma: no cover


class CommandTemplate(ProjectCommand):
    """Represents a command from the project file."""

    args_transformer_cls = None

    def __init__(self, name, attributes):
        """Construct a command with the given attributes.

        Args:
            name (str): name of the command
            attributes (dict): named attributes of the command
        """
        super(CommandTemplate, self).__init__(name=name, attributes=attributes)
        self._args_transformer = self.args_transformer_cls(self)

    @property
    def command_with_conda_prefix(self):
        """Full command path pointing to <conda prefix>/bin."""
        return join(os.environ['CONDA_PREFIX'], 'bin', self.command)

    def _choose_args_and_shell(self, environ, extra_args=None):
        """Prepare extra args calling class _args_trasform.transform_args."""
        extra_args = self._args_transformer.transform_args(extra_args)
        return self.choose_args_and_shell(environ, extra_args=extra_args)

    def choose_args_and_shell(self, environ, extra_args=None):
        """Overwrite this method to implement custom plugin logic."""
        raise NotImplementedError()
