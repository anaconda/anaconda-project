from __future__ import absolute_import

import os
import pytest

from project.internal.local_state_file import LocalStateFile
from project.internal.test.tmpfile_utils import with_directory_contents
from project.plugins.provider import ProvideContext, ProviderRegistry, EnvVarProvider


def test_find_by_env_var():
    registry = ProviderRegistry()
    found = registry.find_by_env_var(requirement=None, env_var="FOO")
    assert 1 == len(found)
    assert isinstance(found[0], EnvVarProvider)


def test_env_var_provider():
    def check_env_var_provider(dirname):
        provider = EnvVarProvider()
        assert "Manually set environment variable" == provider.title
        local_state_file = LocalStateFile.load_for_directory(dirname)
        context = ProvideContext(environ=dict(), local_state_file=local_state_file)
        # just check this doesn't throw or anything, for now
        provider.provide(requirement=None, context=context)

    with_directory_contents(dict(), check_env_var_provider)


def test_fail_to_find_by_service():
    registry = ProviderRegistry()
    found = registry.find_by_service(requirement=None, service="nope")
    assert 0 == len(found)


def test_provide_context_properties():
    def check_provide_contents(dirname):
        environ = dict(foo='bar')
        local_state_file = LocalStateFile.load_for_directory(dirname)
        context = ProvideContext(environ=environ, local_state_file=local_state_file)
        assert dict(foo='bar') == context.environ
        assert [] == context.errors
        context.append_error("foo")
        context.append_error("bar")
        assert ["foo", "bar"] == context.errors

        assert [] == context.logs
        context.append_log("foo")
        context.append_log("bar")
        assert ["foo", "bar"] == context.logs

    with_directory_contents(dict(), check_provide_contents)


def test_provide_context_ensure_work_directory():
    def check_provide_contents(dirname):
        environ = dict()
        local_state_file = LocalStateFile.load_for_directory(dirname)
        context = ProvideContext(environ=environ, local_state_file=local_state_file)
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
        context = ProvideContext(environ=environ, local_state_file=local_state_file)
        with pytest.raises(IOError) as excinfo:
            context.ensure_work_directory("foo")
        assert "this is not EEXIST" in repr(excinfo.value)

    with_directory_contents(dict(), check_provide_contents)


def test_provide_context_transform_service_run_state():
    def check_provide_contents(dirname):
        environ = dict()
        local_state_file = LocalStateFile.load_for_directory(dirname)
        local_state_file.set_service_run_state("myservice", dict(port=42))
        context = ProvideContext(environ=environ, local_state_file=local_state_file)

        def transform_it(state):
            assert 42 == state['port']
            state['port'] = 43
            state['foo'] = 'bar'
            return 1234

        result = context.transform_service_run_state("myservice", transform_it)
        assert 1234 == result
        assert dict(port=43, foo='bar') == local_state_file.get_service_run_state("myservice")

    with_directory_contents(dict(), check_provide_contents)
