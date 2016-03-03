from __future__ import absolute_import, print_function

import os

_minimal_environ = None

system_vars_to_keep = ('PATH', 'LD_LIBRARY_PATH', 'TERM', 'PYTHONPATH')


def minimal_environ(**additions):
    """Get an environment with minimal likely weird side effects on tests, while still working."""
    global _minimal_environ

    if _minimal_environ is None:
        _minimal_environ = dict()
        for name in system_vars_to_keep:
            if name in os.environ:
                _minimal_environ[name] = os.environ[name]

    if len(additions) > 0:
        copy = _minimal_environ.copy()
        for (key, value) in additions.items():
            copy[key] = value
        return copy
    else:
        return _minimal_environ


def strip_environ(environ):
    """Pull system variables back out of our minimal environ so we can check test results without noise."""
    copy = environ.copy()
    for name in system_vars_to_keep:
        if name in copy:
            del copy[name]
    return copy
