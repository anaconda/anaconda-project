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

import anaconda_project.internal.conda_api as conda_api
import anaconda_project.internal.pip_api as pip_api

from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.internal.test.test_conda_api import monkeypatch_conda_not_to_use_links

if platform.system() == 'Windows':
    FLAKE8_BINARY = "Scripts\flake8.exe"
else:
    FLAKE8_BINARY = "bin/flake8"


# lots is in this one big test so we don't have to create
# tons of environments
def test_conda_create_and_install_and_remove_pip_stuff(monkeypatch):
    monkeypatch_conda_not_to_use_links(monkeypatch)

    def do_test(dirname):
        envdir = os.path.join(dirname, "myenv")
        # don't specify a python version so we use the one we already have
        # in the root env, otherwise this might take forever.
        conda_api.create(prefix=envdir, pkgs=['python'])

        assert os.path.isdir(envdir)
        assert os.path.isdir(os.path.join(envdir, "conda-meta"))

        # test that we can install a package via pip
        assert not os.path.exists(os.path.join(envdir, FLAKE8_BINARY))
        pip_api.install(prefix=envdir, pkgs=['flake8'])
        assert os.path.exists(os.path.join(envdir, FLAKE8_BINARY))

        # list what was installed
        installed = pip_api.installed(prefix=envdir)
        assert 'flake8' in installed
        assert installed['flake8'][0] == 'flake8'
        assert installed['flake8'][1] is not None

        # test that we can remove it again
        pip_api.remove(prefix=envdir, pkgs=['flake8'])
        assert not os.path.exists(os.path.join(envdir, FLAKE8_BINARY))

        # no longer in the installed list
        installed = pip_api.installed(prefix=envdir)
        assert 'flake8' not in installed

    with_directory_contents(dict(), do_test)


# lots is in this one big test so we don't have to create
# tons of environments
def test_pip_errors(monkeypatch):
    monkeypatch_conda_not_to_use_links(monkeypatch)

    def do_test(dirname):
        envdir = os.path.join(dirname, "myenv")

        conda_api.create(prefix=envdir, pkgs=['python'])

        # no packages to install
        with pytest.raises(TypeError) as excinfo:
            pip_api.install(prefix=envdir, pkgs=[])
        assert 'must specify a list' in repr(excinfo.value)

        # no packages to remove
        with pytest.raises(TypeError) as excinfo:
            pip_api.remove(prefix=envdir, pkgs=[])
        assert 'must specify a list' in repr(excinfo.value)

        # pip command not installed
        from os.path import exists as real_exists

        def mock_exists(path):
            if path.endswith("pip") or path.endswith("pip.exe"):
                return False
            else:
                return real_exists(path)

        monkeypatch.setattr('os.path.exists', mock_exists)
        with pytest.raises(pip_api.PipError) as excinfo:
            pip_api.installed(prefix=envdir)
        assert 'command is not installed in the environment' in repr(excinfo.value)

        # pip command exits nonzero
        def get_failed_command(prefix, extra_args):
            return ["bash", "-c", "echo TEST_ERROR 1>&2 && false"]

        monkeypatch.setattr('anaconda_project.internal.pip_api._get_pip_command', get_failed_command)
        with pytest.raises(pip_api.PipError) as excinfo:
            pip_api.install(prefix=envdir, pkgs=['flake8'])
        assert 'TEST_ERROR' in repr(excinfo.value)

        # pip command exits zero printing stuff on stderr
        def get_failed_command(prefix, extra_args):
            return ["bash", "-c", "echo TEST_ERROR 1>&2 && true"]

        monkeypatch.setattr('anaconda_project.internal.pip_api._get_pip_command', get_failed_command)
        pip_api.install(prefix=envdir, pkgs=['flake8'])

        # cannot exec pip
        def mock_popen(args, stdout=None, stderr=None):
            raise OSError("failed to exec")

        monkeypatch.setattr('subprocess.Popen', mock_popen)
        with pytest.raises(pip_api.PipError) as excinfo:
            pip_api.install(prefix=envdir, pkgs=['flake8'])
        assert 'failed to exec' in repr(excinfo.value)

    with_directory_contents(dict(), do_test)


def test_installed_on_nonexistent_prefix():
    installed = pip_api.installed("/this/does/not/exist")
    assert dict() == installed
