# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import json
import os
import platform
import pytest
import random
import stat

from pprint import pprint

import anaconda_project.internal.conda_api as conda_api
import anaconda_project.internal.pip_api as pip_api

from anaconda_project.internal.test.tmpfile_utils import (with_directory_contents, tmp_script_commandline)

if platform.system() == 'Windows':
    PYTHON_BINARY = "python.exe"
    IPYTHON_BINARY = "Scripts\\ipython.exe"
else:
    PYTHON_BINARY = "bin/python"
    IPYTHON_BINARY = "bin/ipython"


def monkeypatch_conda_not_to_use_links(monkeypatch):
    # on Windows, if you hardlink a file that's in use you can't then
    # remove the file. So we need to pass --copy to conda to avoid errors
    # in the tests when we try to clean up.
    if platform.system() != 'Windows':
        return

    def mock_get_conda_command(extra_args):
        cmd_list = [conda_api.CONDA_EXE]
        cmd_list.extend(extra_args)
        if 'create' in cmd_list:
            i = cmd_list.index('create')
            cmd_list[i:i + 1] = ['create', '--copy']
        elif 'install' in cmd_list:
            i = cmd_list.index('install')
            cmd_list[i:i + 1] = ['install', '--copy']
        return cmd_list

    monkeypatch.setattr('anaconda_project.internal.conda_api._get_conda_command', mock_get_conda_command)


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


@pytest.mark.slow
def test_conda_create_and_install_and_remove(monkeypatch):
    monkeypatch_conda_not_to_use_links(monkeypatch)

    def do_test(dirname):
        envdir = os.path.join(dirname, "myenv")
        print('CONDA_EXE: {}'.format(os.environ.get('CONDA_EXE')))
        # originally we did not specify a python version here, but we
        # needed to add it with python 3.9 was released because a compatible
        # version of ipython had not been created yet.
        conda_api.create(prefix=envdir, pkgs=['python<3.9'])

        assert os.path.isdir(envdir)
        assert os.path.isdir(os.path.join(envdir, "conda-meta"))
        assert os.path.exists(os.path.join(envdir, PYTHON_BINARY))

        # test that if it exists we can't create it again
        with pytest.raises(conda_api.CondaEnvExistsError) as excinfo:
            conda_api.create(prefix=envdir, pkgs=['python'])
        assert 'already exists' in repr(excinfo.value)

        # test that we can install a package
        assert not os.path.exists(os.path.join(envdir, IPYTHON_BINARY))
        conda_api.install(prefix=envdir, pkgs=['ipython'])
        assert os.path.exists(os.path.join(envdir, IPYTHON_BINARY))

        # test that we can remove it again
        conda_api.remove(prefix=envdir, pkgs=['ipython'])
        assert not os.path.exists(os.path.join(envdir, IPYTHON_BINARY))

    with_directory_contents(dict(), do_test)


def test_conda_create_no_packages():
    def do_test(dirname):
        envdir = os.path.join(dirname, "myenv")

        conda_api.create(prefix=envdir, pkgs=[])

    with_directory_contents(dict(), do_test)


def _assert_packages_not_found(e):
    # conda has changed this message several times
    ok = False
    valid_strings = ('No packages found', 'Package missing in current', 'Package missing in current',
                     'PackageNotFoundError:', 'PackagesNotFoundError:', 'Package not found')

    ok = any(s in str(e) for s in valid_strings)
    if not ok:
        # pytest truncates the exception message sometimes?
        print("Not the exception we wanted: %r" % e)
        raise AssertionError("Expecting package not found error, got: %s" % repr(e))


@pytest.mark.slow
def test_conda_create_bad_package():
    def do_test(dirname):
        envdir = os.path.join(dirname, "myenv")

        with pytest.raises(conda_api.CondaError) as excinfo:
            conda_api.create(prefix=envdir, pkgs=['this_is_not_a_real_package'])

        _assert_packages_not_found(excinfo.value)
        assert 'this_is_not_a_real_package' in repr(excinfo.value)

    with_directory_contents(dict(), do_test)


@pytest.mark.slow
def test_conda_install_no_packages(monkeypatch):
    monkeypatch_conda_not_to_use_links(monkeypatch)

    def do_test(dirname):
        envdir = os.path.join(dirname, "myenv")

        conda_api.create(prefix=envdir, pkgs=['python'])

        with pytest.raises(TypeError) as excinfo:
            conda_api.install(prefix=envdir, pkgs=[])
        assert 'must specify a list' in repr(excinfo.value)

    with_directory_contents(dict(), do_test)


@pytest.mark.slow
def test_pip_installed():
    def do_test(dirname):
        envdir = os.path.join(dirname, 'myenv')

        conda_api.create(prefix=envdir, pkgs=['python=3.8'])
        pip_api.install(prefix=envdir, pkgs=['chardet==3'])

        pip_packages = conda_api.installed_pip(envdir)
        assert pip_packages == ['chardet==3.0.0']

    with_directory_contents(dict(), do_test)


@pytest.mark.slow
def test_conda_remove_no_packages(monkeypatch):
    monkeypatch_conda_not_to_use_links(monkeypatch)

    def do_test(dirname):
        envdir = os.path.join(dirname, "myenv")

        conda_api.create(prefix=envdir, pkgs=['python'])

        with pytest.raises(TypeError) as excinfo:
            conda_api.remove(prefix=envdir, pkgs=[])
        assert 'must specify a list' in repr(excinfo.value)

    with_directory_contents(dict(), do_test)


def test_conda_invoke_fails(monkeypatch):
    def mock_popen(args, stdout=None, stderr=None, env=None):
        raise OSError("failed to exec")

    def do_test(dirname):
        monkeypatch.setattr('subprocess.Popen', mock_popen)
        with pytest.raises(conda_api.CondaError) as excinfo:
            conda_api.info()
        assert 'failed to exec' in repr(excinfo.value)
        conda_cmd = os.path.basename(conda_api.CONDA_EXE)
        assert conda_cmd + ' info' in repr(excinfo.value)

    with_directory_contents(dict(), do_test)


