# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import os
import pytest

from anaconda_project.internal.cli.main import _parse_args_and_run_subcommand
from anaconda_project.internal.cli.prepare import prepare_command, main
from anaconda_project.internal.cli.prepare_with_mode import (UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT,
                                                             UI_MODE_TEXT_ASSUME_YES_PRODUCTION, UI_MODE_TEXT_ASSUME_NO)
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents_completing_project_file
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME
from anaconda_project.local_state_file import LocalStateFile

from anaconda_project.test.project_utils import project_dir_disable_dedicated_env
from anaconda_project.internal.simple_status import SimpleStatus
from anaconda_project.internal import keyring


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


def _test_prepare_command(monkeypatch, ui_mode):
    can_connect_args = _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch)

    def prepare_redis_url(dirname):
        project_dir_disable_dedicated_env(dirname)
        result = prepare_command(dirname, ui_mode, conda_environment=None, command_name=None)
        assert can_connect_args['port'] == 6379
        assert result

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, prepare_redis_url)


def test_prepare_command_development(monkeypatch):
    _test_prepare_command(monkeypatch, UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT)


def test_prepare_command_production(monkeypatch):
    _test_prepare_command(monkeypatch, UI_MODE_TEXT_ASSUME_YES_PRODUCTION)


def test_prepare_command_assume_no(monkeypatch):
    _test_prepare_command(monkeypatch, UI_MODE_TEXT_ASSUME_NO)


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

    from anaconda_project.internal.cli.prepare_with_mode import prepare_with_ui_mode_printing_errors as real_prepare

    def _mock_prepare_do_not_keep_going(project,
                                        environ=None,
                                        ui_mode=UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT,
                                        all=False,
                                        extra_command_args=None):
        return real_prepare(project, environ, ui_mode=ui_mode, extra_command_args=extra_command_args)

    monkeypatch.setattr('anaconda_project.internal.cli.prepare_with_mode.prepare_with_ui_mode_printing_errors',
                        _mock_prepare_do_not_keep_going)

    def main_redis_url(dirname):
        project_dir_disable_dedicated_env(dirname)
        code = main(Args(directory=dirname, all=False, refresh=False))
        assert 1 == code

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, main_redis_url)

    out, err = capsys.readouterr()
    assert "missing requirement" in err
    assert "All ports from 6380 to 6449 were in use" in err


def test_prepare_command_choose_environment(capsys, monkeypatch):
    def mock_conda_create(prefix, pkgs, channels, stdout_callback, stderr_callback):
        from anaconda_project.internal.makedirs import makedirs_ok_if_exists
        metadir = os.path.join(prefix, "conda-meta")
        makedirs_ok_if_exists(metadir)
        for p in pkgs:
            pkgmeta = os.path.join(metadir, "%s-0.1-pyNN.json" % p)
            open(pkgmeta, 'a').close()

    monkeypatch.setattr('anaconda_project.internal.conda_api.create', mock_conda_create)

    def check_prepare_choose_environment(dirname):
        wrong_envdir = os.path.join(dirname, "envs", "foo")
        envdir = os.path.join(dirname, "envs", "bar")
        result = _parse_args_and_run_subcommand(
            ['anaconda-project', 'prepare', '--directory', dirname, '--env-spec=bar'])
        assert result == 0

        assert os.path.isdir(envdir)
        assert not os.path.isdir(wrong_envdir)

        package_json = os.path.join(envdir, "conda-meta", "nonexistent_bar-0.1-pyNN.json")
        assert os.path.isfile(package_json)

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
env_specs:
  foo:
    packages:
        - nonexistent_foo
  bar:
    packages:
        - nonexistent_bar
"""
        }, check_prepare_choose_environment)

    out, err = capsys.readouterr()
    assert out == ("The project is ready to run commands.\n" +
                   "Use `anaconda-project list-commands` to see what's available.\n")
    assert err == ""


def test_prepare_command_all_environments(capsys, monkeypatch):
    def mock_conda_create(prefix, pkgs, channels, stdout_callback, stderr_callback):
        from anaconda_project.internal.makedirs import makedirs_ok_if_exists
        metadir = os.path.join(prefix, "conda-meta")
        makedirs_ok_if_exists(metadir)
        for p in pkgs:
            pkgmeta = os.path.join(metadir, "%s-0.1-pyNN.json" % p)
            open(pkgmeta, 'a').close()

    monkeypatch.setattr('anaconda_project.internal.conda_api.create', mock_conda_create)

    def check_prepare_choose_environment(dirname):
        foo_envdir = os.path.join(dirname, "envs", "foo")
        bar_envdir = os.path.join(dirname, "envs", "bar")
        result = _parse_args_and_run_subcommand(['anaconda-project', 'prepare', '--directory', dirname, '--all'])
        assert result == 0

        assert os.path.isdir(foo_envdir)
        assert os.path.isdir(bar_envdir)

        foo_package_json = os.path.join(foo_envdir, "conda-meta", "nonexistent_foo-0.1-pyNN.json")
        assert os.path.isfile(foo_package_json)

        bar_package_json = os.path.join(bar_envdir, "conda-meta", "nonexistent_bar-0.1-pyNN.json")
        assert os.path.isfile(bar_package_json)

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
env_specs:
  foo:
    packages:
        - nonexistent_foo
  bar:
    packages:
        - nonexistent_bar
"""
        }, check_prepare_choose_environment)

    out, err = capsys.readouterr()
    assert out == ("The project is ready to run commands.\n" +
                   "Use `anaconda-project list-commands` to see what's available.\n")
    assert err == ""


