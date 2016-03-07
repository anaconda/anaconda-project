from __future__ import absolute_import, print_function

from copy import deepcopy
import errno
import pytest
import os

from project.commands.launch import launch_command, main
from project.internal.test.tmpfile_utils import with_directory_contents
from project.prepare import UI_MODE_NOT_INTERACTIVE
from project.project_file import PROJECT_FILENAME

from project.test.project_utils import project_dir_disable_dedicated_env


class Args(object):
    def __init__(self, **kwargs):
        self.project_dir = "."
        self.ui_mode = UI_MODE_NOT_INTERACTIVE
        for key in kwargs:
            setattr(self, key, kwargs[key])


def test_launch_command(monkeypatch):

    executed = {}

    def mock_execvpe(file, args, env):
        executed['file'] = file
        executed['args'] = args
        executed['env'] = env

    mock_environ = deepcopy(os.environ)
    mock_environ['FOO'] = 'bar'

    monkeypatch.setattr('os.environ', mock_environ)
    monkeypatch.setattr('os.execvpe', mock_execvpe)

    def check_launch(dirname):
        project_dir_disable_dedicated_env(dirname)

        result = launch_command(dirname, UI_MODE_NOT_INTERACTIVE)
        assert result is None
        assert 'file' in executed
        assert 'args' in executed
        assert 'env' in executed
        assert executed['file'].endswith("python")
        assert executed['args'][0].endswith("python")
        assert '--version' == executed['args'][1]
        assert 'bar' == executed['env']['FOO']

    with_directory_contents(
        {PROJECT_FILENAME: """
runtime:
  FOO: {}

app:
  entry: python --version

"""}, check_launch)


def test_launch_command_no_app_entry(capsys):
    def check_launch_no_app_entry(dirname):
        project_dir_disable_dedicated_env(dirname)
        result = launch_command(dirname, UI_MODE_NOT_INTERACTIVE)
        assert result is None

    with_directory_contents({PROJECT_FILENAME: """

"""}, check_launch_no_app_entry)

    out, err = capsys.readouterr()
    assert out == ""
    assert 'No known launch command' in err


def test_launch_command_failed_prepare(capsys):
    def check_launch_failed_prepare(dirname):
        project_dir_disable_dedicated_env(dirname)
        result = launch_command(dirname, UI_MODE_NOT_INTERACTIVE)
        assert result is None

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  - WILL_NOT_BE_SET
"""}, check_launch_failed_prepare)

    out, err = capsys.readouterr()
    assert out == ""
    assert 'Environment variable WILL_NOT_BE_SET is not set' in err


def test_main(monkeypatch, capsys):
    executed = {}

    def mock_execvpe(file, args, env):
        executed['file'] = file
        executed['args'] = args
        executed['env'] = env

    monkeypatch.setattr('os.execvpe', mock_execvpe)

    def check_launch_main(dirname):
        project_dir_disable_dedicated_env(dirname)
        result = main(Args(project_dir=dirname))

        assert result is None
        assert 'file' in executed
        assert 'args' in executed
        assert 'env' in executed
        assert executed['file'].endswith("python")
        assert executed['args'][0].endswith("python")
        assert '--version' == executed['args'][1]

    with pytest.raises(SystemExit) as excinfo:
        with_directory_contents({PROJECT_FILENAME: """
app:
  entry: python --version

"""}, check_launch_main)

    # main() assumes failure if execvpe returns, as it did here
    assert 1 == excinfo.value.code

    out, err = capsys.readouterr()
    assert "" == out
    assert "" == err


def test_main_failed_exec(monkeypatch, capsys):
    def mock_execvpe(file, args, env):
        raise OSError(errno.ENOMEM, "It did not work, Michael")

    monkeypatch.setattr('os.execvpe', mock_execvpe)

    def check_launch_main(dirname):
        project_dir_disable_dedicated_env(dirname)
        result = main(Args(project_dir=dirname))

        assert result is None

    with pytest.raises(SystemExit) as excinfo:
        with_directory_contents({PROJECT_FILENAME: """
app:
  entry: python --version

"""}, check_launch_main)

    assert 1 == excinfo.value.code

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

    def check_launch_main(dirname):
        from os.path import abspath as real_abspath

        def mock_abspath(path):
            if path == ".":
                return dirname
            else:
                return real_abspath(path)

        monkeypatch.setattr('os.path.abspath', mock_abspath)

        project_dir_disable_dedicated_env(dirname)
        result = main(Args(project_dir=dirname))

        assert result is None
        assert 'file' in executed
        assert 'args' in executed
        assert 'env' in executed
        assert executed['file'].endswith("python")
        assert executed['args'][0].endswith("python")
        assert '--version' == executed['args'][1]

    with pytest.raises(SystemExit) as excinfo:
        with_directory_contents({PROJECT_FILENAME: """
app:
  entry: python --version

"""}, check_launch_main)

    # main() assumes failure if execvpe returns, as it did here
    assert 1 == excinfo.value.code

    out, err = capsys.readouterr()
    assert "" == out
    assert "" == err
