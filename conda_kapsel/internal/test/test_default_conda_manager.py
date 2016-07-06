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

from conda_kapsel.env_spec import EnvSpec
from conda_kapsel.conda_manager import CondaManagerError

from conda_kapsel.internal.default_conda_manager import DefaultCondaManager
import conda_kapsel.internal.pip_api as pip_api

from conda_kapsel.internal.test.tmpfile_utils import with_directory_contents
from conda_kapsel.internal.test.test_conda_api import monkeypatch_conda_not_to_use_links

if platform.system() == 'Windows':
    PYTHON_BINARY = "python.exe"
    IPYTHON_BINARY = "Scripts\ipython.exe"
    FLAKE8_BINARY = "Scripts\\flake8.exe"
else:
    PYTHON_BINARY = "bin/python"
    IPYTHON_BINARY = "bin/ipython"
    FLAKE8_BINARY = "bin/flake8"


def test_conda_create_and_install_and_remove(monkeypatch):
    monkeypatch_conda_not_to_use_links(monkeypatch)

    spec = EnvSpec(name='myenv', conda_packages=['ipython'], pip_packages=['flake8'], channels=[])
    assert spec.conda_packages == ('ipython', )
    assert spec.pip_packages == ('flake8', )

    spec_with_phony_pip_package = EnvSpec(name='myenv',
                                          conda_packages=['ipython'],
                                          pip_packages=['flake8', 'nope_not_a_thing'],
                                          channels=[])
    assert spec_with_phony_pip_package.conda_packages == ('ipython', )
    assert spec_with_phony_pip_package.pip_packages == ('flake8', 'nope_not_a_thing')

    def do_test(dirname):
        envdir = os.path.join(dirname, spec.name)

        manager = DefaultCondaManager()

        assert not os.path.isdir(envdir)
        assert not os.path.exists(os.path.join(envdir, IPYTHON_BINARY))
        assert not os.path.exists(os.path.join(envdir, FLAKE8_BINARY))

        deviations = manager.find_environment_deviations(envdir, spec)

        assert deviations.missing_packages == ('ipython', )
        assert deviations.missing_pip_packages == ('flake8', )

        manager.fix_environment_deviations(envdir, spec, deviations)

        assert os.path.isdir(envdir)
        assert os.path.isdir(os.path.join(envdir, "conda-meta"))
        assert os.path.exists(os.path.join(envdir, IPYTHON_BINARY))
        assert os.path.exists(os.path.join(envdir, FLAKE8_BINARY))

        # test bad pip package throws error
        deviations = manager.find_environment_deviations(envdir, spec_with_phony_pip_package)

        assert deviations.missing_packages == ()
        assert deviations.missing_pip_packages == ('nope_not_a_thing', )

        with pytest.raises(CondaManagerError) as excinfo:
            manager.fix_environment_deviations(envdir, spec, deviations)
        assert 'Failed to install missing pip packages' in str(excinfo.value)

        # test that we can remove a package
        manager.remove_packages(prefix=envdir, packages=['ipython'])
        assert not os.path.exists(os.path.join(envdir, IPYTHON_BINARY))

        # test for error removing
        with pytest.raises(CondaManagerError) as excinfo:
            manager.remove_packages(prefix=envdir, packages=['ipython'])
        assert 'no packages found to remove' in str(excinfo.value)

        # test failure to exec pip
        def mock_call_pip(*args, **kwargs):
            raise pip_api.PipError("pip fail")

        monkeypatch.setattr('conda_kapsel.internal.pip_api._call_pip', mock_call_pip)

        with pytest.raises(CondaManagerError) as excinfo:
            deviations = manager.find_environment_deviations(envdir, spec)
        assert 'pip failed while listing' in str(excinfo.value)

    with_directory_contents(dict(), do_test)
