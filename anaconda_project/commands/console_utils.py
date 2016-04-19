# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Utilities for implementing console interaction."""
from __future__ import absolute_import, print_function

import sys


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
    """Print errors from the status."""
    assert status is not None
    for log in status.logs:
        print(log, file=sys.stderr)
    for error in status.errors:
        print(error, file=sys.stderr)
    print(status.status_description, file=sys.stderr)


def stdin_is_interactive():
    """True if stdin is a tty."""
    return sys.stdin.isatty()


def _input(prompt):
    # builtins are annoying to mock especially when they are python-version-specific)
    try:  # pragma: no cover
        return input(prompt)  # flake8: noqa # pragma: no cover
    except NameError:  # pragma: no cover
        return raw_input(prompt)  # flake8: noqa # pragma: no cover (py2 only)


def console_input(prompt):
    """Wrapper for raw_input (py2) and input (py3).

    Returns None on EOF.
    """
    try:
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
