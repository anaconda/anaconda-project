"""Shell command line manipulation."""
from __future__ import absolute_import

import shlex


def shell_split_command_line(command):
    return shlex.split(command)


def shell_join_command_line(args):
    quoted = []
    for arg in args:
        quoted.append(shlex.quote(arg))
    return " ".join(quoted)
