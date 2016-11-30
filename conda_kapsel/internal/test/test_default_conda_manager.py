# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import codecs
import json
import os
import platform
import pytest

from conda_kapsel.env_spec import EnvSpec
from conda_kapsel.conda_manager import CondaManagerError
from conda_kapsel.version import version

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

test_spec = EnvSpec(name='myenv', conda_packages=['ipython'], pip_packages=['flake8'], channels=[])


def test_conda_create_and_install_and_remove(monkeypatch):
    monkeypatch_conda_not_to_use_links(monkeypatch)

    spec = test_spec
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
        assert not manager._timestamp_file_up_to_date(envdir, spec)

        deviations = manager.find_environment_deviations(envdir, spec)

        assert deviations.missing_packages == ('ipython', )
        assert deviations.missing_pip_packages == ('flake8', )

        manager.fix_environment_deviations(envdir, spec, deviations)

        assert os.path.isdir(envdir)
        assert os.path.isdir(os.path.join(envdir, "conda-meta"))
        assert os.path.exists(os.path.join(envdir, IPYTHON_BINARY))
        assert os.path.exists(os.path.join(envdir, FLAKE8_BINARY))

        assert manager._timestamp_file_up_to_date(envdir, spec)
        assert not manager._timestamp_file_up_to_date(envdir, spec_with_phony_pip_package)

        # test bad pip package throws error
        deviations = manager.find_environment_deviations(envdir, spec_with_phony_pip_package)

        assert deviations.missing_packages == ()
        assert deviations.missing_pip_packages == ('nope_not_a_thing', )

        with pytest.raises(CondaManagerError) as excinfo:
            manager.fix_environment_deviations(envdir, spec, deviations)
        assert 'Failed to install missing pip packages' in str(excinfo.value)
        assert not manager._timestamp_file_up_to_date(envdir, spec_with_phony_pip_package)

        # test that we can remove a package
        assert manager._timestamp_file_up_to_date(envdir, spec)
        manager.remove_packages(prefix=envdir, packages=['ipython'])
        assert not os.path.exists(os.path.join(envdir, IPYTHON_BINARY))
        assert not manager._timestamp_file_up_to_date(envdir, spec)

        # test for error removing
        with pytest.raises(CondaManagerError) as excinfo:
            manager.remove_packages(prefix=envdir, packages=['ipython'])
        assert 'no packages found to remove' in str(excinfo.value)
        assert not manager._timestamp_file_up_to_date(envdir, spec)

        # test failure to exec pip
        def mock_call_pip(*args, **kwargs):
            raise pip_api.PipError("pip fail")

        monkeypatch.setattr('conda_kapsel.internal.pip_api._call_pip', mock_call_pip)

        with pytest.raises(CondaManagerError) as excinfo:
            deviations = manager.find_environment_deviations(envdir, spec)
        assert 'pip failed while listing' in str(excinfo.value)

    with_directory_contents(dict(), do_test)


def test_timestamp_file_avoids_package_manager_calls(monkeypatch):
    monkeypatch_conda_not_to_use_links(monkeypatch)

    spec = test_spec

    def do_test(dirname):
        envdir = os.path.join(dirname, spec.name)

        manager = DefaultCondaManager()

        assert not os.path.isdir(envdir)
        assert not os.path.exists(os.path.join(envdir, IPYTHON_BINARY))
        assert not os.path.exists(os.path.join(envdir, FLAKE8_BINARY))
        assert not manager._timestamp_file_up_to_date(envdir, spec)

        deviations = manager.find_environment_deviations(envdir, spec)

        assert deviations.missing_packages == ('ipython', )
        assert deviations.missing_pip_packages == ('flake8', )
        assert not deviations.ok

        manager.fix_environment_deviations(envdir, spec, deviations)

        assert os.path.isdir(envdir)
        assert os.path.isdir(os.path.join(envdir, "conda-meta"))
        assert os.path.exists(os.path.join(envdir, IPYTHON_BINARY))
        assert os.path.exists(os.path.join(envdir, FLAKE8_BINARY))

        assert manager._timestamp_file_up_to_date(envdir, spec)

        called = []
        from conda_kapsel.internal.pip_api import _call_pip as real_call_pip
        from conda_kapsel.internal.conda_api import _call_conda as real_call_conda

        def traced_call_pip(*args, **kwargs):
            called.append(("pip", args, kwargs))
            return real_call_pip(*args, **kwargs)

        monkeypatch.setattr('conda_kapsel.internal.pip_api._call_pip', traced_call_pip)

        def traced_call_conda(*args, **kwargs):
            called.append(("conda", args, kwargs))
            return real_call_conda(*args, **kwargs)

        monkeypatch.setattr('conda_kapsel.internal.conda_api._call_conda', traced_call_conda)

        deviations = manager.find_environment_deviations(envdir, spec)

        assert [] == called

        assert deviations.missing_packages == ()
        assert deviations.missing_pip_packages == ()
        assert deviations.ok

        assert manager._timestamp_file_up_to_date(envdir, spec)

        # now modify conda-meta and check that we DO call the package managers
        inside_conda_meta = os.path.join(envdir, "conda-meta", "thing.txt")
        with codecs.open(inside_conda_meta, 'w', encoding='utf-8') as f:
            f.write(u"This file should change the mtime on conda-meta\n")
        os.remove(inside_conda_meta)

        assert not manager._timestamp_file_up_to_date(envdir, spec)

        deviations = manager.find_environment_deviations(envdir, spec)

        assert len(called) == 2

        assert deviations.missing_packages == ()
        assert deviations.missing_pip_packages == ()
        # deviations should not be ok (due to timestamp)
        assert not deviations.ok

        assert not manager._timestamp_file_up_to_date(envdir, spec)

        # we want to be sure we update the timestamp file even though
        # there wasn't any actual work to do
        manager.fix_environment_deviations(envdir, spec, deviations)

        assert manager._timestamp_file_up_to_date(envdir, spec)

    with_directory_contents(dict(), do_test)


def test_timestamp_file_ignores_failed_write(monkeypatch):
    monkeypatch_conda_not_to_use_links(monkeypatch)

    spec = test_spec

    def do_test(dirname):
        from codecs import open as real_open

        envdir = os.path.join(dirname, spec.name)

        manager = DefaultCondaManager()

        counts = dict(calls=0)

        def mock_open(*args, **kwargs):
            counts['calls'] += 1
            if counts['calls'] == 1:
                raise IOError("did not open")
            else:
                return real_open(*args, **kwargs)

        monkeypatch.setattr('codecs.open', mock_open)

        # this should NOT throw but also should not write the
        # timestamp file (we ignore errors)
        filename = manager._timestamp_file(envdir, spec)
        assert filename.startswith(envdir)
        assert not os.path.exists(filename)
        manager._write_timestamp_file(envdir, spec)
        assert not os.path.exists(filename)
        # the second time we really write it (this is to prove we
        # are looking at the right filename)
        manager._write_timestamp_file(envdir, spec)
        assert os.path.exists(filename)

        # check on the file contents
        with real_open(filename, 'r', encoding='utf-8') as f:
            content = json.loads(f.read())
            assert dict(conda_kapsel_version=version) == content

    with_directory_contents(dict(), do_test)
