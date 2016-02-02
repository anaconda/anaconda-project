from __future__ import absolute_import

import os

import pytest

from project.internal.test.tmpfile_utils import with_directory_contents
from project.local_state_file import LocalStateFile, LOCAL_STATE_DIRECTORY, LOCAL_STATE_FILENAME
from project.plugins.provider import Provider, ProvideContext, ProviderRegistry, EnvVarProvider
from project.plugins.requirement import EnvVarRequirement
from project.project import Project
from project.project_file import PROJECT_FILENAME


def test_find_by_env_var():
    registry = ProviderRegistry()
    found = registry.find_by_env_var(requirement=None, env_var="FOO")
    assert 1 == len(found)
    assert isinstance(found[0], EnvVarProvider)
    assert "EnvVarProvider" == found[0].config_key


def test_env_var_provider_title():
    provider = EnvVarProvider()
    assert "Manually set environment variable" == provider.title


def test_find_by_class_name():
    registry = ProviderRegistry()
    found = registry.find_by_class_name(class_name="ProjectScopedCondaEnvProvider")
    assert found is not None
    assert found.__class__.__name__ == "ProjectScopedCondaEnvProvider"


def test_find_by_class_name_not_found():
    registry = ProviderRegistry()
    found = registry.find_by_class_name(class_name="NotAThing")
    assert found is None


def test_provider_default_method_implementations():
    class UselessProvider(Provider):
        @property
        def title(self):
            return ""

        def read_config(self, local_state, requirement):
            return dict()

        def provide(self, requirement, context):
            pass

    provider = UselessProvider()
    # this method is supposed to do nothing by default (ignore
    # unknown names, in particular)
    provider.set_config_value_from_string(local_state_file=None, requirement=None, name=None, value_string=None)


def _load_env_var_requirement(dirname, env_var):
    project = Project(dirname)
    for requirement in project.requirements:
        if isinstance(requirement, EnvVarRequirement) and requirement.env_var == env_var:
            return requirement
    raise RuntimeError("No requirement for %s was in the project file, only %r" % (env_var, project.requirements))


def test_env_var_provider_with_no_value():
    def check_env_var_provider(dirname):
        provider = EnvVarProvider()
        requirement = _load_env_var_requirement(dirname, "FOO")
        local_state_file = LocalStateFile.load_for_directory(dirname)
        config = provider.read_config(local_state_file, requirement)
        assert dict() == config
        context = ProvideContext(environ=dict(), local_state_file=local_state_file, config=config)

        provider.provide(requirement, context=context)
        assert 'FOO' not in context.environ

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  - FOO
"""}, check_env_var_provider)


def test_env_var_provider_with_default_value_in_project_file():
    def check_env_var_provider(dirname):
        provider = EnvVarProvider()
        requirement = _load_env_var_requirement(dirname, "FOO")
        assert dict(default='from_default') == requirement.options
        local_state_file = LocalStateFile.load_for_directory(dirname)
        config = provider.read_config(local_state_file, requirement)
        context = ProvideContext(environ=dict(), local_state_file=local_state_file, config=config)
        provider.provide(requirement, context=context)
        assert 'FOO' in context.environ
        assert 'from_default' == context.environ['FOO']

    with_directory_contents(
        {PROJECT_FILENAME: """
runtime:
  FOO:
    default: from_default
"""}, check_env_var_provider)


def test_env_var_provider_with_value_set_in_environment():
    def check_env_var_provider(dirname):
        provider = EnvVarProvider()
        requirement = _load_env_var_requirement(dirname, "FOO")
        local_state_file = LocalStateFile.load_for_directory(dirname)
        config = provider.read_config(local_state_file, requirement)
        assert dict() == config
        context = ProvideContext(environ=dict(FOO='from_environ'), local_state_file=local_state_file, config=config)
        provider.provide(requirement, context=context)
        assert 'FOO' in context.environ
        assert 'from_environ' == context.environ['FOO']

    # set a default to be sure we prefer 'environ' instead
    with_directory_contents(
        {PROJECT_FILENAME: """