def test_prepare_command_all_environments_refresh(capsys, monkeypatch):
    def mock_conda_create(prefix, pkgs, channels, stdout_callback, stderr_callback):
        from anaconda_project.internal.makedirs import makedirs_ok_if_exists
        metadir = os.path.join(prefix, "conda-meta")
        makedirs_ok_if_exists(metadir)
        for p in pkgs:
            pkgmeta = os.path.join(metadir, "%s-0.1-pyNN.json" % p)
            open(pkgmeta, 'a').close()

    monkeypatch.setattr('anaconda_project.internal.conda_api.create', mock_conda_create)

    def check_prepare_choose_environment(dirname):
        foo_envdir = os.path.join(dirname, "envs", "foo")
        bar_envdir = os.path.join(dirname, "envs", "bar")
        result = _parse_args_and_run_subcommand(['anaconda-project', 'prepare', '--directory', dirname, '--all'])
        assert result == 0

        result = _parse_args_and_run_subcommand(
            ['anaconda-project', 'prepare', '--directory', dirname, '--all', '--refresh'])
        assert result == 0

        assert os.path.isdir(foo_envdir)
        assert os.path.isdir(bar_envdir)

        foo_package_json = os.path.join(foo_envdir, "conda-meta", "nonexistent_foo-0.1-pyNN.json")
        assert os.path.isfile(foo_package_json)

        bar_package_json = os.path.join(bar_envdir, "conda-meta", "nonexistent_bar-0.1-pyNN.json")
        assert os.path.isfile(bar_package_json)

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
env_specs:
  foo:
    packages:
        - nonexistent_foo
  bar:
    packages:
        - nonexistent_bar
"""
        }, check_prepare_choose_environment)

    out, err = capsys.readouterr()
    assert out == ("The project is ready to run commands.\n" +
                   "Use `anaconda-project list-commands` to see what's available.\n" +
                   "The project is ready to run commands.\n" +
                   "Use `anaconda-project list-commands` to see what's available.\n")
    assert err == ""


def test_prepare_command_default_environment_refresh(capsys, monkeypatch):
    def mock_conda_create(prefix, pkgs, channels, stdout_callback, stderr_callback):
        from anaconda_project.internal.makedirs import makedirs_ok_if_exists
        metadir = os.path.join(prefix, "conda-meta")
        makedirs_ok_if_exists(metadir)
        for p in pkgs:
            pkgmeta = os.path.join(metadir, "%s-0.1-pyNN.json" % p)
            open(pkgmeta, 'a').close()

    monkeypatch.setattr('anaconda_project.internal.conda_api.create', mock_conda_create)

    def check_prepare_choose_environment(dirname):
        default_envdir = os.path.join(dirname, "envs", "default")
        result = _parse_args_and_run_subcommand(
            ['anaconda-project', 'prepare', '--directory', dirname, '--env-spec', 'default'])
        assert result == 0

        result = _parse_args_and_run_subcommand(
            ['anaconda-project', 'prepare', '--directory', dirname, '--env-spec', 'default', '--refresh'])
        assert result == 0

        assert os.path.isdir(default_envdir)

        foo_package_json = os.path.join(default_envdir, "conda-meta", "nonexistent_foo-0.1-pyNN.json")
        assert os.path.isfile(foo_package_json)

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
packages:
    - nonexistent_foo
"""}, check_prepare_choose_environment)

    out, err = capsys.readouterr()
    assert out == ("The project is ready to run commands.\n" +
                   "Use `anaconda-project list-commands` to see what's available.\n" +
                   "The project is ready to run commands.\n" +
                   "Use `anaconda-project list-commands` to see what's available.\n")
    assert err == ""


