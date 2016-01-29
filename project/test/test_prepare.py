from __future__ import absolute_import

import pytest

from project.internal.test.tmpfile_utils import with_directory_contents
from project.plugins.requirement import RequirementRegistry
from project.prepare import prepare, unprepare, UI_MODE_BROWSER
from project.project import Project
from project.project_file import PROJECT_FILENAME


def test_prepare_empty_directory():
    def prepare_empty(dirname):
        requirement_registry = RequirementRegistry()
        project = Project(dirname, requirement_registry)
        environ = dict()
        result = prepare(project, environ=environ)
        assert result
        assert len(environ) == 0

    with_directory_contents(dict(), prepare_empty)


def test_prepare_bad_ui_mode():
    def prepare_bad_ui_mode(dirname):
        with pytest.raises(ValueError) as excinfo:
            requirement_registry = RequirementRegistry()
            project = Project(dirname, requirement_registry)
            environ = dict()
            prepare(project, ui_mode="BAD_UI_MODE", environ=environ)
        assert "invalid UI mode" in repr(excinfo.value)

    with_directory_contents(dict(), prepare_bad_ui_mode)


def test_unprepare_empty_directory():
    def unprepare_empty(dirname):
        requirement_registry = RequirementRegistry()
        project = Project(dirname, requirement_registry)
        result = unprepare(project)
        assert result is None

    with_directory_contents(dict(), unprepare_empty)


def test_default_to_system_environ():
    def prepare_system_environ(dirname):
        requirement_registry = RequirementRegistry()
        project = Project(dirname, requirement_registry)
        prepare(project)
        # we should really improve this test to check that we
        # really put something in os.environ, but for now
        # we don't have the capability to load a default
        # value from the project file and set it

    with_directory_contents(dict(), prepare_system_environ)


def test_prepare_some_env_var_already_set():
    def prepare_some_env_var(dirname):
        requirement_registry = RequirementRegistry()
        project = Project(dirname, requirement_registry)
        environ = dict(FOO='bar')
        result = prepare(project, environ=environ)
        assert result
        assert dict(FOO='bar') == environ

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  FOO: {}
"""}, prepare_some_env_var)


def test_prepare_some_env_var_not_set():
    def prepare_some_env_var(dirname):
        requirement_registry = RequirementRegistry()
        project = Project(dirname, requirement_registry)
        environ = dict(BAR='bar')
        result = prepare(project, environ=environ)
        assert not result
        assert dict(BAR='bar') == environ

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  FOO: {}
"""}, prepare_some_env_var)


def test_prepare_with_browser(monkeypatch):
    from tornado.ioloop import IOLoop
    io_loop = IOLoop()

    http_results = {}

    def mock_open_new_tab(url):
        from project.internal.test.http_utils import http_get_async, http_post_async
        from tornado import gen

        @gen.coroutine
        def do_http():
            http_results['get'] = yield http_get_async(url)
            http_results['post'] = yield http_post_async(url, body="")

        io_loop.add_callback(do_http)

    monkeypatch.setattr('webbrowser.open_new_tab', mock_open_new_tab)

    def prepare_with_browser(dirname):
        requirement_registry = RequirementRegistry()
        project = Project(dirname, requirement_registry)
        environ = dict(BAR='bar')
        result = prepare(project, environ=environ, io_loop=io_loop, ui_mode=UI_MODE_BROWSER)
        assert not result
        assert dict(BAR='bar') == environ

        # wait for the results of the POST to come back,
        # awesome hack-tacular
        while 'post' not in http_results:
            io_loop.call_later(0.01, lambda: io_loop.stop())
            io_loop.start()

        assert 'get' in http_results
        assert 'post' in http_results

        assert 200 == http_results['get'].code
        assert 200 == http_results['post'].code

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  FOO: {}
"""}, prepare_with_browser)
