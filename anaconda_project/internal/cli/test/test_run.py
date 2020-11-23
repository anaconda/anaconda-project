# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from copy import deepcopy
import errno
import platform
import os

from anaconda_project.internal.cli.main import _parse_args_and_run_subcommand
from anaconda_project.internal.cli.run import run_command, main
from anaconda_project.internal.cli.prepare_with_mode import UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT
from anaconda_project.internal.test.tmpfile_utils import (with_directory_contents,
                                                          with_directory_contents_completing_project_file)
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME

from anaconda_project.test.project_utils import project_dir_disable_dedicated_env


class Args(object):
    def __init__(self, **kwargs):
        self.directory = "."
        self.env_spec = None
        self.mode = UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT
        self.command = None
        self.extra_args_for_command = None
        for key in kwargs:
            setattr(self, key, kwargs[key])


python_exe = "python"
if platform.system() == 'Windows':
    python_exe = "python.exe"


def test_run_command(monkeypatch):

    executed = {}

    def mock_execvpe(file, args, env):
        executed['file'] = file
        executed['args'] = args
        executed['env'] = env

    mock_environ = deepcopy(os.environ)
    mock_environ['FOO'] = 'bar'

    monkeypatch.setattr('os.environ', mock_environ)
    monkeypatch.setattr('os.execvpe', mock_execvpe)

    def check_run(dirname):
        project_dir_disable_dedicated_env(dirname)

        result = run_command(dirname,
                             UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT,
                             conda_environment=None,
                             command_name=None,
                             extra_command_args=None)
        assert result is None
        assert 'file' in executed
        assert 'args' in executed
        assert 'env' in executed
        assert executed['file'].endswith(python_exe)
        assert executed['args'][0].endswith(python_exe)
        assert '--version' == executed['args'][1]
        assert 'bar' == executed['env']['FOO']

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
variables:
  FOO: {}

commands:
  default:
    conda_app_entry: python --version

"""
        }, check_run)


def test_run_command_no_app_entry(capsys):
    def check_run_no_app_entry(dirname):
        project_dir_disable_dedicated_env(dirname)
        result = run_command(dirname,
                             UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT,
                             conda_environment=None,
                             command_name=None,
                             extra_command_args=None)
        assert result is None

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """

"""}, check_run_no_app_entry)

    out, err = capsys.readouterr()
    assert out == ""
    assert 'No known run command' in err


def test_run_command_nonexistent_project(capsys):
    def check_run_nonexistent(dirname):
        project_dir = os.path.join(dirname, "nope")
        result = _parse_args_and_run_subcommand(['anaconda-project', 'run', '--directory', project_dir])

        assert 1 == result

        out, err = capsys.readouterr()
        assert out == ""
        assert ("Project directory '%s' does not exist." % project_dir) in err

    with_directory_contents(dict(), check_run_nonexistent)


def test_run_command_failed_prepare(capsys):
    def check_run_failed_prepare(dirname):
        project_dir_disable_dedicated_env(dirname)
        result = run_command(dirname,
                             UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT,
                             conda_environment=None,
                             command_name=None,
                             extra_command_args=None)
        assert result is None

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
variables:
  - WILL_NOT_BE_SET
"""}, check_run_failed_prepare)

    out, err = capsys.readouterr()
    assert out == ""
    assert 'Environment variable WILL_NOT_BE_SET is not set' in err


def test_main(monkeypatch, capsys):
    def mock_conda_create(prefix, pkgs, channels):
        raise RuntimeError("this test should not create an environment in %s with pkgs %r" % (prefix, pkgs))

    monkeypatch.setattr('anaconda_project.internal.conda_api.create', mock_conda_create)

    executed = {}

    def mock_execvpe(file, args, env):
        executed['file'] = file
        executed['args'] = args
        executed['env'] = env

    monkeypatch.setattr('os.execvpe', mock_execvpe)

    def check_run_main(dirname):
        project_dir_disable_dedicated_env(dirname)
        result = main(Args(directory=dirname))

        assert 1 == result
        assert 'file' in executed
        assert 'args' in executed
        assert 'env' in executed
        assert executed['file'].endswith(python_exe)
        assert executed['args'][0].endswith(python_exe)
        assert '--version' == executed['args'][1]

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  default:
    conda_app_entry: python --version