def test_conda_invoke_nonzero_returncode(monkeypatch):
    def get_failed_command(extra_args):
        return tmp_script_commandline("""from __future__ import print_function
import sys
print("TEST_ERROR", file=sys.stderr)
sys.exit(1)
""")

    def do_test(dirname):
        monkeypatch.setattr('anaconda_project.internal.conda_api._get_conda_command', get_failed_command)
        with pytest.raises(conda_api.CondaError) as excinfo:
            conda_api.info()
        assert 'TEST_ERROR' in repr(excinfo.value)

    with_directory_contents(dict(), do_test)


def test_conda_invoke_zero_returncode_with_stuff_on_stderr(monkeypatch, capsys):
    def get_command(extra_args):
        return tmp_script_commandline("""from __future__ import print_function
import sys
print("TEST_ERROR", file=sys.stderr)
print("{}")
sys.exit(0)
""")

    def do_test(dirname):
        monkeypatch.setattr('anaconda_project.internal.conda_api._get_conda_command', get_command)
        conda_api.info()
        (out, err) = capsys.readouterr()
        assert 'TEST_ERROR' in err

    with_directory_contents(dict(), do_test)


def test_conda_invoke_zero_returncode_with_invalid_json(monkeypatch, capsys):
    def get_command(extra_args):
        return tmp_script_commandline("""from __future__ import print_function
import sys
print("NOT_JSON")
sys.exit(0)
""")

    def do_test(dirname):
        monkeypatch.setattr('anaconda_project.internal.conda_api._get_conda_command', get_command)
        with pytest.raises(conda_api.CondaError) as excinfo:
            conda_api.info()
        assert 'Invalid JSON from conda' in repr(excinfo.value)

    with_directory_contents(dict(), do_test)


def test_conda_create_disable_override_channels(monkeypatch):
    monkeypatch.setenv('ANACONDA_PROJECT_DISABLE_OVERRIDE_CHANNELS', True)

    def mock_call_conda(extra_args, json_mode=False, platform=None, stdout_callback=None, stderr_callback=None):
        assert ['create', '--yes', '--prefix', '/prefix', '--channel', 'foo', '--channel', 'defaults',
                'python'] == extra_args

    monkeypatch.setattr('anaconda_project.internal.conda_api._call_conda', mock_call_conda)
    conda_api.create(prefix='/prefix', pkgs=['python'], channels=['foo'])


def test_conda_create_nodefaults(monkeypatch):
    def mock_call_conda(extra_args, json_mode=False, platform=None, stdout_callback=None, stderr_callback=None):
        assert ['create', '--override-channels', '--yes', '--prefix', '/prefix', '--channel', 'foo',
                'python'] == extra_args

    monkeypatch.setattr('anaconda_project.internal.conda_api._call_conda', mock_call_conda)
    conda_api.create(prefix='/prefix', pkgs=['python'], channels=['foo', 'nodefaults'])


def test_conda_create_gets_channels(monkeypatch):
    def mock_call_conda(extra_args, json_mode=False, platform=None, stdout_callback=None, stderr_callback=None):
        assert [
            'create', '--override-channels', '--yes', '--prefix', '/prefix', '--channel', 'foo', '--channel',
            'defaults', 'python'
        ] == extra_args

    monkeypatch.setattr('anaconda_project.internal.conda_api._call_conda', mock_call_conda)
    conda_api.create(prefix='/prefix', pkgs=['python'], channels=['foo'])


def test_conda_create_with_defaults(monkeypatch):
    def mock_call_conda(extra_args, json_mode=False, platform=None, stdout_callback=None, stderr_callback=None):
        assert [
            'create', '--override-channels', '--yes', '--prefix', '/prefix', '--channel', 'defaults', '--channel',
            'foo', 'python'
        ] == extra_args

    monkeypatch.setattr('anaconda_project.internal.conda_api._call_conda', mock_call_conda)
    conda_api.create(prefix='/prefix', pkgs=['python'], channels=['defaults', 'foo'])


def test_conda_install_gets_channels(monkeypatch):
    def mock_call_conda(extra_args, json_mode=False, platform=None, stdout_callback=None, stderr_callback=None):
        assert [
            'install', '--override-channels', '--yes', '--prefix', '/prefix', '--channel', 'foo', '--channel',
            'defaults', 'python'
        ] == extra_args

    monkeypatch.setattr('anaconda_project.internal.conda_api._call_conda', mock_call_conda)
    conda_api.install(prefix='/prefix', pkgs=['python'], channels=['foo'])


def test_conda_install_with_defaults(monkeypatch):
    def mock_call_conda(extra_args, json_mode=False, platform=None, stdout_callback=None, stderr_callback=None):
        assert [
            'install', '--override-channels', '--yes', '--prefix', '/prefix', '--channel', 'defaults', '--channel',
            'foo', 'python'
        ] == extra_args

    monkeypatch.setattr('anaconda_project.internal.conda_api._call_conda', mock_call_conda)
    conda_api.install(prefix='/prefix', pkgs=['python'], channels=['defaults', 'foo'])


def test_resolve_root_prefix():
    prefix = conda_api.resolve_env_to_prefix('root')
    assert prefix is not None
    assert os.path.isdir(prefix)


def test_resolve_named_env(monkeypatch):
    def mock_info():
        return {'root_prefix': '/foo', 'envs': ['/foo/envs/bar']}

    monkeypatch.setattr('anaconda_project.internal.conda_api.info', mock_info)
    prefix = conda_api.resolve_env_to_prefix('bar')
    assert "/foo/envs/bar" == prefix


