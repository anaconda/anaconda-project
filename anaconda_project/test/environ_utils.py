# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import os

from anaconda_project.internal import conda_api

# we keep the conda env variables because otherwise
# we'd have to keep recreating project-specific conda envs in our tests
system_vars_to_keep = (
    'PATH',
    'LD_LIBRARY_PATH',
    'TERM',
    'PYTHONPATH',
    'HOME',
    # Windows stuff
    'SystemRoot',
    'SystemDrive',
    'OS',
    'ProgramData',
    'ProgramFiles',
    'LOCALAPPDATA',
    'HOMEDRIVE',
    'HOMEPATH')
conda_vars_to_keep = ('CONDA_DEFAULT_ENV', 'CONDA_ENV_PATH', 'CONDA_PREFIX')


def _minimal_environ_full(with_conda_env, **additions):
    minimal_environ = dict()
    for name in (system_vars_to_keep + conda_vars_to_keep):
        if name in os.environ:
            minimal_environ[name] = os.environ[name]

    env_prefix = conda_api.environ_get_prefix(minimal_environ)

    if len(additions) > 0 or not with_conda_env:
        if not with_conda_env:
            for name in conda_vars_to_keep:
                if name in minimal_environ:
                    del minimal_environ[name]

        for (key, value) in additions.items():
            minimal_environ[key] = value

    return (env_prefix, minimal_environ)


def minimal_environ(**additions):
    """Get an environment with minimal likely weird side effects on tests, while still working."""
    return _minimal_environ_full(with_conda_env=True, **additions)[1]


def minimal_environ_no_conda_env(**additions):
    """Get a minimal environment without the conda env in it."""
    return _minimal_environ_full(with_conda_env=False, **additions)[1]


def env_prefix_and_minimal_environ(**additions):
    """Get a tuple of env_prefix and minimal environ without conda vars."""
    return _minimal_environ_full(with_conda_env=False, **additions)


def strip_environ(environ):
    """Pull system variables back out of our minimal environ so we can check test results without noise."""
    copy = environ.copy()
    for name in (system_vars_to_keep + conda_vars_to_keep):
        if name in copy:
            del copy[name]
    return copy


def strip_environ_keeping_conda_env(environ):
    """Pull system variables back out of our minimal environ so we can check test results without noise."""
    copy = environ.copy()
    for name in system_vars_to_keep:
        if name in copy:
            del copy[name]
    return copy