def test_prepare_command_choose_environment_does_not_exist(capsys):
    def check_prepare_choose_environment_does_not_exist(dirname):
        project_dir_disable_dedicated_env(dirname)
        result = _parse_args_and_run_subcommand(
            ['anaconda-project', 'prepare', '--directory', dirname, '--env-spec=nope'])
        assert result == 1

        expected_error = ("Environment name 'nope' is not in %s, these names were found: bar, foo" %
                          os.path.join(dirname, DEFAULT_PROJECT_FILENAME))
        out, err = capsys.readouterr()
        assert out == ""
        assert expected_error in err

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
env_specs:
  foo:
    packages:
        - nonexistent_foo
  bar:
    packages:
        - nonexistent_bar
"""
        }, check_prepare_choose_environment_does_not_exist)


@pytest.mark.slow
def test_prepare_command_choose_command_chooses_env_spec(capsys):
    def check(dirname):
        project_dir_disable_dedicated_env(dirname)
        result = _parse_args_and_run_subcommand(
            ['anaconda-project', 'prepare', '--directory', dirname, '--command=with_bar'])
        assert result == 1

        out, err = capsys.readouterr()
        assert 'nonexistent_bar' in err
        assert 'nonexistent_foo' not in err

        result = _parse_args_and_run_subcommand(
            ['anaconda-project', 'prepare', '--directory', dirname, '--command=with_foo'])
        assert result == 1

        out, err = capsys.readouterr()
        assert 'nonexistent_foo' in err
        assert 'nonexistent_bar' not in err

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
env_specs:
  foo:
    packages:
        - nonexistent_foo
  bar:
    packages:
        - nonexistent_bar
commands:
  with_foo:
    conda_app_entry: python --version
    env_spec: foo
  with_bar:
    conda_app_entry: python --version
    env_spec: bar

"""
        }, check)


def test_ask_variables_interactively(monkeypatch):
    def check(dirname):
        project_dir_disable_dedicated_env(dirname)

        def mock_is_interactive():
            return True

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.stdin_is_interactive', mock_is_interactive)

        inputs = ["foo", "bar"]

        def mock_console_input(prompt, encrypted):
            return inputs.pop(0)

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.console_input', mock_console_input)

        res = _parse_args_and_run_subcommand(['anaconda-project', 'prepare', '--directory', dirname])
        assert res == 0

        local_state = LocalStateFile.load_for_directory(dirname)
        assert local_state.get_value(['variables', 'FOO']) == 'foo'
        assert local_state.get_value(['variables', 'BAR_PASSWORD']) is None
        assert set(keyring.fallback_data().values()) == set(['bar'])

    keyring.enable_fallback_keyring()
    try:
        with_directory_contents_completing_project_file(
            {DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: null
  BAR_PASSWORD: null
"""}, check)
    finally:
        keyring.disable_fallback_keyring()


def test_ask_variables_interactively_empty_answer_re_asks(monkeypatch):
    def check(dirname):
        project_dir_disable_dedicated_env(dirname)

        def mock_is_interactive():
            return True

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.stdin_is_interactive', mock_is_interactive)

        inputs = ["", "foo", "bar"]

        def mock_console_input(prompt, encrypted):
            return inputs.pop(0)

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.console_input', mock_console_input)

        res = _parse_args_and_run_subcommand(['anaconda-project', 'prepare', '--directory', dirname])
        assert res == 0

        local_state = LocalStateFile.load_for_directory(dirname)
        assert local_state.get_value(['variables', 'FOO']) == 'foo'
        assert local_state.get_value(['variables', 'BAR']) == 'bar'

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: null
  BAR: null
"""}, check)


def test_ask_variables_interactively_whitespace_answer_re_asks(monkeypatch):
    def check(dirname):
        project_dir_disable_dedicated_env(dirname)

        def mock_is_interactive():
            return True

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.stdin_is_interactive', mock_is_interactive)

        inputs = ["    ", "foo", "bar"]

        def mock_console_input(prompt, encrypted):
            return inputs.pop(0)

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.console_input', mock_console_input)

        res = _parse_args_and_run_subcommand(['anaconda-project', 'prepare', '--directory', dirname])
        assert res == 0

        local_state = LocalStateFile.load_for_directory(dirname)
        assert local_state.get_value(['variables', 'FOO']) == 'foo'
        assert local_state.get_value(['variables', 'BAR']) == 'bar'

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: null
  BAR: null