def test_resolve_bogus_env(monkeypatch):
    def mock_info():
        return {'root_prefix': '/foo', 'envs': ['/foo/envs/bar']}

    monkeypatch.setattr('anaconda_project.internal.conda_api.info', mock_info)
    prefix = conda_api.resolve_env_to_prefix('nope')
    assert prefix is None


def test_resolve_env_prefix_from_dirname():
    prefix = conda_api.resolve_env_to_prefix('/foo/bar')
    assert "/foo/bar" == prefix


def test_installed():
    def check_installed(dirname):
        expected = {
            'numexpr': ('numexpr', '2.4.4', 'np110py27_0'),
            'portaudio': ('portaudio', '19', '0'),
            'unittest2': ('unittest2', '0.5.1', 'py27_1'),
            'websocket': ('websocket', '0.2.1', 'py27_0'),
            'ipython-notebook': ('ipython-notebook', '4.0.4', 'py27_0')
        }

        installed = conda_api.installed(dirname)
        assert expected == installed

    files = {
        'conda-meta/websocket-0.2.1-py27_0.json': "",
        'conda-meta/unittest2-0.5.1-py27_1.json': "",
        'conda-meta/portaudio-19-0.json': "",
        'conda-meta/numexpr-2.4.4-np110py27_0.json': "",
        # note that this has a hyphen in package name
        'conda-meta/ipython-notebook-4.0.4-py27_0.json': "",
        'conda-meta/not-a-json-file.txt': "",
        'conda-meta/json_file_without_proper_name_structure.json': ""
    }

    with_directory_contents(files, check_installed)


def test_installed_on_nonexistent_prefix():
    installed = conda_api.installed("/this/does/not/exist")
    assert dict() == installed


def test_installed_no_conda_meta():
    def check_installed(dirname):
        installed = conda_api.installed(dirname)
        assert dict() == installed

    with_directory_contents(dict(), check_installed)


def test_installed_cannot_list_dir(monkeypatch):
    def mock_listdir(dirname):
        raise OSError("cannot list this")

    monkeypatch.setattr("os.listdir", mock_listdir)
    with pytest.raises(conda_api.CondaError) as excinfo:
        conda_api.installed("/this/does/not/exist")
    assert 'cannot list this' in repr(excinfo.value)


def test_set_conda_env_in_path_unix(monkeypatch):
    import platform
    if platform.system() == 'Windows':

        def mock_system():
            return 'Linux'

        monkeypatch.setattr('platform.system', mock_system)

        def mock_is_conda_bindir_unix(path):
            if path.endswith("\\"):
                path = path[:-1]
            if not path.endswith("\\bin"):
                return False
            possible_prefix = os.path.dirname(path)
            return os.path.isdir(os.path.join(possible_prefix, "conda-meta"))

        monkeypatch.setattr('anaconda_project.internal.conda_api._is_conda_bindir_unix', mock_is_conda_bindir_unix)

    def check_conda_env_in_path_unix(dirname):
        env1 = os.path.join(dirname, "env1")
        os.makedirs(os.path.join(env1, "conda-meta"))
        env1bin = os.path.join(env1, "bin")
        os.makedirs(env1bin)
        env2 = os.path.join(dirname, "env2")
        os.makedirs(os.path.join(env2, "conda-meta"))
        env2bin = os.path.join(env2, "bin")
        os.makedirs(env2bin)
        notenv = os.path.join(dirname, "notenv")
        notenvbin = os.path.join(notenv, "bin")
        os.makedirs(notenvbin)

        # add env to empty path
        path = conda_api.set_conda_env_in_path("", env1)
        assert env1bin == path
        # add env that's already there
        path = conda_api.set_conda_env_in_path(env1bin, env1)
        assert env1bin == path
        # we can set a non-env because we don't waste time checking it
        path = conda_api.set_conda_env_in_path("", notenv)
        assert notenvbin == path
        # add an env to a non-env
        path = conda_api.set_conda_env_in_path(notenvbin, env1)
        assert (env1bin + os.pathsep + notenvbin) == path
        # add an env to another env
        path = conda_api.set_conda_env_in_path(env1bin, env2)
        assert env2bin == path
        # replace an env that wasn't at the front
        path = conda_api.set_conda_env_in_path(notenvbin + os.pathsep + env2bin, env1)
        assert (env1bin + os.pathsep + notenvbin) == path
        # keep a bunch of random stuff
        random_stuff = "foo:bar/:/baz/boo/"
        path = conda_api.set_conda_env_in_path(random_stuff, env1)
        assert (env1bin + os.pathsep + random_stuff) == path

    with_directory_contents(dict(), check_conda_env_in_path_unix)


def _windows_monkeypatch(monkeypatch):
    import platform
    if platform.system() != 'Windows':

        def mock_system():
            return 'Windows'

        monkeypatch.setattr('platform.system', mock_system)

        monkeypatch.setattr('os.pathsep', ';')

        from os.path import dirname as real_dirname

        def mock_dirname(path):
            replaced = path.replace("\\", "/")
            return real_dirname(replaced)

        monkeypatch.setattr('os.path.dirname', mock_dirname)

        def mock_join(path, *more):
            for m in more:
                if not (path.endswith("\\") or path.endswith("/")):
                    path = path + "\\"
                if m.startswith("\\") or m.startswith("/"):
                    m = m[1:]
                path = path + m
            return path.replace("\\", "/")

        monkeypatch.setattr('os.path.join', mock_join)

        from os import makedirs as real_makedirs

        def mock_makedirs(path, mode=int('0777', 8), exist_ok=True):

            if os.path.exists(path) and exist_ok:
                return None
            else:
                return real_makedirs(path.replace("\\", "/"), mode)

        monkeypatch.setattr('os.makedirs', mock_makedirs)

        from os.path import isdir as real_isdir

        def mock_isdir(path):
            return real_isdir(path.replace("\\", "/"))

        monkeypatch.setattr('os.path.isdir', mock_isdir)


