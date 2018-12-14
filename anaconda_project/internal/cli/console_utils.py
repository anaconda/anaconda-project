# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Utilities for implementing console interaction."""
from __future__ import absolute_import, print_function

import getpass
import sys

_PY2 = sys.version_info[0] == 2


def print_project_problems(project):
    """Print project problems to stderr, and return True if there were problems."""
    if project.problems:
        for problem in project.problems:
            print(problem, file=sys.stderr)
        print("Unable to load the project.", file=sys.stderr)
        return True
    else:
        return False


def print_status_errors(status):
    """Print out status description to stderr."""
    assert status is not None
    # don't print status.errors because we will have done that
    # already in streaming fashion from our Frontend.
    print(status.status_description, file=sys.stderr)


def format_names_and_descriptions(objects, name_attr='name', description_attr='description'):
    """Format a table with names on the left and descriptions on the right."""
    pairs = []
    for o in objects:
        name = getattr(o, name_attr)
        description = getattr(o, description_attr)
        pairs.append((name, description))

    # deterministic order
    pairs = sorted(pairs, key=lambda p: p[0])

    # add headers if there's anything in the list
    if len(pairs) > 0:
        pairs = [("Name", "Description"), ("====", "===========")] + pairs

    # format as table
    max_name_len = 0
    for pair in pairs:
        max_name_len = max(len(pair[0]), max_name_len)
    table = ""
    for pair in pairs:
        if pair[0] == pair[1]:
            # skip useless description
            line = pair[0]
        else:
            line = pair[0].ljust(max_name_len) + "  " + pair[1]
        table = table + line + "\n"
    if table == "":
        return "\n"
    else:
        return table


def print_names_and_descriptions(objects, name_attr='name', description_attr='description'):
    """Print a table with names on the left and descriptions on the right."""
    output = format_names_and_descriptions(objects, name_attr=name_attr, description_attr=description_attr)
    # we chop the newline off
    print(output[:-1])


def stdin_is_interactive():
    """True if stdin is a tty."""
    return sys.stdin.isatty()


# this "_input" wrapper exists to let us mock "input" because
# pytest makes it pesky to mock builtin functions that vary across
# python versions.  Python 2 has "input" and "raw_input" where
# "input" is eval(raw_input()).  Python 3 renames "raw_input" to
# "input".
def _input(prompt):
    if _PY2:  # pragma: no cover
        return raw_input(prompt)  # noqa # pragma: no cover (py2 only)
    else:
        return input(prompt)  # noqa # pragma: no cover


def console_input(prompt, encrypted=False):
    """Wrapper for raw_input (py2) and input (py3).

    Returns None on EOF.
    """
    try:
        if encrypted:
            return getpass.getpass(prompt)
        else:
            return _input(prompt)
    except EOFError:
        return None
    except KeyboardInterrupt:
        print("\nCanceling\n", file=sys.stderr)
        sys.exit(1)


def console_ask_yes_or_no(prompt, default):
    """Ask a yes or no question, returning a bool.

    Returns default if not on a console or EOF.
    """
    if not stdin_is_interactive():
        return default

    # show the "(enter y or n)" clutter only the second time around
    extra = ""
    while True:
        reply = console_input(prompt + extra + " ")
        if reply is None:
            return default

        if len(reply) > 0:
            if reply[0] in ('y', 'Y'):
                return True
            elif reply[0] in ('n', 'N'):
                return False

        extra = " (enter y or n):"
