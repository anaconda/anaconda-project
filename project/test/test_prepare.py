import pytest

from project.internal.test.tmpfile_utils import with_directory_contents
from project.internal.project_file import PROJECT_FILENAME
from project.prepare import prepare
from project.project import Project
from project.plugins.requirement import RequirementRegistry


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


def _monkeypatch_can_connect_to_socket(monkeypatch):
    can_connect_args = dict()

    def mock_can_connect_to_socket(host, port, timeout_seconds=0.5):
        can_connect_args['host'] = host
        can_connect_args['port'] = port
        can_connect_args['timeout_seconds'] = timeout_seconds
        return True

    monkeypatch.setattr("project.plugins.network_util.can_connect_to_socket", mock_can_connect_to_socket)

    return can_connect_args


def test_prepare_redis_url_with_dict_in_runtime_section(monkeypatch):
    can_connect_args = _monkeypatch_can_connect_to_socket(monkeypatch)

    def prepare_redis_url(dirname):
        requirement_registry = RequirementRegistry()
        project = Project(dirname, requirement_registry)
        environ = dict()
        result = prepare(project, environ=environ)
        assert result
        assert dict(REDIS_URL="redis://localhost:6379") == environ
        assert dict(host='localhost', port=6379, timeout_seconds=0.5) == can_connect_args

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  REDIS_URL: {}
"""}, prepare_redis_url)


def test_prepare_redis_url_with_list_in_runtime_section(monkeypatch):
    can_connect_args = _monkeypatch_can_connect_to_socket(monkeypatch)

    def prepare_redis_url(dirname):
        requirement_registry = RequirementRegistry()
        project = Project(dirname, requirement_registry)
        environ = dict()
        result = prepare(project, environ=environ)
        assert result
        assert dict(REDIS_URL="redis://localhost:6379") == environ
        assert dict(host='localhost', port=6379, timeout_seconds=0.5) == can_connect_args

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  - REDIS_URL
"""}, prepare_redis_url)


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