"""}, check_run_main)

    out, err = capsys.readouterr()
    assert "" == out
    assert "" == err


def test_main_failed_exec(monkeypatch, capsys):
    def mock_execvpe(file, args, env):
        raise OSError(errno.ENOMEM, "It did not work, Michael")

    monkeypatch.setattr('os.execvpe', mock_execvpe)

    def check_run_main(dirname):
        project_dir_disable_dedicated_env(dirname)
        result = main(Args(directory=dirname))

        assert 1 == result

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  default:
    conda_app_entry: python --version

"""}, check_run_main)

    out, err = capsys.readouterr()
    assert "" == out
    assert 'Failed to execute' in err
    assert 'It did not work, Michael' in err


def test_main_dirname_not_provided_use_pwd(monkeypatch, capsys):
    executed = {}

    def mock_execvpe(file, args, env):
        executed['file'] = file
        executed['args'] = args
        executed['env'] = env

    monkeypatch.setattr('os.execvpe', mock_execvpe)

    def check_run_main(dirname):
        from os.path import abspath as real_abspath

        def mock_abspath(path):
            if path == ".":
                return dirname
            else:
                return real_abspath(path)

        monkeypatch.setattr('os.path.abspath', mock_abspath)

        project_dir_disable_dedicated_env(dirname)
        result = _parse_args_and_run_subcommand(['anaconda-project', 'run'])

        assert 1 == result
        assert 'file' in executed
        assert 'args' in executed
        assert 'env' in executed
        assert executed['file'].endswith(python_exe)
        assert executed['args'][0].endswith(python_exe)
        assert '--version' == executed['args'][1]

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  default:
    conda_app_entry: python --version

"""}, check_run_main)

    out, err = capsys.readouterr()
    assert "" == out
    assert "" == err


def test_run_command_extra_args(monkeypatch, capsys):
    executed = {}

    def mock_execvpe(file, args, env):
        executed['file'] = file
        executed['args'] = args
        executed['env'] = env

    monkeypatch.setattr('os.execvpe', mock_execvpe)

    def check_run_main(dirname):
        from os.path import abspath as real_abspath

        def mock_abspath(path):
            if path == ".":
                return dirname
            else:
                return real_abspath(path)

        monkeypatch.setattr('os.path.abspath', mock_abspath)

        project_dir_disable_dedicated_env(dirname)
        result = _parse_args_and_run_subcommand(
            ['anaconda-project', 'run', '--directory', dirname, 'default', 'foo', '$PATH', '--something'])

        assert 1 == result
        assert 'file' in executed
        assert 'args' in executed
        assert 'env' in executed
        assert executed['file'].endswith(python_exe)
        assert executed['args'][0].endswith(python_exe)
        assert len(executed['args']) == 5
        assert '--version' == executed['args'][1]
        assert 'foo' == executed['args'][2]
        assert '$PATH' == executed['args'][3]
        assert '--something' == executed['args'][4]

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  default:
    conda_app_entry: python --version

"""}, check_run_main)

    out, err = capsys.readouterr()
    assert "" == out
    assert "" == err


def test_run_command_verbose(monkeypatch, capsys):
    executed = {}

    def mock_execvpe(file, args, env):
        executed['file'] = file
        executed['args'] = args
        executed['env'] = env

    monkeypatch.setattr('os.execvpe', mock_execvpe)

    def check_run_main(dirname):
        from os.path import abspath as real_abspath

        def mock_abspath(path):
            if path == ".":
                return dirname
            else:
                return real_abspath(path)

        monkeypatch.setattr('os.path.abspath', mock_abspath)

        project_dir_disable_dedicated_env(dirname)
        result = _parse_args_and_run_subcommand(
            ['anaconda-project', '--verbose', 'run', '--directory', dirname, 'default'])

        assert 1 == result
        assert 'file' in executed
        assert 'args' in executed
        assert 'env' in executed
        assert executed['file'].endswith(python_exe)
        assert executed['args'][0].endswith(python_exe)
        assert len(executed['args']) == 2
        assert '--version' == executed['args'][1]

        # conda info is cached so may not be here depending on
        # which other tests run
        log_lines = [
            "$ %s info --json" % executed['env']['CONDA_EXE'],
            "$ %s env config vars list -p %s --json" % (executed['env']['CONDA_EXE'], executed['env']['CONDA_PREFIX']),
            "$ %s --version" % executed['args'][0]
        ]
        log_lines_without_conda_info = log_lines[1:]

        def nl(lines):
            return ("\n".join(lines) + "\n")

        out, err = capsys.readouterr()
        assert "" == out
        assert nl(log_lines) == err or nl(log_lines_without_conda_info) == err

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  default:
    conda_app_entry: python --version

