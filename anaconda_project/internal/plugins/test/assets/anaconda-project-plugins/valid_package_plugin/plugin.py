# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2017, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from anaconda_project.plugins import ArgsTrasformerTemplate, CommandTemplate


class ArgsTransformer(ArgsTrasformerTemplate):
    def add_args(self, results, args):
        added = ['--show']
        for (option, values) in results:
            if option in ('--anaconda-project-host', '--anaconda-project-port', '--anaconda-project-address'):
                for v in values:
                    added.append(option.replace('anaconda-project-', 'custom-cmd-'))
                    added.append(v)

        return added + args


class ProjectCommand(CommandTemplate):
    command = 'custom-cmd'
    args_transformer_cls = ArgsTransformer

    def choose_args_and_shell(self, environ, extra_args=None):
        assert extra_args is None or isinstance(extra_args, list)

        shell = False
        args = [self.command_with_conda_prefix, 'custom-sub-cmd', '--%s.TESTARG' % self.command]
        args = args + extra_args
        return args, shell