runtime:
  FOO:
    default: from_default
"""}, check_env_var_provider)


def test_env_var_provider_with_value_set_in_local_state():
    def check_env_var_provider(dirname):
        provider = EnvVarProvider()
        requirement = _load_env_var_requirement(dirname, "FOO")
        local_state_file = LocalStateFile.load_for_directory(dirname)
        config = provider.read_config(local_state_file, requirement)
        assert dict(value="from_local_state") == config
        # set an environ to be sure we override it with local state
        context = ProvideContext(environ=dict(FOO='from_environ'), local_state_file=local_state_file, config=config)
        provider.provide(requirement, context=context)
        assert 'FOO' in context.environ
        assert 'from_local_state' == context.environ['FOO']

    with_directory_contents(
        {PROJECT_FILENAME: """
runtime:
  FOO:
    default: from_default
    """,
         LOCAL_STATE_DIRECTORY + "/" + LOCAL_STATE_FILENAME: """
variables:
  FOO: from_local_state
"""}, check_env_var_provider)


def test_fail_to_find_by_service():
    registry = ProviderRegistry()
    found = registry.find_by_service(requirement=None, service="nope")
    assert 0 == len(found)


def test_provide_context_properties():
    def check_provide_contents(dirname):
        environ = dict(foo='bar')
        local_state_file = LocalStateFile.load_for_directory(dirname)
        context = ProvideContext(environ=environ, local_state_file=local_state_file, config=dict(foo=42))
        assert dict(foo='bar') == context.environ
        assert [] == context.errors
        context.append_error("foo")
        context.append_error("bar")
        assert ["foo", "bar"] == context.errors

        assert [] == context.logs
        context.append_log("foo")
        context.append_log("bar")
        assert ["foo", "bar"] == context.logs

        assert dict(foo=42) == context.config

    with_directory_contents(dict(), check_provide_contents)


def test_provide_context_ensure_work_directory():
    def check_provide_contents(dirname):
        environ = dict()
        local_state_file = LocalStateFile.load_for_directory(dirname)
        context = ProvideContext(environ=environ, local_state_file=local_state_file, config={})
        workpath = context.ensure_work_directory("foo")
        assert os.path.isdir(workpath)
        parent = os.path.dirname(workpath)
        assert parent.endswith("/run")
        parent = os.path.dirname(parent)
        assert parent.endswith("/.anaconda")

        # be sure we can create if it already exists
        workpath2 = context.ensure_work_directory("foo")
        assert os.path.isdir(workpath2)
        assert workpath == workpath2

    with_directory_contents(dict(), check_provide_contents)


def test_provide_context_ensure_work_directory_cannot_create(monkeypatch):
    def mock_makedirs(path, mode=0):
        raise IOError("this is not EEXIST")

    monkeypatch.setattr("os.makedirs", mock_makedirs)

    def check_provide_contents(dirname):
        environ = dict()
        local_state_file = LocalStateFile.load_for_directory(dirname)
        context = ProvideContext(environ=environ, local_state_file=local_state_file, config={})
        with pytest.raises(IOError) as excinfo:
            context.ensure_work_directory("foo")
        assert "this is not EEXIST" in repr(excinfo.value)

    with_directory_contents(dict(), check_provide_contents)


def test_provide_context_transform_service_run_state():
    def check_provide_contents(dirname):
        environ = dict()
        local_state_file = LocalStateFile.load_for_directory(dirname)
        local_state_file.set_service_run_state("myservice", dict(port=42))
        context = ProvideContext(environ=environ, local_state_file=local_state_file, config={})

        def transform_it(state):
            assert 42 == state['port']
            state['port'] = 43
            state['foo'] = 'bar'
            return 1234

        result = context.transform_service_run_state("myservice", transform_it)
        assert 1234 == result
        assert dict(port=43, foo='bar') == local_state_file.get_service_run_state("myservice")

    with_directory_contents(dict(), check_provide_contents)
