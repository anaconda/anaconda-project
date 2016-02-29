from __future__ import absolute_import, print_function

import pytest

from project.commands.prepare import prepare_command, main
from project.internal.test.tmpfile_utils import with_directory_contents
from project.prepare import UI_MODE_NOT_INTERACTIVE
from project.project_file import PROJECT_FILENAME


def _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch):
    can_connect_args = dict()

    def mock_can_connect_to_socket(host, port, timeout_seconds=0.5):
        can_connect_args['host'] = host
        can_connect_args['port'] = port
        can_connect_args['timeout_seconds'] = timeout_seconds
        return True

    monkeypatch.setattr("project.plugins.network_util.can_connect_to_socket", mock_can_connect_to_socket)

    return can_connect_args


def test_prepare_command(monkeypatch):
    can_connect_args = _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch)

    def prepare_redis_url(dirname):
        result = prepare_command(dirname, UI_MODE_NOT_INTERACTIVE)
        assert can_connect_args['port'] == 6379
        assert result

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  REDIS_URL: {}
"""}, prepare_redis_url)


def _monkeypatch_open_new_tab(monkeypatch):
    from tornado.ioloop import IOLoop

    http_results = {}

    def mock_open_new_tab(url):
        from project.internal.test.http_utils import http_get_async, http_post_async
        from tornado import gen

        @gen.coroutine
        def do_http():
            http_results['get'] = yield http_get_async(url)
            http_results['post'] = yield http_post_async(url, body="")

        IOLoop.current().add_callback(do_http)

    monkeypatch.setattr('webbrowser.open_new_tab', mock_open_new_tab)

    return http_results


def test_main(monkeypatch, capsys):
    can_connect_args = _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch)
    _monkeypatch_open_new_tab(monkeypatch)

    def main_redis_url(dirname):
        main(['prepare', dirname])

    with pytest.raises(SystemExit) as excinfo:
        with_directory_contents({PROJECT_FILENAME: """
runtime:
  REDIS_URL: {}
"""}, main_redis_url)

    assert 0 == excinfo.value.code
    assert can_connect_args['port'] == 6379

    out, err = capsys.readouterr()
    assert "# Configure the project at " in out
    assert "" == err


def test_main_dirname_not_provided_use_pwd(monkeypatch, capsys):
    can_connect_args = _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch)
    _monkeypatch_open_new_tab(monkeypatch)

    def main_redis_url(dirname):
        from os.path import abspath as real_abspath

        def mock_abspath(path):
            if path == ".":
                return dirname
            else:
                return real_abspath(path)

        monkeypatch.setattr('os.path.abspath', mock_abspath)
        main(['prepare'])

    with pytest.raises(SystemExit) as excinfo:
        with_directory_contents({PROJECT_FILENAME: """
runtime:
  REDIS_URL: {}
"""}, main_redis_url)

    assert 0 == excinfo.value.code
    assert can_connect_args['port'] == 6379

    out, err = capsys.readouterr()
    assert "# Configure the project at " in out
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
    _monkeypatch_open_new_tab(monkeypatch)

    from project.prepare import prepare as real_prepare

    def _mock_prepare_do_not_keep_going(project,
                                        environ=None,
                                        ui_mode=UI_MODE_NOT_INTERACTIVE,
                                        keep_going_until_success=False,
                                        io_loop=None,
                                        show_url=None):
        return real_prepare(project, environ, ui_mode, False, io_loop, show_url)

    monkeypatch.setattr('project.prepare.prepare', _mock_prepare_do_not_keep_going)

    def main_redis_url(dirname):
        main(['prepare', dirname])

    with pytest.raises(SystemExit) as excinfo:
        with_directory_contents({PROJECT_FILENAME: """
runtime:
  REDIS_URL: {}
"""}, main_redis_url)

    assert 1 == excinfo.value.code

    out, err = capsys.readouterr()
    assert "missing requirement" in err
    assert "All ports from 6380 to 6449 were in use" in err