"""}, check_run_main)


def test_run_command_extra_args_with_double_hyphen(monkeypatch, capsys):
    executed = {}

    def mock_execvpe(file, args, env):
        executed['file'] = file
        executed['args'] = args
        executed['env'] = env

    monkeypatch.setattr('os.execvpe', mock_execvpe)

    def check_run_main(dirname):
        from os.path import abspath as real_abspath

        def mock_abspath(path):
            if path == ".":
                return dirname
            else:
                return real_abspath(path)

        monkeypatch.setattr('os.path.abspath', mock_abspath)

        project_dir_disable_dedicated_env(dirname)
        # double hyphen lets us specify "--foo" as a command name
        result = _parse_args_and_run_subcommand(
            ['anaconda-project', 'run', '--directory', dirname, '--', '--foo', '--bar'])

        assert 1 == result
        assert 'file' in executed
        assert 'args' in executed
        assert 'env' in executed
        assert executed['file'].endswith(python_exe)
        assert executed['args'][0].endswith(python_exe)
        assert len(executed['args']) == 3
        assert '--version' == executed['args'][1]
        assert '--bar' == executed['args'][2]

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  "--foo":
    conda_app_entry: python --version
"""}, check_run_main)

    out, err = capsys.readouterr()
    assert "" == out
    assert "" == err


def _is_python_exe(path):
    assert path.endswith(python_exe)


def _test_run_command_foo(command_line, monkeypatch, capsys, file_assertion=_is_python_exe):
    executed = {}

    def mock_execvpe(file, args, env):
        executed['file'] = file
        executed['args'] = args
        executed['env'] = env

    monkeypatch.setattr('os.execvpe', mock_execvpe)

    def check_run_main(dirname):
        from os.path import abspath as real_abspath

        def mock_abspath(path):
            if path == ".":
                return dirname
            else:
                return real_abspath(path)

        monkeypatch.setattr('os.path.abspath', mock_abspath)

        project_dir_disable_dedicated_env(dirname)

        for n, i in enumerate(command_line):
            if i == '<DIRNAME>':
                command_line[n] = dirname

        result = _parse_args_and_run_subcommand(command_line)

        assert 1 == result
        assert 'file' in executed
        assert 'args' in executed
        assert 'env' in executed
        file_assertion(executed['file'])

        out, err = capsys.readouterr()
        assert "" == out
        assert "" == err

        return executed['args'][1:]

    return with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
commands:
  default:
    conda_app_entry: python --version def
  foo:
    conda_app_entry: python --version foo
  bar:
    conda_app_entry: python --version bar
"""
        }, check_run_main)


def test_run_command_specify_name_after_options(monkeypatch, capsys):
    args = _test_run_command_foo(['anaconda-project', 'run', '--directory', '<DIRNAME>', 'foo'], monkeypatch, capsys)

    assert args == ['--version', 'foo']


def test_run_command_specify_name_before_options(monkeypatch, capsys):
    args = _test_run_command_foo(['anaconda-project', 'run', 'foo', '--directory', '<DIRNAME>'], monkeypatch, capsys)
    assert args[:-1] == ['--version', 'foo', '--directory']


def test_run_command_omit_name_use_default(monkeypatch, capsys):
    args = _test_run_command_foo(['anaconda-project', 'run', '--directory', '<DIRNAME>'], monkeypatch, capsys)
    assert args == ['--version', 'def']


def _test_run_nodefault_command(command_line, monkeypatch, capsys, file_assertion=_is_python_exe):
    executed = {}

    def mock_execvpe(file, args, env):
        executed['file'] = file
        executed['args'] = args
        executed['env'] = env

    monkeypatch.setattr('os.execvpe', mock_execvpe)

    def check_run_main(dirname):
        from os.path import abspath as real_abspath

        def mock_abspath(path):
            if path == ".":
                return dirname
            else:
                return real_abspath(path)

        monkeypatch.setattr('os.path.abspath', mock_abspath)

        project_dir_disable_dedicated_env(dirname)

        for n, i in enumerate(command_line):
            if i == '<DIRNAME>':
                command_line[n] = dirname

        result = _parse_args_and_run_subcommand(command_line)

        assert 1 == result
        assert 'file' in executed
        assert 'args' in executed
        assert 'env' in executed
        file_assertion(executed['file'])

        out, err = capsys.readouterr()
        assert "" == out
        assert "" == err

        return executed['args'][1:]

    return with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
commands:
  nodefault:
    conda_app_entry: python --version def
  foo:
    conda_app_entry: python --version foo
  bar:
    conda_app_entry: python --version bar
"""
        }, check_run_main)


