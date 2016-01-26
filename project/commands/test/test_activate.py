from __future__ import absolute_import, print_function

import pytest

from project.commands.activate import activate, main
from project.internal.project_file import PROJECT_FILENAME
from project.internal.test.tmpfile_utils import with_directory_contents


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
        result = activate(dirname)
        assert can_connect_args['port'] == 6379
        assert result is not None
        assert ['export REDIS_URL=redis://localhost:6379'] == result

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  REDIS_URL: {}
"""}, activate_redis_url)


def test_main(monkeypatch, capsys):
    can_connect_args = _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch)

    def main_redis_url(dirname):
        main(['activate', dirname])

    with pytest.raises(SystemExit) as excinfo:
        with_directory_contents({PROJECT_FILENAME: """
runtime:
  REDIS_URL: {}
"""}, main_redis_url)

    assert 0 == excinfo.value.code
    assert can_connect_args['port'] == 6379

    out, err = capsys.readouterr()
    assert "export REDIS_URL=redis://localhost:6379\n" == out
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
        main(['activate'])

    with pytest.raises(SystemExit) as excinfo:
        with_directory_contents({PROJECT_FILENAME: """
runtime:
  REDIS_URL: {}
"""}, main_redis_url)

    assert 0 == excinfo.value.code
    assert can_connect_args['port'] == 6379

    out, err = capsys.readouterr()
    assert "export REDIS_URL=redis://localhost:6379\n" == out
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
        main(['activate', dirname])

    with pytest.raises(SystemExit) as excinfo:
        with_directory_contents({PROJECT_FILENAME: """
runtime:
  REDIS_URL: {}
"""}, main_redis_url)

    assert 1 == excinfo.value.code

    out, err = capsys.readouterr()
    assert "missing requirement" in err
    assert "All ports between 6380 and 6450 were in use" in err
