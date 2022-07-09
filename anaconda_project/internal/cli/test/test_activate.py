# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

try:
    from shlex import quote
except ImportError:
    from pipes import quote

import platform
import re

from anaconda_project.internal.cli.main import _parse_args_and_run_subcommand
from anaconda_project.internal.cli.activate import activate, main
from anaconda_project.internal.cli.prepare_with_mode import UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents_completing_project_file
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME
from anaconda_project.local_state_file import DEFAULT_LOCAL_STATE_FILENAME
from anaconda_project.test.project_utils import project_dir_disable_dedicated_env


class Args(object):
    def __init__(self, **kwargs):
        self.directory = "."
        self.env_spec = None
        self.mode = UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT
        self.command = None
        for key in kwargs:
            setattr(self, key, kwargs[key])


def _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch):
    can_connect_args = dict()

    def mock_can_connect_to_socket(host, port, timeout_seconds=0.5):
        can_connect_args['host'] = host
        can_connect_args['port'] = port
        can_connect_args['timeout_seconds'] = timeout_seconds
        return True

    monkeypatch.setattr("anaconda_project.requirements_registry.network_util.can_connect_to_socket",
                        mock_can_connect_to_socket)

    return can_connect_args


def _filter_activate_result(result, vars):
    additional_output = False
    outputs = {}
    for line in (result or ()):
        match = re.match(r'^export ([^=]*)=(.*)$', line)
        if match:
            var, value = match.groups()
            if var == 'PATH' and platform.system() == 'Windows':
                print("activate changed PATH on Windows and ideally it would not.")
            outputs[var] = value
        else:
            additional_output = True
    if set(outputs) != set(vars) or additional_output:
        import os
        print("os.environ=" + repr(os.environ))
        print("result=" + repr(result))
    return tuple(outputs.get(v) for v in vars)


def test_activate(monkeypatch):
    can_connect_args = _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch)

    def activate_redis_url(dirname):
        project_dir_disable_dedicated_env(dirname)
        result = activate(dirname, UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT, conda_environment=None, command_name=None)
        assert can_connect_args['port'] == 6379
        result = _filter_activate_result(result, ('PROJECT_DIR', 'REDIS_URL'))
        assert result == (quote(dirname), 'redis://localhost:6379')

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
    """}, activate_redis_url)


def test_activate_quoting(monkeypatch):
    def activate_foo(dirname):
        project_dir_disable_dedicated_env(dirname)
        result = activate(dirname, UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT, conda_environment=None, command_name=None)
        result = _filter_activate_result(result, ('FOO', 'PROJECT_DIR'))
        assert result == ("'$! boo'", quote(dirname))

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: {}
    """,
            DEFAULT_LOCAL_STATE_FILENAME: """
variables:
  FOO: $! boo
"""
        }, activate_foo)


def test_main(monkeypatch, capsys):
    def mock_conda_create(prefix, pkgs, channels):
        raise RuntimeError("this test should not create an environment in %s with pkgs %r" % (prefix, pkgs))

    monkeypatch.setattr('anaconda_project.internal.conda_api.create', mock_conda_create)

    can_connect_args = _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch)

    def main_redis_url(dirname):
        project_dir_disable_dedicated_env(dirname)
        main(Args(directory=dirname))

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, main_redis_url)

    assert can_connect_args['port'] == 6379

    out, err = capsys.readouterr()

    assert "export REDIS_URL=redis://localhost:6379\n" in out
    assert "" == err


def test_main_dirname_not_provided_use_pwd(monkeypatch, capsys):
    can_connect_args = _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch)

    def main_redis_url(dirname):
        monkeypatch.chdir(dirname)
        project_dir_disable_dedicated_env(dirname)
        code = _parse_args_and_run_subcommand(['anaconda-project', 'activate'])
        assert code == 0

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, main_redis_url)

    assert can_connect_args['port'] == 6379

    out, err = capsys.readouterr()
    assert "export PROJECT_DIR" in out
    assert "export REDIS_URL=redis://localhost:6379\n" in out
    assert "" == err


def test_main_dirname_provided_use_it(monkeypatch, capsys):
    can_connect_args = _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch)

    def main_redis_url(dirname):
        project_dir_disable_dedicated_env(dirname)
        code = _parse_args_and_run_subcommand(['anaconda-project', 'activate', '--directory', dirname])
        assert code == 0

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, main_redis_url)

    assert can_connect_args['port'] == 6379

    out, err = capsys.readouterr()
    assert "export PROJECT_DIR" in out
    assert "export REDIS_URL=redis://localhost:6379\n" in out
    assert "" == err


def test_main_bad_command_provided(capsys):
    def check(dirname):
        project_dir_disable_dedicated_env(dirname)
        code = _parse_args_and_run_subcommand(
            ['anaconda-project', 'activate', '--directory', dirname, '--command', 'nope'])
        assert code == 1

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, check)

    out, err = capsys.readouterr()
    assert err.startswith("Command name 'nope' is not in")


def _monkeypatch_can_connect_to_socket_to_fail_to_find_redis(monkeypatch):
    def mock_can_connect_to_socket(host, port, timeout_seconds=0.5):
        if port == 6379:
            return False  # default Redis not there
        else:
            return True  # can't start a custom Redis here

    monkeypatch.setattr("anaconda_project.requirements_registry.network_util.can_connect_to_socket",
                        mock_can_connect_to_socket)


def test_main_fails_to_redis(monkeypatch, capsys):
    _monkeypatch_can_connect_to_socket_to_fail_to_find_redis(monkeypatch)

    def main_redis_url(dirname):
        project_dir_disable_dedicated_env(dirname)
        code = main(Args(directory=dirname))
        assert 1 == code

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, main_redis_url)

    out, err = capsys.readouterr()
    assert "missing requirement" in err
    assert "All ports from 6380 to 6449 were in use" in err
