from __future__ import absolute_import, print_function

import os
import pytest

import project.internal.conda_api as conda_api

from project.internal.test.tmpfile_utils import with_directory_contents


def test_conda_info():
    json = conda_api.info()

    print(repr(json))  # pytest shows this on failure
    assert isinstance(json, dict)

    # check that some stuff is in here.
    # conda apparently doesn't guarantee that any of this is here,
    # but if it changes I guess we'd like to know via test failure.
    assert 'channels' in json
    assert 'root_prefix' in json
    assert 'platform' in json
    assert 'envs' in json


def test_conda_create_and_install():
    def do_test(dirname):
        envdir = os.path.join(dirname, "myenv")
        # don't specify a python version so we use the one we already have
        # in the root env, otherwise this might take forever.
        conda_api.create(prefix=envdir, pkgs=['python'])

        assert os.path.isdir(envdir)
        assert os.path.isdir(os.path.join(envdir, "conda-meta"))
        assert os.path.exists(os.path.join(envdir, "bin/python"))

        # test that if it exists we can't create it again
        with pytest.raises(conda_api.CondaEnvExistsError) as excinfo:
            conda_api.create(prefix=envdir, pkgs=['python'])
        assert 'already exists' in repr(excinfo.value)

        # test that we can install a package
        assert not os.path.exists(os.path.join(envdir, "bin/ipython"))
        conda_api.install(prefix=envdir, pkgs=['ipython'])
        assert os.path.exists(os.path.join(envdir, "bin/ipython"))

    with_directory_contents(dict(), do_test)


def test_conda_create_no_packages():
    def do_test(dirname):
        envdir = os.path.join(dirname, "myenv")

        with pytest.raises(TypeError) as excinfo:
            conda_api.create(prefix=envdir, pkgs=[])
        assert 'must specify a list' in repr(excinfo.value)

    with_directory_contents(dict(), do_test)


def test_conda_create_bad_package():
    def do_test(dirname):
        envdir = os.path.join(dirname, "myenv")

        with pytest.raises(conda_api.CondaError) as excinfo:
            conda_api.create(prefix=envdir, pkgs=['this_is_not_a_real_package'])
        assert 'No packages found' in repr(excinfo.value)
        assert 'this_is_not_a_real_package' in repr(excinfo.value)

    with_directory_contents(dict(), do_test)


def test_conda_install_no_packages():
    def do_test(dirname):
        envdir = os.path.join(dirname, "myenv")

        conda_api.create(prefix=envdir, pkgs=['python'])

        with pytest.raises(TypeError) as excinfo:
            conda_api.install(prefix=envdir, pkgs=[])
        assert 'must specify a list' in repr(excinfo.value)

    with_directory_contents(dict(), do_test)
