# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import os
import platform
import pytest

import anaconda_project.internal.conda_api as conda_api
import anaconda_project.internal.pip_api as pip_api

from anaconda_project.internal.test.tmpfile_utils import (with_directory_contents, tmp_script_commandline)
from anaconda_project.internal.test.test_conda_api import monkeypatch_conda_not_to_use_links

if platform.system() == 'Windows':
    FLAKE8_BINARY = "Scripts\\flake8.exe"
    # Use a different package from the test env due to weird CI path/env errors
    PYINSTRUMENT_BINARY = "Scripts\\pyinstrument.exe"
else:
    FLAKE8_BINARY = "bin/flake8"
    # Use a different package from the test env due to weird CI path/env errors
    PYINSTRUMENT_BINARY = "bin/pyinstrument"


# lots is in this one big test so we don't have to create
# tons of environments
@pytest.mark.slow
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
        assert not os.path.exists(os.path.join(envdir, PYINSTRUMENT_BINARY))
        pip_api.install(prefix=envdir, pkgs=['pyinstrument'])
        assert os.path.exists(os.path.join(envdir, PYINSTRUMENT_BINARY))

        # list what was installed
        installed = pip_api.installed(prefix=envdir)
        assert 'pyinstrument' in installed
        assert installed['pyinstrument'][0] == 'pyinstrument'
        assert installed['pyinstrument'][1] is not None

        # test that we can remove it again
        pip_api.remove(prefix=envdir, pkgs=['pyinstrument'])
        assert not os.path.exists(os.path.join(envdir, PYINSTRUMENT_BINARY))

        # no longer in the installed list
        installed = pip_api.installed(prefix=envdir)
        assert 'pyinstrument' not in installed

    with_directory_contents(dict(), do_test)


# lots is in this one big test so we don't have to create
# tons of environments
@pytest.mark.slow
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
        with pytest.raises(pip_api.PipNotInstalledError) as excinfo:
            pip_api.install(prefix=envdir, pkgs=['foo'])
        assert 'command is not installed in the environment' in repr(excinfo.value)

        installed = pip_api.installed(prefix=envdir)
        assert dict() == installed  # with pip not installed, no packages are listed.

        # pip command exits nonzero
        error_script = """from __future__ import print_function
import sys
print("TEST_ERROR", file=sys.stderr)
sys.exit(1)
"""

        def get_failed_command(prefix, extra_args):
            return tmp_script_commandline(error_script)

        monkeypatch.setattr('anaconda_project.internal.pip_api._get_pip_command', get_failed_command)
        with pytest.raises(pip_api.PipError) as excinfo:
            pip_api.install(prefix=envdir, pkgs=['flake8'])
        assert 'TEST_ERROR' in repr(excinfo.value)

        # pip command exits zero printing stuff on stderr
        error_message_but_success_script = """from __future__ import print_function
import sys
print("TEST_ERROR", file=sys.stderr)
sys.exit(0)
"""

        def get_failed_command(prefix, extra_args):
            return tmp_script_commandline(error_message_but_success_script)

        monkeypatch.setattr('anaconda_project.internal.pip_api._get_pip_command', get_failed_command)
        pip_api.install(prefix=envdir, pkgs=['flake8'])

        # cannot exec pip
        def mock_popen(args, stdout=None, stderr=None, env=None):
            raise OSError("failed to exec")

        monkeypatch.setattr('subprocess.Popen', mock_popen)
        with pytest.raises(pip_api.PipError) as excinfo:
            pip_api.install(prefix=envdir, pkgs=['flake8'])
        assert 'failed to exec' in repr(excinfo.value)

    with_directory_contents(dict(), do_test)


def test_installed_on_nonexistent_prefix():
    installed = pip_api.installed("/this/does/not/exist")
    assert dict() == installed


def test_parse_spec():
    # just a package name
    assert "foo" == pip_api.parse_spec("foo").name
    # ignore leading whitespace
    assert "foo" == pip_api.parse_spec("  foo").name
    # non-alphanumeric names not ok
    assert pip_api.parse_spec("=") is None
    assert pip_api.parse_spec("%%") is None
    # ignore the version specifier stuff
    assert "foo" == pip_api.parse_spec("foo==1.3").name
    # these three punctuation chars are allowed
    assert "a-_." == pip_api.parse_spec("a-_.").name
    # we use this in some tests
    assert "nope_not_a_thing" == pip_api.parse_spec("nope_not_a_thing").name

    # a bunch of examples from the pip docs
    for spec in [
            'SomeProject', 'SomeProject == 1.3', 'SomeProject >=1.2,<.2.0', 'SomeProject[foo, bar]',
            'SomeProject~=1.4.2', "SomeProject ==5.4 ; python_version < '2.7'", "SomeProject; sys_platform == 'win32'"
    ]:
        assert "SomeProject" == pip_api.parse_spec(spec).name


def test_parse_spec_url():
    assert "bar" == pip_api.parse_spec("http://example.com/foo#egg=bar").name
    assert "bar" == pip_api.parse_spec("https://example.com/foo#egg=bar").name
    # ignore after extra &
    assert "bar" == pip_api.parse_spec("https://example.com/foo#egg=bar&subdirectory=blah").name
    # ignore "-1.3" type of stuff after the package name
    assert "bar" == pip_api.parse_spec("https://example.com/foo#egg=bar-1.3").name
    # ignore if no #egg fragment
    assert pip_api.parse_spec("http://example.com/foo") is None

    # this was a real-world example with an url and [] after package name
    assert 'dask' == pip_api.parse_spec('git+https://github.com/blaze/dask.git#egg=dask[complete]').name
