"""The ``activate`` command which prepares a project to run and prints commands to source in your shell."""
from __future__ import absolute_import, print_function

from copy import deepcopy
import os
import sys

from project.prepare import prepare, UI_MODE_NOT_INTERACTIVE
from project.project import Project


def activate(dirname, ui_mode):
    """Prepare project and return lines to be sourced.

    Future direction: should also activate the proper conda env.

    Returns:
        None on failure or a list of lines to print.
    """
    environ = deepcopy(os.environ)
    project = Project(dirname)
    result = prepare(project, ui_mode=ui_mode, environ=environ)
    if not result:
        return None

    result = []
    # sort so we have deterministic output order for tests
    sorted_keys = list(environ.keys())
    sorted_keys.sort()
    for key in sorted_keys:
        value = environ[key]
        if key not in os.environ or os.environ[key] != value:
            result.append("export {key}={value}".format(key=key, value=value))
    return result


def main(argv):
    """Start the activate command."""
    # future: real arg parser
    if len(argv) > 1:
        dirname = argv[1]
    else:
        dirname = "."
    dirname = os.path.abspath(dirname)
    result = activate(dirname, ui_mode=UI_MODE_NOT_INTERACTIVE)
    if result is None:
        sys.exit(1)
    else:
        for line in result:
            print(line)
        sys.exit(0)