def test_set_conda_env_in_path_windows(monkeypatch):
    def check_conda_env_in_path_windows(dirname):
        _windows_monkeypatch(monkeypatch)

        scripts = "Scripts"
        library = "Library\\bin"

        env1 = os.path.join(dirname, "env1")
        os.makedirs(os.path.join(env1, "conda-meta"))
        env1scripts = os.path.join(env1, scripts)
        os.makedirs(env1scripts)
        env1lib = os.path.join(env1, library)
        os.makedirs(env1lib)

        env1path = "%s;%s;%s" % (env1, env1scripts, env1lib)

        env2 = os.path.join(dirname, "env2")
        os.makedirs(os.path.join(env2, "conda-meta"))
        env2scripts = os.path.join(env2, scripts)
        os.makedirs(env2scripts)
        env2lib = os.path.join(env2, library)
        os.makedirs(env2lib)

        env2path = "%s;%s;%s" % (env2, env2scripts, env2lib)

        notenv = os.path.join(dirname, "notenv")
        notenvscripts = os.path.join(notenv, scripts)
        os.makedirs(notenvscripts)
        notenvlib = os.path.join(notenv, library)
        os.makedirs(notenvlib)

        notenvpath = "%s;%s;%s" % (notenv, notenvscripts, notenvlib)

        # add env to empty path
        path = conda_api.set_conda_env_in_path("", env1)
        assert env1path == path
        # add env that's already there
        path = conda_api.set_conda_env_in_path(env1path, env1)
        assert env1path == path
        # we can set a non-env because we don't waste time checking it
        path = conda_api.set_conda_env_in_path("", notenv)
        assert notenvpath == path
        # add an env to a non-env
        path = conda_api.set_conda_env_in_path(notenvpath, env1)
        assert (env1path + os.pathsep + notenvpath) == path
        # add an env to another env
        path = conda_api.set_conda_env_in_path(env1path, env2)
        assert env2path == path
        # replace an env that wasn't at the front
        path = conda_api.set_conda_env_in_path(notenvpath + os.pathsep + env2path, env1)
        assert (env1path + os.pathsep + notenvpath) == path
        # keep a bunch of random stuff
        random_stuff = "foo;bar;/baz/boo"
        path = conda_api.set_conda_env_in_path(random_stuff, env1)
        assert (env1path + os.pathsep + random_stuff) == path

    with_directory_contents(dict(), check_conda_env_in_path_windows)


def test_set_conda_env_in_path_windows_trailing_slashes(monkeypatch):
    def check_conda_env_in_path_windows_trailing_slashes(dirname):
        _windows_monkeypatch(monkeypatch)

        scripts = "Scripts"
        library = "Library\\bin"

        env1 = os.path.join(dirname, "env1")
        os.makedirs(os.path.join(env1, "conda-meta"))
        env1scripts = os.path.join(env1, scripts)
        os.makedirs(env1scripts)
        env1lib = os.path.join(env1, library)
        os.makedirs(env1lib)

        env1path = "%s\\;%s\\;%s\\" % (env1, env1scripts, env1lib)
        env1path_no_slashes = "%s;%s;%s" % (env1, env1scripts, env1lib)

        env2 = os.path.join(dirname, "env2")
        os.makedirs(os.path.join(env2, "conda-meta"))
        env2scripts = os.path.join(env2, scripts)
        os.makedirs(env2scripts)
        env2lib = os.path.join(env2, library)
        os.makedirs(env2lib)

        env2path = "%s\\;%s\\;%s\\" % (env2, env2scripts, env2lib)
        env2path_no_slashes = "%s;%s;%s" % (env2, env2scripts, env2lib)

        notenv = os.path.join(dirname, "notenv\\")
        notenvscripts = os.path.join(notenv, scripts)
        os.makedirs(notenvscripts)
        notenvlib = os.path.join(notenv, library)
        os.makedirs(notenvlib)

        notenvpath = "%s\\;%s\\;%s\\" % (notenv, notenvscripts, notenvlib)
        notenvpath_no_slashes = "%s;%s;%s" % (notenv, notenvscripts, notenvlib)

        # add env to empty path
        path = conda_api.set_conda_env_in_path("", env1)
        assert env1path_no_slashes == path
        # add env that's already there
        path = conda_api.set_conda_env_in_path(env1path, env1)
        assert env1path_no_slashes == path
        # we can set a non-env because we don't waste time checking it
        path = conda_api.set_conda_env_in_path("", notenv)
        assert notenvpath_no_slashes == path
        # add an env to a non-env
        path = conda_api.set_conda_env_in_path(notenvpath, env1)
        assert (env1path_no_slashes + os.pathsep + notenvpath) == path
        # add an env to another env
        path = conda_api.set_conda_env_in_path(env1path, env2)
        assert env2path_no_slashes == path
        # replace an env that wasn't at the front
        path = conda_api.set_conda_env_in_path(notenvpath + os.pathsep + env2path, env1)
        assert (env1path_no_slashes + os.pathsep + notenvpath) == path
        # keep a bunch of random stuff
        random_stuff = "foo;bar;/baz/boo"
        path = conda_api.set_conda_env_in_path(random_stuff, env1)
        assert (env1path_no_slashes + os.pathsep + random_stuff) == path

    with_directory_contents(dict(), check_conda_env_in_path_windows_trailing_slashes)


def test_invalid_specs():
    invalids = ['=', 'foo 1.0', '>']
    for invalid in invalids:
        assert conda_api.parse_spec(invalid) is None

    with pytest.raises(TypeError) as excinfo:
        conda_api.parse_spec(42)
    assert 'Expected a string' in str(excinfo.value)