def test_run_command_use_default(monkeypatch, capsys):
    args = _test_run_nodefault_command(['anaconda-project', 'run', '--directory', '<DIRNAME>', 'default'], monkeypatch,
                                       capsys)
    assert args == ['--version', 'def']


# can't put an assert in a lambda so this makes us a "lambda" with
# an assert in it
def _func_asserting_contains(what):
    def f(s):
        assert what in s

    return f


def test_run_command_executable_not_in_config(monkeypatch, capsys):
    args = _test_run_command_foo(['anaconda-project', 'run', '--directory', '<DIRNAME>', 'something1', 'something2'],
                                 monkeypatch, capsys, _func_asserting_contains('something1'))
    assert args == ['something2']


def test_run_notebook_not_in_config(monkeypatch, capsys):
    args = _test_run_command_foo(['anaconda-project', 'run', '--directory', '<DIRNAME>', 'something.ipynb'],
                                 monkeypatch, capsys, _func_asserting_contains('jupyter-notebook'))
    assert len(args) == 2
    assert args[0].endswith('something.ipynb')
    assert args[1] == '--NotebookApp.default_url=/notebooks/something.ipynb'


def test_run_command_nonexistent_name(monkeypatch, capsys):
    def check_run_main(dirname):
        from os.path import abspath as real_abspath

        def mock_abspath(path):
            if path == ".":
                return dirname
            else:
                return real_abspath(path)

        monkeypatch.setattr('os.path.abspath', mock_abspath)

        def mock_execvpe(file, args, env):
            assert file == 'nope'
            assert args == ['nope']
            raise OSError("no such file nope")

        monkeypatch.setattr('os.execvpe', mock_execvpe)

        project_dir_disable_dedicated_env(dirname)
        result = _parse_args_and_run_subcommand(['anaconda-project', 'run', '--directory', dirname, 'nope'])

        assert 1 == result

        out, err = capsys.readouterr()
        assert "" == out
        assert "Failed to execute 'nope'" in err

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
commands:
  default:
    conda_app_entry: python --version
  foo:
    conda_app_entry: python --version foo
  bar:
    conda_app_entry: python --version bar
"""
        }, check_run_main)


def _test_run_with_env_vars(command_line, monkeypatch, capsys, file_assertion=_is_python_exe):
    executed = {}

    def mock_execvpe(file, args, env):
        executed['file'] = file
        executed['args'] = args
        executed['env'] = env

    monkeypatch.setattr('os.execvpe', mock_execvpe)

    def check_run_main(dirname):
        from os.path import abspath as real_abspath

        def mock_abspath(path):
            if path == ".":
                return dirname
            else:
                return real_abspath(path)

        monkeypatch.setattr('os.path.abspath', mock_abspath)

        project_dir_disable_dedicated_env(dirname)

        for n, i in enumerate(command_line):
            if i == '<DIRNAME>':
                command_line[n] = dirname

        result = _parse_args_and_run_subcommand(command_line)

        assert 1 == result
        assert 'file' in executed
        assert 'args' in executed
        assert 'env' in executed
        file_assertion(executed['file'])

        out, err = capsys.readouterr()
        assert "" == out
        assert "" == err

        return executed['env']

    return with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
variables:
  MY_VARIABLE: "project"
commands:
  default:
    conda_app_entry: python --version
  foo:
    variables:
      MY_VARIABLE: "command"
    conda_app_entry: python --version foo
  bar:
    conda_app_entry: python --version bar
"""
        }, check_run_main)


def test_run_command_vars_project(monkeypatch, capsys):
    env = _test_run_with_env_vars(['anaconda-project', 'run', '--directory', '<DIRNAME>', 'default'], monkeypatch,
                                  capsys)
    assert "MY_VARIABLE" in env
    assert env['MY_VARIABLE'] == 'project'


def test_run_command_vars_command_override_project(monkeypatch, capsys):
    env = _test_run_with_env_vars(['anaconda-project', 'run', '--directory', '<DIRNAME>', 'foo'], monkeypatch, capsys)
    assert "MY_VARIABLE" in env
    assert env['MY_VARIABLE'] == 'command'


