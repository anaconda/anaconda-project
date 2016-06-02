# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import os
import platform
import pytest

from anaconda_project.package_set import PackageSet
from anaconda_project.conda_manager import CondaManagerError

from anaconda_project.internal.default_conda_manager import DefaultCondaManager

from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.internal.test.test_conda_api import monkeypatch_conda_not_to_use_links

if platform.system() == 'Windows':
    PYTHON_BINARY = "python.exe"
    IPYTHON_BINARY = "Scripts\ipython.exe"
else:
    PYTHON_BINARY = "bin/python"
    IPYTHON_BINARY = "bin/ipython"


def test_conda_create_and_install_and_remove(monkeypatch):
    monkeypatch_conda_not_to_use_links(monkeypatch)

    spec = PackageSet(name='myenv', dependencies=['ipython'], channels=[])

    def do_test(dirname):
        envdir = os.path.join(dirname, spec.name)

        manager = DefaultCondaManager()

        assert not os.path.isdir(envdir)

        deviations = manager.find_environment_deviations(envdir, spec)

        manager.fix_environment_deviations(envdir, spec, deviations)

        assert os.path.isdir(envdir)
        assert os.path.isdir(os.path.join(envdir, "conda-meta"))
        assert os.path.exists(os.path.join(envdir, IPYTHON_BINARY))

        # test that we can remove a package
        manager.remove_packages(prefix=envdir, packages=['ipython'])
        assert not os.path.exists(os.path.join(envdir, IPYTHON_BINARY))

        # test for error removing
        with pytest.raises(CondaManagerError) as excinfo:
            manager.remove_packages(prefix=envdir, packages=['ipython'])
        assert 'no packages found to remove' in str(excinfo.value)

    with_directory_contents(dict(), do_test)