def test_conda_style_specs():
    cases = [('foo', ('foo', None, None, None, None)), ('foo=1.0', ('foo', '=1.0', None, '1.0', None)),
             ('foo=1.0*', ('foo', '=1.0*', None, None, None)), ('foo=1.0|1.2', ('foo', '=1.0|1.2', None, None, None)),
             ('foo=1.0=2', ('foo', '=1.0=2', None, '1.0', '2'))]
    for case in cases:
        assert conda_api.parse_spec(case[0]) == case[1]


def test_pip_style_specs():
    cases = [('foo>=1.0', ('foo', None, '>=1.0', None, None)), ('foo >=1.0', ('foo', None, '>=1.0', None, None)),
             ('FOO-Bar >=1.0', ('foo-bar', None, '>=1.0', None, None)),
             ('foo >= 1.0', ('foo', None, '>=1.0', None, None)), ('foo > 1.0', ('foo', None, '>1.0', None, None)),
             ('foo != 1.0', ('foo', None, '!=1.0', None, None)), ('foo <1.0', ('foo', None, '<1.0', None, None)),
             ('foo >=1.0 , < 2.0', ('foo', None, '>=1.0,<2.0', None, None))]
    for case in cases:
        assert conda_api.parse_spec(case[0]) == case[1]


def test_parse_platform():
    for p in conda_api.default_platforms_plus_32_bit:
        (name, bits) = conda_api.parse_platform(p)
        assert bits in ('32', '64')
        assert name in conda_api.known_platform_names

    assert ('linux-cos5', '64') == conda_api.parse_platform('linux-cos5-64')


def test_conda_variable_when_not_in_conda(monkeypatch):
    monkeypatch.setattr('os.environ', dict())
    assert conda_api.conda_prefix_variable() == 'CONDA_PREFIX'


def test_conda_variable_when_have_only_env_path_and_default_env(monkeypatch):
    monkeypatch.setattr('os.environ', dict(CONDA_ENV_PATH='foo', CONDA_DEFAULT_ENV='bar'))
    assert conda_api.conda_prefix_variable() == 'CONDA_ENV_PATH'


def test_conda_variable_when_have_only_default_env(monkeypatch):
    monkeypatch.setattr('os.environ', dict(CONDA_DEFAULT_ENV='foo'))
    assert conda_api.conda_prefix_variable() == 'CONDA_DEFAULT_ENV'


def test_conda_variable_when_have_all_three(monkeypatch):
    monkeypatch.setattr('os.environ', dict(CONDA_ENV_PATH='foo', CONDA_DEFAULT_ENV='bar', CONDA_PREFIX='baz'))
    assert conda_api.conda_prefix_variable() == 'CONDA_PREFIX'


def test_environ_set_prefix_to_root():
    prefix = conda_api.resolve_env_to_prefix('root')
    environ = dict()
    conda_api.environ_set_prefix(environ, prefix, varname='CONDA_PREFIX')
    assert environ['CONDA_PREFIX'] == prefix
    assert environ['CONDA_DEFAULT_ENV'] == 'root'


@pytest.mark.slow
@pytest.mark.parametrize('p', conda_api.default_platforms_plus_32_bit)
def test_resolve_dependencies_with_actual_conda(p):
    try:
        result = conda_api.resolve_dependencies(['requests=2.20.1'], platform=p)
    except conda_api.CondaError as e:
        print("*** Dependency resolution failed on %s" % p)
        pprint(e.json)
        raise e

    names = [pkg[0] for pkg in result]
    assert 'requests' in names
    names_and_versions = [(pkg[0], pkg[1]) for pkg in result]
    assert ('requests', '2.20.1') in names_and_versions
    assert len(result) > 1  # requests has some dependencies so should be >1

    print("Dependency resolution test OK on %s" % p)


@pytest.mark.slow
@pytest.mark.parametrize('p', [p for p in conda_api.default_platforms_plus_32_bit if 'win' in p])
def test_resolve_msys2_dependencies_with_actual_conda(p):
    try:
        result = conda_api.resolve_dependencies(['m2-msys2-runtime=2.5.0.17080.65c939c'], platform=p)
    except conda_api.CondaError as e:
        print("*** Dependency resolution failed on %s" % p)
        pprint(e.json)
        raise e

    names = [pkg[0] for pkg in result]
    assert 'm2-msys2-runtime' in names
    names_and_versions = [(pkg[0], pkg[1]) for pkg in result]
    assert ('m2-msys2-runtime', '2.5.0.17080.65c939c') in names_and_versions
    assert len(result) > 1  # requests has some dependencies so should be >1

    print("Dependency resolution test OK on %s" % p)


@pytest.mark.slow
def test_resolve_dependencies_for_bogus_package_with_actual_conda():
    with pytest.raises(conda_api.CondaError) as excinfo:
        conda_api.resolve_dependencies(['doesnotexistblahblah'])
    if hasattr(excinfo.value, 'json'):
        pprint(excinfo.value.json)
    exc_str = str(excinfo.value)
    valid_strings = ('Package not found', 'Package missing', 'Packages missing', 'packages are not available')
    assert any(s in exc_str for s in valid_strings)


@pytest.mark.slow
def test_resolve_dependencies_with_actual_conda_depending_on_conda():
    try:
        result = conda_api.resolve_dependencies(['conda=4.10.1'], platform=None)
    except conda_api.CondaError as e:
        pprint(e.json)
        raise e

    names = [pkg[0] for pkg in result]
    assert 'conda' in names
    names_and_versions = [(pkg[0], pkg[1]) for pkg in result]
    assert ('conda', '4.10.1') in names_and_versions
    assert len(result) > 1  # conda has some dependencies so should be >1


