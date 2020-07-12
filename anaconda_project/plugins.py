# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Plugins base classes and functions."""
import os
from os.path import join
from anaconda_project.project_commands import (_ArgsTransformer, ProjectCommand)


class ArgsTransformerTemplate(_ArgsTransformer):
    """Template class for plugins args trasformers.

    Plugins args transformers should subclass it and redefine add_class
    to implement custom arguments mapping.
    """
    def __init__(self, command):
        """Construct an ArgTransformer for the given command.

        Args:
            command (ProjectCommand): command that maps to the ArgsTransformer
        """
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

    # ArgsTransformer to be used to parse args before forwarding them
    # to the actual command args and shell builder (choose_args_and_shell)
    args_transformer_cls = None

    # Base command to be executed. This should be overwritten by the
    # child class. I.e. command=`python` for a hypotetical python
    # command
    command = None

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


# Some other packages depend upon this typo from 0.8.2 and earlier
ArgsTrasformerTemplate = ArgsTransformerTemplate
