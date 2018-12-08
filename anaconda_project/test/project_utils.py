# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from anaconda_project.project import Project
from anaconda_project.local_state_file import LocalStateFile
from anaconda_project.internal.test.fake_frontend import FakeFrontend


def project_dir_disable_dedicated_env(dirname):
    """Modify project config to disable having a dedicated environment."""
    local_state = LocalStateFile.load_for_directory(dirname)
    local_state.set_value('inherit_environment', True)
    local_state.save()


def project_no_dedicated_env(*args, **kwargs):
    """Get a project that won't create envs/default as long as there's an env already."""
    if len(args) > 0:
        dirname = args[0]
    elif 'directory_path' in kwargs:
        dirname = kwargs['directory_path']
    else:
        raise RuntimeError("no directory_path for Project")

    project_dir_disable_dedicated_env(dirname)

    if 'frontend' not in kwargs:
        kwargs['frontend'] = FakeFrontend()

    project = Project(*args, **kwargs)

    return project


def assert_identical_except_blank_lines(f1, f2):
    """Compare two files that should be identical, ignoring blank lines."""
    f1 = [c for c in f1.splitlines() if c.strip()]
    f2 = [c for c in f2.splitlines() if c.strip()]
    assert f1 == f2