def test_resolve_dependencies_ignores_rmtree_failure(monkeypatch):
    def mock_call_conda(extra_args, json_mode, platform, stdout_callback=None, stderr_callback=None):
        return json.dumps({
            'actions': [{
                'LINK': [{
                    'base_url': None,
                    'build_number': 0,
                    'build_string': '0',
                    'channel': 'defaults',
                    'dist_name': 'mkl-2017.0.1-0',
                    'name': 'mkl',
                    'platform': None,
                    'version': '2017.0.1',
                    'with_features_depends': None
                }]
            }]
        })

    monkeypatch.setattr('anaconda_project.internal.conda_api._call_conda', mock_call_conda)

    def mock_isdir(*args, **kwargs):
        return True

    monkeypatch.setattr('os.path.isdir', mock_isdir)

    called = dict()

    def mock_rmtree(*args, **kwargs):
        called['yes'] = True
        raise Exception("did not rm the tree")

    monkeypatch.setattr('shutil.rmtree', mock_rmtree)

    result = conda_api.resolve_dependencies(['foo=1.0'])

    assert 'yes' in called
    assert [('mkl', '2017.0.1', '0')] == result


def test_resolve_dependencies_no_actions_field(monkeypatch):
    def mock_call_conda(extra_args, json_mode, platform=None, stdout_callback=None, stderr_callback=None):
        return json.dumps({'foo': 'bar'})

    monkeypatch.setattr('anaconda_project.internal.conda_api._call_conda', mock_call_conda)

    with pytest.raises(conda_api.CondaError) as excinfo:
        conda_api.resolve_dependencies(['foo=1.0'])
    assert 'Could not understand JSON from Conda' in str(excinfo.value)


def test_resolve_dependencies_no_link_op(monkeypatch):
    def mock_call_conda(extra_args, json_mode, platform=None, stdout_callback=None, stderr_callback=None):
        return json.dumps({'actions': [{'SOMETHING': {}}]})

    monkeypatch.setattr('anaconda_project.internal.conda_api._call_conda', mock_call_conda)

    with pytest.raises(conda_api.CondaError) as excinfo:
        conda_api.resolve_dependencies(['foo=1.0'])
    assert 'Could not understand JSON from Conda' in str(excinfo.value)


def test_resolve_dependencies_pass_through_channels(monkeypatch):
    def mock_call_conda(extra_args, json_mode, platform=None, stdout_callback=None, stderr_callback=None):
        assert '--channel' in extra_args
        assert 'abc' in extra_args
        assert 'nbc' in extra_args
        return json.dumps({
            'actions': [{
                'LINK': [{
                    'base_url': None,
                    'build_number': 0,
                    'build_string': '0',
                    'channel': 'defaults',
                    'dist_name': 'mkl-2017.0.1-0',
                    'name': 'mkl',
                    'platform': None,
                    'version': '2017.0.1',
                    'with_features_depends': None
                }]
            }]
        })

    monkeypatch.setattr('anaconda_project.internal.conda_api._call_conda', mock_call_conda)

    result = conda_api.resolve_dependencies(['foo=1.0'], channels=['abc', 'nbc'])

    assert [('mkl', '2017.0.1', '0')] == result


def test_resolve_dependencies_no_packages():
    def do_test(dirname):
        with pytest.raises(TypeError) as excinfo:
            conda_api.resolve_dependencies(pkgs=[])
        assert 'must specify a list' in repr(excinfo.value)

    with_directory_contents(dict(), do_test)


