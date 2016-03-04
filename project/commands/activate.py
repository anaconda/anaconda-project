"""The ``activate`` command which prepares a project to run and prints commands to source in your shell."""
from __future__ import absolute_import, print_function

import os
import sys

try:
    from shlex import quote  # pragma: no cover (py3 only)
except ImportError:  # pragma: no cover (py2 only)
    from pipes import quote

from project.prepare import prepare, UI_MODE_NOT_INTERACTIVE
from project.project import Project


def activate(dirname, ui_mode):
    """Prepare project and return lines to be sourced.

    Future direction: should also activate the proper conda env.

    Returns:
        None on failure or a list of lines to print.
    """
    project = Project(dirname)
    result = prepare(project, ui_mode=ui_mode)
    if result.failed:
        result.print_output()
        return None

    exports = []
    # sort so we have deterministic output order for tests
    sorted_keys = list(result.environ.keys())
    sorted_keys.sort()
    for key in sorted_keys:
        value = result.environ[key]
        if key not in os.environ or os.environ[key] != value:
            exports.append("export {key}={value}".format(key=key, value=quote(value)))
    return exports


def main(args):
    """Start the activate command."""
    dirname = os.path.abspath(args.dirname)
    result = activate(dirname, ui_mode=UI_MODE_NOT_INTERACTIVE)
    if result is None:
        sys.exit(1)
    else:
        for line in result:
            print(line)
        sys.exit(0)