"""}, check)


_foo_and_bar_missing = ("missing requirement to run this project: BAR environment variable must be set.\n" +
                        "  Environment variable BAR is not set.\n" +
                        "missing requirement to run this project: FOO environment variable must be set.\n" +
                        "  Environment variable FOO is not set.\n")


def test_ask_variables_interactively_eof_answer_gives_up(monkeypatch, capsys):
    def check(dirname):
        project_dir_disable_dedicated_env(dirname)

        def mock_is_interactive():
            return True

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.stdin_is_interactive', mock_is_interactive)

        def mock_console_input(prompt, encrypted):
            return None

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.console_input', mock_console_input)

        res = _parse_args_and_run_subcommand(['anaconda-project', 'prepare', '--directory', dirname])
        assert res == 1

        out, err = capsys.readouterr()

        assert err == _foo_and_bar_missing

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: null
  BAR: null
"""}, check)


def test_ask_variables_interactively_then_set_variable_fails(monkeypatch, capsys):
    def check(dirname):
        project_dir_disable_dedicated_env(dirname)

        def mock_is_interactive():
            return True

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.stdin_is_interactive', mock_is_interactive)

        inputs = ["foo", "bar"]

        def mock_console_input(prompt, encrypted):
            return inputs.pop(0)

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.console_input', mock_console_input)

        def mock_set_variables(project, env_spec_name, vars_and_values, prepare_result):
            return SimpleStatus(success=False, description="Set variables FAIL")

        monkeypatch.setattr('anaconda_project.project_ops.set_variables', mock_set_variables)

        res = _parse_args_and_run_subcommand(['anaconda-project', 'prepare', '--directory', dirname])
        assert res == 1

        out, err = capsys.readouterr()

        assert err == _foo_and_bar_missing + "Set variables FAIL\n"

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: null
  BAR: null
"""}, check)


def test_no_ask_variables_interactively_not_interactive(monkeypatch, capsys):
    def check(dirname):
        project_dir_disable_dedicated_env(dirname)

        def mock_is_interactive():
            return False

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.stdin_is_interactive', mock_is_interactive)

        def mock_console_input(prompt, encrypted):
            raise Exception("should not have been called")

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.console_input', mock_console_input)

        res = _parse_args_and_run_subcommand(['anaconda-project', 'prepare', '--directory', dirname])
        assert res == 1

        out, err = capsys.readouterr()

        assert err == _foo_and_bar_missing

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: null
  BAR: null
"""}, check)


def test_no_ask_variables_interactively_if_no_variables_missing_but_prepare_fails(monkeypatch, capsys):
    def check(dirname):
        project_dir_disable_dedicated_env(dirname)

        def mock_is_interactive():
            return True

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.stdin_is_interactive', mock_is_interactive)

        def mock_console_input(prompt, encrypted):
            raise Exception("Should not have called this, prompt " + prompt)

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.console_input', mock_console_input)

        res = _parse_args_and_run_subcommand(['anaconda-project', 'prepare', '--directory', dirname])
        assert res == 1

        out, err = capsys.readouterr()

        assert out == ""
        assert err == ("%s: env_specs should be a dictionary from environment name to environment attributes, not 42\n"
                       "Unable to load the project.\n") % DEFAULT_PROJECT_FILENAME

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
variables:
  FOO: { default: "foo" }
  BAR: { default: "bar" }

# breakage
env_specs: 42

"""
        }, check)


@pytest.mark.slow
def test_no_ask_conda_prefix_interactively(monkeypatch, capsys):
    def check(dirname):
        project_dir_disable_dedicated_env(dirname)

        def mock_is_interactive():
            return True

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.stdin_is_interactive', mock_is_interactive)

        def mock_console_input(prompt, encrypted):
            raise Exception("should not have been called")

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.console_input', mock_console_input)

        res = _parse_args_and_run_subcommand(['anaconda-project', 'prepare', '--directory', dirname])
        assert res == 1

        out, err = capsys.readouterr()

        assert err.endswith("Conda environment is missing packages: nonexistent_package_name\n")

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
packages:
 - nonexistent_package_name
"""}, check)


def test_display_suggestions(monkeypatch, capsys):
    def check(dirname):
        project_dir_disable_dedicated_env(dirname)

        def mock_is_interactive():
            return True

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.stdin_is_interactive', mock_is_interactive)

        def mock_console_input(prompt, encrypted):
            raise Exception("should not have been called")

        monkeypatch.setattr('anaconda_project.internal.cli.console_utils.console_input', mock_console_input)

        res = _parse_args_and_run_subcommand(['anaconda-project', 'prepare', '--directory', dirname])
        assert res == 0

        out, err = capsys.readouterr()

        assert """Potential issues with this project:
  * anaconda-project.yml: Unknown field name 'weird_field'

The project is ready to run commands.
Use `anaconda-project list-commands` to see what's available.
""" == out
        assert '' == err

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
packages: []
weird_field: 42
"""}, check)