def test_resolve_dependencies_with_conda_43_json(monkeypatch):
    def mock_call_conda(extra_args, json_mode, platform=None, stdout_callback=None, stderr_callback=None):
        old_json = {
            'actions': [{
                'LINK': [{
                    'base_url': None,
                    'build_number': 0,
                    'build_string': '0',
                    'channel': 'defaults',
                    'dist_name': 'mkl-2017.0.1-0',
                    'name': 'mkl',
                    'platform': None,
                    'version': '2017.0.1',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 1,
                    'build_string': '1',
                    'channel': 'defaults',
                    'dist_name': 'openssl-1.0.2k-1',
                    'name': 'openssl',
                    'platform': None,
                    'version': '1.0.2k',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 2,
                    'build_string': '2',
                    'channel': 'defaults',
                    'dist_name': 'readline-6.2-2',
                    'name': 'readline',
                    'platform': None,
                    'version': '6.2',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 0,
                    'build_string': '0',
                    'channel': 'defaults',
                    'dist_name': 'sqlite-3.13.0-0',
                    'name': 'sqlite',
                    'platform': None,
                    'version': '3.13.0',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 0,
                    'build_string': '0',
                    'channel': 'defaults',
                    'dist_name': 'tk-8.5.18-0',
                    'name': 'tk',
                    'platform': None,
                    'version': '8.5.18',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 0,
                    'build_string': '0',
                    'channel': 'defaults',
                    'dist_name': 'yaml-0.1.6-0',
                    'name': 'yaml',
                    'platform': None,
                    'version': '0.1.6',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 3,
                    'build_string': '3',
                    'channel': 'defaults',
                    'dist_name': 'zlib-1.2.8-3',
                    'name': 'zlib',
                    'platform': None,
                    'version': '1.2.8',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 0,
                    'build_string': '0',
                    'channel': 'defaults',
                    'dist_name': 'python-2.7.13-0',
                    'name': 'python',
                    'platform': None,
                    'version': '2.7.13',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 0,
                    'build_string': 'py27_0',
                    'channel': 'defaults',
                    'dist_name': 'backports-1.0-py27_0',
                    'name': 'backports',
                    'platform': None,
                    'version': '1.0',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 0,
                    'build_string': 'py27_0',
                    'channel': 'defaults',
                    'dist_name': 'backports_abc-0.5-py27_0',
                    'name': 'backports_abc',
                    'platform': None,
                    'version': '0.5',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 0,
                    'build_string': 'py27_0',
                    'channel': 'defaults',
                    'dist_name': 'futures-3.0.5-py27_0',
                    'name': 'futures',
                    'platform': None,
                    'version': '3.0.5',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 2,
                    'build_string': 'py27_2',
                    'channel': 'defaults',
                    'dist_name': 'markupsafe-0.23-py27_2',
                    'name': 'markupsafe',
                    'platform': None,
                    'version': '0.23',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 0,
                    'build_string': 'py27_0',
                    'channel': 'defaults',
                    'dist_name': 'numpy-1.12.0-py27_0',
                    'name': 'numpy',
                    'platform': None,
                    'version': '1.12.0',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 0,
                    'build_string': 'py27_0',
                    'channel': 'defaults',
                    'dist_name': 'pyyaml-3.12-py27_0',
                    'name': 'pyyaml',
                    'platform': None,
                    'version': '3.12',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 0,
                    'build_string': 'py27_0',
                    'channel': 'defaults',
                    'dist_name': 'requests-2.13.0-py27_0',
                    'name': 'requests',
                    'platform': None,
                    'version': '2.13.0',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 0,
                    'build_string': 'py27_0',
                    'channel': 'defaults',
                    'dist_name': 'setuptools-27.2.0-py27_0',
                    'name': 'setuptools',
                    'platform': None,
                    'version': '27.2.0',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 0,
                    'build_string': 'py27_0',
                    'channel': 'defaults',
                    'dist_name': 'six-1.10.0-py27_0',
                    'name': 'six',
                    'platform': None,
                    'version': '1.10.0',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 0,
                    'build_string': 'py27_0',
                    'channel': 'defaults',
                    'dist_name': 'wheel-0.29.0-py27_0',
                    'name': 'wheel',
                    'platform': None,
                    'version': '0.29.0',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 0,
                    'build_string': 'py27_0',
                    'channel': 'defaults',
                    'dist_name': 'jinja2-2.9.5-py27_0',
                    'name': 'jinja2',
                    'platform': None,
                    'version': '2.9.5',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 1,
                    'build_string': 'py27_1',
                    'channel': 'defaults',
                    'dist_name': 'pip-9.0.1-py27_1',
                    'name': 'pip',
                    'platform': None,
                    'version': '9.0.1',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 0,
                    'build_string': 'py27_0',
                    'channel': 'defaults',
                    'dist_name': 'python-dateutil-2.6.0-py27_0',
                    'name': 'python-dateutil',
                    'platform': None,
                    'version': '2.6.0',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 0,
                    'build_string': 'py27_0',
                    'channel': 'defaults',
                    'dist_name': 'singledispatch-3.4.0.3-py27_0',
                    'name': 'singledispatch',
                    'platform': None,
                    'version': '3.4.0.3',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 1,
                    'build_string': 'py27_1',
                    'channel': 'defaults',
                    'dist_name': 'ssl_match_hostname-3.4.0.2-py27_1',
                    'name': 'ssl_match_hostname',
                    'platform': None,
                    'version': '3.4.0.2',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 0,
                    'build_string': 'py27_0',
                    'channel': 'defaults',
                    'dist_name': 'tornado-4.4.2-py27_0',
                    'name': 'tornado',
                    'platform': None,
                    'version': '4.4.2',
                    'with_features_depends': None
                }, {
                    'base_url': None,
                    'build_number': 0,
                    'build_string': 'py27_0',
                    'channel': 'defaults',
                    'dist_name': 'bokeh-0.12.4-py27_0',
                    'name': 'bokeh',
                    'platform': None,
                    'version': '0.12.4',
                    'with_features_depends': None
                }],
                'PREFIX':
                '/tmp/kapsel_resolve__7_udcjm',
                'SYMLINK_CONDA': ['/home/hp/bin/anaconda2'],
                'op_order': [
                    'CHECK_FETCH', 'RM_FETCHED', 'FETCH', 'CHECK_EXTRACT', 'RM_EXTRACTED', 'EXTRACT', 'UNLINK', 'LINK',
                    'SYMLINK_CONDA'
                ]
            }],
            'dry_run':
            True,
            'success':
            True
        }
        return json.dumps(old_json)

    monkeypatch.setattr('anaconda_project.internal.conda_api._call_conda', mock_call_conda)

    try:
        result = conda_api.resolve_dependencies(['bokeh=0.12.4'])
    except conda_api.CondaError as e:
        pprint(e.json)
        raise e

    names = [pkg[0] for pkg in result]
    assert 'bokeh' in names
    names_and_versions = [(pkg[0], pkg[1]) for pkg in result]
    assert ('bokeh', '0.12.4') in names_and_versions
    assert len(result) > 1  # bokeh has some dependencies so should be >1