def _test_run_with_conda_vars(command_line, monkeypatch, capsys, file_assertion=_is_python_exe, conda_env_var=False):
    executed = {}

    def mock_get_env_vars(prefix):
        return {'MY_VARIABLE': 'conda'}

    def mock_execvpe(file, args, env):
        executed['file'] = file
        executed['args'] = args
        executed['env'] = env

    mock_environ = deepcopy(os.environ)
    mock_environ['CONDA_PREFIX'] = os.environ['CONDA_PREFIX']

    monkeypatch.setattr('os.environ', mock_environ)
    monkeypatch.setattr('anaconda_project.internal.conda_api.get_env_vars', mock_get_env_vars)
    monkeypatch.setattr('os.execvpe', mock_execvpe)

    def check_run_main(dirname):
        from os.path import abspath as real_abspath

        def mock_abspath(path):
            if path == ".":
                return dirname
            else:
                return real_abspath(path)

        monkeypatch.setattr('os.path.abspath', mock_abspath)

        project_dir_disable_dedicated_env(dirname)

        for n, i in enumerate(command_line):
            if i == '<DIRNAME>':
                command_line[n] = dirname

        result = _parse_args_and_run_subcommand(command_line)

        assert 1 == result
        assert 'file' in executed
        assert 'args' in executed
        assert 'env' in executed
        file_assertion(executed['file'])

        out, err = capsys.readouterr()
        assert "" == out
        assert "" == err

        return executed['env']

    return with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
commands:
  default:
    conda_app_entry: python --version
  foo:
    variables:
      MY_VARIABLE: "command"
    conda_app_entry: python --version foo
  bar:
    conda_app_entry: python --version bar
"""
        }, check_run_main)


def test_run_command_vars_conda(monkeypatch, capsys):
    env = _test_run_with_conda_vars(['anaconda-project', 'run', '--directory', '<DIRNAME>', 'default'], monkeypatch,
                                    capsys)
    assert "MY_VARIABLE" in env
    assert env['MY_VARIABLE'] == 'conda'


def test_run_command_vars_cmd_override_conda(monkeypatch, capsys):
    env = _test_run_with_conda_vars(['anaconda-project', 'run', '--directory', '<DIRNAME>', 'foo'], monkeypatch, capsys)
    assert "MY_VARIABLE" in env
    assert env['MY_VARIABLE'] == 'command'


def _test_run_with_environ_vars(command_line, monkeypatch, capsys, file_assertion=_is_python_exe, conda_env_var=False):
    executed = {}

    def mock_get_env_vars(prefix):
        return {'MY_VARIABLE': 'conda'}

    def mock_execvpe(file, args, env):
        executed['file'] = file
        executed['args'] = args
        executed['env'] = env

    mock_environ = deepcopy(os.environ)
    mock_environ['CONDA_PREFIX'] = os.environ['CONDA_PREFIX']
    mock_environ['MY_VARIABLE'] = 'environ'

    monkeypatch.setattr('os.environ', mock_environ)
    monkeypatch.setattr('anaconda_project.internal.conda_api.get_env_vars', mock_get_env_vars)
    monkeypatch.setattr('os.execvpe', mock_execvpe)

    def check_run_main(dirname):
        from os.path import abspath as real_abspath

        def mock_abspath(path):
            if path == ".":
                return dirname
            else:
                return real_abspath(path)

        monkeypatch.setattr('os.path.abspath', mock_abspath)

        project_dir_disable_dedicated_env(dirname)

        for n, i in enumerate(command_line):
            if i == '<DIRNAME>':
                command_line[n] = dirname

        result = _parse_args_and_run_subcommand(command_line)

        assert 1 == result
        assert 'file' in executed
        assert 'args' in executed
        assert 'env' in executed
        file_assertion(executed['file'])

        out, err = capsys.readouterr()
        assert "" == out
        assert "" == err

        return executed['env']

    return with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
commands:
  default:
    conda_app_entry: python --version
  foo:
    variables:
      MY_VARIABLE: "command"
    conda_app_entry: python --version foo
  bar:
    conda_app_entry: python --version bar
"""
        }, check_run_main)


def test_run_command_vars_environ(monkeypatch, capsys):
    env = _test_run_with_environ_vars(['anaconda-project', 'run', '--directory', '<DIRNAME>', 'default'], monkeypatch,
                                      capsys)
    assert "MY_VARIABLE" in env
    assert env['MY_VARIABLE'] == 'environ'


def test_run_command_vars_environ_override_cmd(monkeypatch, capsys):
    env = _test_run_with_environ_vars(['anaconda-project', 'run', '--directory', '<DIRNAME>', 'foo'], monkeypatch,
                                      capsys)
    assert "MY_VARIABLE" in env
    assert env['MY_VARIABLE'] == 'environ'
