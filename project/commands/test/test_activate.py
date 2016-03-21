from __future__ import absolute_import, print_function

import pytest

try:
    from shlex import quote
except ImportError:
    from pipes import quote

from project.commands.main import main as toplevel_main
from project.commands.activate import activate, main
from project.internal.test.tmpfile_utils import with_directory_contents
from project.prepare import UI_MODE_NOT_INTERACTIVE
from project.project_file import DEFAULT_PROJECT_FILENAME
from project.local_state_file import DEFAULT_LOCAL_STATE_FILENAME

from project.test.project_utils import project_dir_disable_dedicated_env


class Args(object):
    def __init__(self, **kwargs):
        self.project_dir = "."
        self.ui_mode = UI_MODE_NOT_INTERACTIVE
        for key in kwargs:
            setattr(self, key, kwargs[key])


def _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch):
    can_connect_args = dict()

    def mock_can_connect_to_socket(host, port, timeout_seconds=0.5):
        can_connect_args['host'] = host
        can_connect_args['port'] = port
        can_connect_args['timeout_seconds'] = timeout_seconds
        return True

    monkeypatch.setattr("project.plugins.network_util.can_connect_to_socket", mock_can_connect_to_socket)

    return can_connect_args


def test_activate(monkeypatch):
    can_connect_args = _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch)

    def activate_redis_url(dirname):
        project_dir_disable_dedicated_env(dirname)
        result = activate(dirname, UI_MODE_NOT_INTERACTIVE)
        assert can_connect_args['port'] == 6379
        assert result is not None
        assert ['export PROJECT_DIR=' + quote(dirname), 'export REDIS_URL=redis://localhost:6379'] == result

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
runtime:
  REDIS_URL: {}
    """}, activate_redis_url)


def test_activate_quoting(monkeypatch):
    def activate_foo(dirname):
        project_dir_disable_dedicated_env(dirname)
        result = activate(dirname, UI_MODE_NOT_INTERACTIVE)
        assert result is not None
        assert ["export FOO='$! boo'", 'export PROJECT_DIR=' + dirname] == result

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME: """
runtime:
  FOO: {}
    """,
            DEFAULT_LOCAL_STATE_FILENAME: """
variables:
  FOO: $! boo
"""
        }, activate_foo)


def test_main(monkeypatch, capsys):
    can_connect_args = _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch)

    def main_redis_url(dirname):
        project_dir_disable_dedicated_env(dirname)
        main(Args(project_dir=dirname))

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
runtime:
  REDIS_URL: {}
"""}, main_redis_url)

    assert can_connect_args['port'] == 6379

    out, err = capsys.readouterr()

    assert "export REDIS_URL=redis://localhost:6379\n" in out
    assert "" == err


def test_main_dirname_not_provided_use_pwd(monkeypatch, capsys):
    can_connect_args = _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch)

    def main_redis_url(dirname):
        from os.path import abspath as real_abspath

        def mock_abspath(path):
            if path == ".":
                return dirname
            else:
                return real_abspath(path)

        monkeypatch.setattr('os.path.abspath', mock_abspath)
        project_dir_disable_dedicated_env(dirname)
        with pytest.raises(SystemExit) as excinfo:
            toplevel_main(['anaconda-project', 'activate'])
        assert excinfo.value.code == 0

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
runtime:
  REDIS_URL: {}
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
        with pytest.raises(SystemExit) as excinfo:
            toplevel_main(['anaconda-project', 'activate', dirname])
        assert excinfo.value.code == 0

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
runtime:
  REDIS_URL: {}
"""}, main_redis_url)

    assert can_connect_args['port'] == 6379

    out, err = capsys.readouterr()
    assert "export PROJECT_DIR" in out
    assert "export REDIS_URL=redis://localhost:6379\n" in out
    assert "" == err


def _monkeypatch_can_connect_to_socket_to_fail_to_find_redis(monkeypatch):
    def mock_can_connect_to_socket(host, port, timeout_seconds=0.5):
        if port == 6379:
            return False  # default Redis not there
        else:
            return True  # can't start a custom Redis here

    monkeypatch.setattr("project.plugins.network_util.can_connect_to_socket", mock_can_connect_to_socket)


def test_main_fails_to_redis(monkeypatch, capsys):
    _monkeypatch_can_connect_to_socket_to_fail_to_find_redis(monkeypatch)

    def main_redis_url(dirname):
        project_dir_disable_dedicated_env(dirname)
        main(Args(project_dir=dirname))

    with pytest.raises(SystemExit) as excinfo:
        with_directory_contents({DEFAULT_PROJECT_FILENAME: """
runtime:
  REDIS_URL: {}
"""}, main_redis_url)

    assert 1 == excinfo.value.code

    out, err = capsys.readouterr()
    assert "missing requirement" in err
    assert "All ports from 6380 to 6449 were in use" in err