def test_resolve_dependencies_with_conda_41_json(monkeypatch):
    def mock_call_conda(extra_args, json_mode, platform=None, stdout_callback=None, stderr_callback=None):
        old_json = {
            'actions': {
                'EXTRACT': [
                    'mkl-2017.0.1-0', 'openssl-1.0.2k-1', 'xz-5.2.2-1', 'python-3.6.0-0', 'markupsafe-0.23-py36_2',
                    'numpy-1.12.0-py36_0', 'pyyaml-3.12-py36_0', 'requests-2.13.0-py36_0', 'setuptools-27.2.0-py36_0',
                    'six-1.10.0-py36_0', 'tornado-4.4.2-py36_0', 'wheel-0.29.0-py36_0', 'jinja2-2.9.5-py36_0',
                    'pip-9.0.1-py36_1', 'python-dateutil-2.6.0-py36_0', 'bokeh-0.12.4-py36_0'
                ],
                'FETCH': [
                    'mkl-2017.0.1-0', 'openssl-1.0.2k-1', 'xz-5.2.2-1', 'python-3.6.0-0', 'markupsafe-0.23-py36_2',
                    'numpy-1.12.0-py36_0', 'pyyaml-3.12-py36_0', 'requests-2.13.0-py36_0', 'setuptools-27.2.0-py36_0',
                    'six-1.10.0-py36_0', 'tornado-4.4.2-py36_0', 'wheel-0.29.0-py36_0', 'jinja2-2.9.5-py36_0',
                    'pip-9.0.1-py36_1', 'python-dateutil-2.6.0-py36_0', 'bokeh-0.12.4-py36_0'
                ],
                'LINK': [
                    'mkl-2017.0.1-0 2', 'openssl-1.0.2k-1 2', 'readline-6.2-2 2', 'sqlite-3.13.0-0 2', 'tk-8.5.18-0 2',
                    'xz-5.2.2-1 2', 'yaml-0.1.6-0 2', 'zlib-1.2.8-3 2', 'python-3.6.0-0 2', 'markupsafe-0.23-py36_2 2',
                    'numpy-1.12.0-py36_0 2', 'pyyaml-3.12-py36_0 2', 'requests-2.13.0-py36_0 2',
                    'setuptools-27.2.0-py36_0 2', 'six-1.10.0-py36_0 2', 'tornado-4.4.2-py36_0 2',
                    'wheel-0.29.0-py36_0 2', 'jinja2-2.9.5-py36_0 2', 'pip-9.0.1-py36_1 2',
                    'python-dateutil-2.6.0-py36_0 2', 'bokeh-0.12.4-py36_0 2'
                ],
                'PREFIX':
                '/tmp/kapsel_resolve_luiqsjla',
                'SYMLINK_CONDA': ['/home/hp/bin/anaconda3_4.1.11'],
                'op_order': ['RM_FETCHED', 'FETCH', 'RM_EXTRACTED', 'EXTRACT', 'UNLINK', 'LINK', 'SYMLINK_CONDA']
            },
            'dry_run': True,
            'success': True
        }
        return json.dumps(old_json)

    monkeypatch.setattr('anaconda_project.internal.conda_api._call_conda', mock_call_conda)

    try:
        result = conda_api.resolve_dependencies(['bokeh=0.12.4'])
    except conda_api.CondaError as e:
        pprint(e.json)
        raise e

    names = [pkg[0] for pkg in result]
    assert 'bokeh' in names
    names_and_versions = [(pkg[0], pkg[1]) for pkg in result]
    assert ('bokeh', '0.12.4') in names_and_versions
    assert len(result) > 1  # bokeh has some dependencies so should be >1


def test_current_platform_non_x86_linux(monkeypatch):
    monkeypatch.setenv('CONDA_SUBDIR', 'linux-armv7l')
    assert conda_api.current_platform() == 'linux-armv7l'


def test_current_platform_non_x86_mac(monkeypatch):
    monkeypatch.setenv('CONDA_SUBDIR', 'osx-arm64')
    assert conda_api.current_platform() == 'osx-arm64'


# this test assumes all dev and CI happens on popular platforms.
@pytest.mark.skip(reason="This test is no longer a good idea")
def test_current_platform_is_in_default():
    assert conda_api.current_platform() in conda_api.default_platforms


def test_sort_platform_list():
    everything_sorted = ('all', 'linux', 'osx', 'win') + conda_api.default_platforms_plus_32_bit
    backward = list(reversed(everything_sorted))
    shuffled = list(everything_sorted)
    random.shuffle(shuffled)

    assert everything_sorted == tuple(conda_api.sort_platform_list(backward))
    assert everything_sorted == tuple(conda_api.sort_platform_list(shuffled))
    assert everything_sorted == tuple(conda_api.sort_platform_list(tuple(backward)))
    assert everything_sorted == tuple(conda_api.sort_platform_list(tuple(shuffled)))
    assert [] == conda_api.sort_platform_list([])
    assert [] == conda_api.sort_platform_list(())
    assert ['linux-64', 'osx-64', 'win-64'] == conda_api.sort_platform_list(['win-64', 'osx-64', 'linux-64'])


def test_validate_platform_list():
    (platforms, unknown, invalid) = conda_api.validate_platform_list(['linux-64', 'wtf', 'something', 'foo-64'])
    assert ['linux-64', 'foo-64'] == platforms
    assert ['foo-64'] == unknown
    assert ['something', 'wtf'] == invalid


@pytest.mark.slow
def test_conda_clone_readonly():
    def do_test(dirname):
        readonly = os.path.join(dirname, "readonly")
        print('CONDA_EXE: {}'.format(os.environ.get('CONDA_EXE')))
        # originally we did not specify a python version here, but we
        # needed to add it with python 3.8 was released because a compatible
        # version of ipython had not been created yet.
        conda_api.create(prefix=readonly, pkgs=['python<3.9'])

        assert os.path.isdir(readonly)
        assert os.path.isdir(os.path.join(readonly, "conda-meta"))
        assert os.path.exists(os.path.join(readonly, PYTHON_BINARY))

        readonly_mode = stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
        os.chmod(readonly, readonly_mode)
        os.chmod(os.path.join(readonly, 'conda-meta'), readonly_mode)

        cloned = os.path.join(dirname, 'cloned')
        conda_api.clone(cloned, readonly)

        assert os.path.isdir(cloned)
        assert os.path.isdir(os.path.join(cloned, "conda-meta"))
        assert os.path.exists(os.path.join(cloned, PYTHON_BINARY))

        write_mode = (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH) ^ readonly_mode
        os.chmod(readonly, write_mode)
        os.chmod(os.path.join(readonly, 'conda-meta'), write_mode)

    with_directory_contents(dict(), do_test)


def test_conda_clone_missing_source():
    def do_test(dirname):
        missing = os.path.join(dirname, "missing")
        print('CONDA_EXE: {}'.format(os.environ.get('CONDA_EXE')))

        with pytest.raises(conda_api.CondaEnvMissingError) as excinfo:
            cloned = os.path.join(dirname, 'cloned')
            conda_api.clone(cloned, missing)
        assert 'missing' in repr(excinfo.value)

    with_directory_contents(dict(), do_test)
