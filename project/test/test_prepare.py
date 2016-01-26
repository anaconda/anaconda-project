from __future__ import absolute_import

import pytest

from project.internal.test.tmpfile_utils import with_directory_contents
from project.internal.project_file import PROJECT_FILENAME
from project.prepare import prepare, unprepare
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
