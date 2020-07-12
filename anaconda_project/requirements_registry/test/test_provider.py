# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import

import os

import pytest

from anaconda_project.internal.test.tmpfile_utils import (with_directory_contents, tmp_script_commandline,
                                                          with_directory_contents_completing_project_file)
from anaconda_project.local_state_file import LocalStateFile, DEFAULT_LOCAL_STATE_FILENAME
from anaconda_project.requirements_registry.provider import (Provider, ProvideContext, EnvVarProvider, ProvideResult,
                                                             shutdown_service_run_state)
from anaconda_project.requirements_registry.registry import RequirementsRegistry
from anaconda_project.requirements_registry.requirement import EnvVarRequirement, UserConfigOverrides
from anaconda_project.project import Project
from anaconda_project.provide import PROVIDE_MODE_DEVELOPMENT
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME
from anaconda_project.prepare import (prepare_without_interaction, unprepare)
from anaconda_project.frontend import NullFrontend
from anaconda_project.test.project_utils import project_no_dedicated_env
from anaconda_project.test.environ_utils import minimal_environ
from anaconda_project.internal import (keyring, conda_api)

conda_env_var = conda_api.conda_prefix_variable()


def test_find_provider_by_class_name():
    registry = RequirementsRegistry()
    found = registry.find_provider_by_class_name(class_name="CondaEnvProvider")
    assert found is not None
    assert found.__class__.__name__ == "CondaEnvProvider"


def test_find_provider_by_class_name_not_found():
    registry = RequirementsRegistry()
    with pytest.raises(ValueError):
        registry.find_provider_by_class_name(class_name="NotAThing")


def test_provider_default_method_implementations():
    class UselessProvider(Provider):
        @property
        def title(self):
            return ""

        def read_config(self, requirement, environ, local_state_file, default_env_spec_name, overrides):
            return dict()

        def provide(self, requirement, context):
            pass

        def unprovide(self, requirement, local_state_file, requirement_status=None):
            pass

        def missing_env_vars_to_configure(self, requirement, environ, local_state_file):
            return ()

        def missing_env_vars_to_provide(self, requirement, environ, local_state_file):
            return ()

    provider = UselessProvider()
    # this method is supposed to do nothing by default (ignore
    # unknown names, in particular)
    provider.set_config_values_as_strings(requirement=None,
                                          environ=None,
                                          local_state_file=None,
                                          default_env_spec_name='default',
                                          overrides=None,
                                          values=dict())


def _load_env_var_requirement(dirname, env_var):
    project = Project(dirname)

    for requirement in project.requirements(project.default_env_spec_name):
        if isinstance(requirement, EnvVarRequirement) and requirement.env_var == env_var:
            return requirement
    assert [] == project.problems
    raise RuntimeError("No requirement for %s was in the project file, only %r" % (env_var, project.requirements))


def test_env_var_provider_with_no_value():
    def check_env_var_provider(dirname):
        provider = EnvVarProvider()
        requirement = _load_env_var_requirement(dirname, "FOO")
        local_state_file = LocalStateFile.load_for_directory(dirname)
        status = requirement.check_status(dict(), local_state_file, 'default', UserConfigOverrides())
        context = ProvideContext(environ=dict(),
                                 local_state_file=local_state_file,
                                 default_env_spec_name='default',
                                 status=status,
                                 mode=PROVIDE_MODE_DEVELOPMENT,
                                 frontend=NullFrontend())

        provider.provide(requirement, context=context)
        assert 'FOO' not in context.environ

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
variables:
  - FOO
"""}, check_env_var_provider)


def test_env_var_provider_with_default_value_in_project_file():
    def check_env_var_provider(dirname):
        provider = EnvVarProvider()
        requirement = _load_env_var_requirement(dirname, "FOO")
        assert dict(default='from_default') == requirement.options
        local_state_file = LocalStateFile.load_for_directory(dirname)
        status = requirement.check_status(dict(), local_state_file, 'default', UserConfigOverrides())
        context = ProvideContext(environ=dict(),
                                 local_state_file=local_state_file,
                                 default_env_spec_name='default',
                                 status=status,
                                 mode=PROVIDE_MODE_DEVELOPMENT,
                                 frontend=NullFrontend())
        result = provider.provide(requirement, context=context)
        assert [] == result.errors
        assert 'FOO' in context.environ
        assert 'from_default' == context.environ['FOO']

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  FOO:
    default: from_default
"""}, check_env_var_provider)


def test_env_var_provider_with_unencrypted_default_value_in_project_file_for_encrypted_requirement():
    # the idea here is that if you want to put an unencrypted
    # password in the file, we aren't going to be annoying and
    # stop you.
    def check_env_var_provider(dirname):
        provider = EnvVarProvider()
        requirement = _load_env_var_requirement(dirname, "FOO_SECRET")
        assert requirement.encrypted
        assert dict(default='from_default') == requirement.options
        local_state_file = LocalStateFile.load_for_directory(dirname)
        environ = dict()
        status = requirement.check_status(environ, local_state_file, 'default', UserConfigOverrides())
        context = ProvideContext(environ=environ,
                                 local_state_file=local_state_file,
                                 default_env_spec_name='default',
                                 status=status,
                                 mode=PROVIDE_MODE_DEVELOPMENT,
                                 frontend=NullFrontend())
        result = provider.provide(requirement, context=context)
        assert [] == result.errors
        assert 'FOO_SECRET' in context.environ
        assert 'from_default' == context.environ['FOO_SECRET']

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  FOO_SECRET:
    default: from_default
"""}, check_env_var_provider)


def test_env_var_provider_with_value_set_in_environment():
    def check_env_var_provider(dirname):
        provider = EnvVarProvider()
        requirement = _load_env_var_requirement(dirname, "FOO")
        local_state_file = LocalStateFile.load_for_directory(dirname)
        environ = dict(FOO='from_environ')
        status = requirement.check_status(environ, local_state_file, 'default', UserConfigOverrides())
        assert dict(source='environ', value='from_environ') == status.analysis.config
        context = ProvideContext(environ=environ,
                                 local_state_file=local_state_file,
                                 default_env_spec_name='default',
                                 status=status,
                                 mode=PROVIDE_MODE_DEVELOPMENT,
                                 frontend=NullFrontend())
        result = provider.provide(requirement, context=context)
        assert [] == result.errors
        assert 'FOO' in context.environ
        assert 'from_environ' == context.environ['FOO']

    # set a default to be sure we prefer 'environ' instead
    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  FOO:
    default: from_default
"""}, check_env_var_provider)


def test_env_var_provider_with_value_set_in_local_state():
    def check_env_var_provider(dirname):
        provider = EnvVarProvider()
        requirement = _load_env_var_requirement(dirname, "FOO")
        local_state_file = LocalStateFile.load_for_directory(dirname)
        # set in environ to be sure we override it with local state
        environ = dict(FOO='from_environ')
        status = requirement.check_status(environ, local_state_file, 'default', UserConfigOverrides())
        assert dict(value="from_local_state", source="variables") == status.analysis.config
        context = ProvideContext(environ=environ,
                                 local_state_file=local_state_file,
                                 default_env_spec_name='default',
                                 status=status,
                                 mode=PROVIDE_MODE_DEVELOPMENT,
                                 frontend=NullFrontend())
        result = provider.provide(requirement, context=context)
        assert [] == result.errors
        assert 'FOO' in context.environ
        assert 'from_local_state' == context.environ['FOO']

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
variables:
  FOO:
    default: from_default
    """,
            DEFAULT_LOCAL_STATE_FILENAME: """
variables:
  FOO: from_local_state
"""
        }, check_env_var_provider)


def test_env_var_provider_with_encrypted_value_set_in_local_state():
    def check_env_var_provider(dirname):
        provider = EnvVarProvider()
        requirement = _load_env_var_requirement(dirname, "FOO_PASSWORD")
        assert requirement.encrypted
        local_state_file = LocalStateFile.load_for_directory(dirname)
        # set in environ to be sure we override it with local state
        environ = dict(FOO_PASSWORD='from_environ')
        status = requirement.check_status(environ, local_state_file, 'default', UserConfigOverrides())
        assert dict(value="from_local_state", source="variables") == status.analysis.config
        context = ProvideContext(environ=environ,
                                 local_state_file=local_state_file,
                                 default_env_spec_name='default',
                                 status=status,
                                 mode=PROVIDE_MODE_DEVELOPMENT,
                                 frontend=NullFrontend())
        result = provider.provide(requirement, context=context)
        assert [] == result.errors
        assert 'FOO_PASSWORD' in context.environ
        assert 'from_local_state' == context.environ['FOO_PASSWORD']

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
variables:
  FOO_PASSWORD:
    default: from_default
    """,
            DEFAULT_LOCAL_STATE_FILENAME: """
variables:
  FOO_PASSWORD: from_local_state
"""
        }, check_env_var_provider)


def test_env_var_provider_configure_local_state_value():
    def check_env_var_provider_config_local_state(dirname):
        provider = EnvVarProvider()
        requirement = _load_env_var_requirement(dirname, "FOO")
        local_state_file = LocalStateFile.load_for_directory(dirname)
        status = requirement.check_status(dict(), local_state_file, 'default', UserConfigOverrides())
        assert dict(source='unset') == status.analysis.config

        assert local_state_file.get_value(['variables', 'FOO']) is None

        environ = dict()

        provider.set_config_values_as_strings(requirement, environ, local_state_file, 'default', UserConfigOverrides(),
                                              dict(value="bar"))

        assert local_state_file.get_value(['variables', 'FOO']) == "bar"
        local_state_file.save()

        local_state_file_2 = LocalStateFile.load_for_directory(dirname)
        assert local_state_file_2.get_value(['variables', 'FOO']) == "bar"

        # setting empty string = unset
        provider.set_config_values_as_strings(requirement, environ, local_state_file, 'default', UserConfigOverrides(),
                                              dict(value=""))
        assert local_state_file.get_value(['variables', 'FOO']) is None

        local_state_file.save()

        local_state_file_3 = LocalStateFile.load_for_directory(dirname)
        assert local_state_file_3.get_value(['variables', 'FOO']) is None

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
variables:
  - FOO
"""}, check_env_var_provider_config_local_state)


def test_env_var_provider_configure_encrypted_value():
    def check_env_var_provider_config_local_state(dirname):
        provider = EnvVarProvider()
        requirement = _load_env_var_requirement(dirname, "FOO_PASSWORD")
        assert requirement.encrypted
        local_state_file = LocalStateFile.load_for_directory(dirname)
        status = requirement.check_status(dict(), local_state_file, 'default', UserConfigOverrides())
        assert dict(source='unset') == status.analysis.config

        assert local_state_file.get_value(['variables', 'FOO_PASSWORD']) is None
        assert set(keyring.fallback_data().values()) == set()

        environ = dict(CONDA_DEFAULT_ENV='/pretend/env', CONDA_ENV_PATH='/pretend/env', CONDA_PREFIX='/pretend/env')

        provider.set_config_values_as_strings(requirement, environ, local_state_file, 'default', UserConfigOverrides(),
                                              dict(value="bar"))

        # should not have affected local state, should use keyring
        assert local_state_file.get_value(['variables', 'FOO_PASSWORD']) is None
        assert set(keyring.fallback_data().values()) == set(["bar"])

        # setting empty string = unset
        provider.set_config_values_as_strings(requirement, environ, local_state_file, 'default', UserConfigOverrides(),
                                              dict(value=""))
        assert local_state_file.get_value(['variables', 'FOO_PASSWORD']) is None
        assert set(keyring.fallback_data().values()) == set()

    keyring.enable_fallback_keyring()
    try:
        with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
variables:
  - FOO_PASSWORD
"""}, check_env_var_provider_config_local_state)
    finally:
        keyring.disable_fallback_keyring()


def test_env_var_provider_configure_disabled_local_state_value():
    def check_env_var_provider_config_disabled_local_state(dirname):
        provider = EnvVarProvider()
        requirement = _load_env_var_requirement(dirname, "FOO")
        local_state_file = LocalStateFile.load_for_directory(dirname)
        status = requirement.check_status(dict(), local_state_file, 'default', UserConfigOverrides())
        assert dict(source='unset') == status.analysis.config

        assert local_state_file.get_value(['variables', 'FOO']) is None
        assert local_state_file.get_value(['disabled_variables', 'FOO']) is None

        environ = dict()

        # source=environ should mean we set disabled_variables instead of variables
        provider.set_config_values_as_strings(requirement, environ, local_state_file, 'default', UserConfigOverrides(),
                                              dict(source='environ', value="bar"))

        assert local_state_file.get_value(['variables', 'FOO']) is None
        assert local_state_file.get_value(['disabled_variables', 'FOO']) == "bar"

        config = provider.read_config(requirement, environ, local_state_file, 'default', UserConfigOverrides())
        assert config == dict(source='unset', value='bar')

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
variables:
  - FOO
"""}, check_env_var_provider_config_disabled_local_state)


def test_env_var_provider_prepare_unprepare():
    def check_env_var_provider_prepare(dirname):
        project = project_no_dedicated_env(dirname)
        result = prepare_without_interaction(project, environ=minimal_environ(FOO='bar'))
        assert result
        status = unprepare(project, result)
        assert status
        assert status.status_description == 'Success.'
        assert project.frontend.logs == [
            "Nothing to clean up for FOO.", ("Current environment is not in %s, no need to delete it." % dirname)
        ]

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: null
"""}, check_env_var_provider_prepare)


def test_provide_context_properties():
    def check_provide_contents(dirname):
        environ = dict(foo='bar')
        local_state_file = LocalStateFile.load_for_directory(dirname)
        requirement = EnvVarRequirement(RequirementsRegistry(), env_var="FOO")
        status = requirement.check_status(environ, local_state_file, 'default', UserConfigOverrides())
        context = ProvideContext(environ=environ,
                                 local_state_file=local_state_file,
                                 default_env_spec_name='default',
                                 status=status,
                                 mode=PROVIDE_MODE_DEVELOPMENT,
                                 frontend=NullFrontend())
        assert dict(foo='bar') == context.environ
        assert context.status is status

    with_directory_contents(dict(), check_provide_contents)


def test_provide_result_properties():
    empty = ProvideResult.empty()
    assert [] == empty.errors

    full = ProvideResult(['c', 'd'])
    assert ['c', 'd'] == full.errors

    unchanged = full.copy_with_additions()
    assert ['c', 'd'] == unchanged.errors

    unchanged2 = full.copy_with_additions([])
    assert ['c', 'd'] == unchanged2.errors

    extended = full.copy_with_additions(['z'])
    assert ['c', 'd', 'z'] == extended.errors


def test_provide_context_ensure_service_directory():
    def check_provide_contents(dirname):
        environ = dict()
        local_state_file = LocalStateFile.load_for_directory(dirname)
        requirement = EnvVarRequirement(RequirementsRegistry(), env_var="FOO")
        status = requirement.check_status(environ, local_state_file, 'default', UserConfigOverrides())
        context = ProvideContext(environ=environ,
                                 local_state_file=local_state_file,
                                 default_env_spec_name='default',
                                 status=status,
                                 mode=PROVIDE_MODE_DEVELOPMENT,
                                 frontend=NullFrontend())
        workpath = context.ensure_service_directory("foo")
        assert os.path.isdir(workpath)
        assert workpath.endswith("foo")
        parent = os.path.dirname(workpath)
        assert parent.endswith("services")
        parent = os.path.dirname(parent)
        assert parent == dirname

        # be sure we can create if it already exists
        workpath2 = context.ensure_service_directory("foo")
        assert os.path.isdir(workpath2)
        assert workpath == workpath2

    with_directory_contents(dict(), check_provide_contents)


def test_provide_context_ensure_service_directory_cannot_create(monkeypatch):
    def mock_makedirs(path, mode=0):
        raise IOError("this is not EEXIST")

    monkeypatch.setattr("os.makedirs", mock_makedirs)

    def check_provide_contents(dirname):
        environ = dict()
        local_state_file = LocalStateFile.load_for_directory(dirname)
        requirement = EnvVarRequirement(RequirementsRegistry(), env_var="FOO")
        status = requirement.check_status(environ, local_state_file, 'default', UserConfigOverrides())
        context = ProvideContext(environ=environ,
                                 local_state_file=local_state_file,
                                 default_env_spec_name='default',
                                 status=status,
                                 mode=PROVIDE_MODE_DEVELOPMENT,
                                 frontend=NullFrontend())
        with pytest.raises(IOError) as excinfo:
            context.ensure_service_directory("foo")
        assert "this is not EEXIST" in repr(excinfo.value)

    with_directory_contents(dict(), check_provide_contents)


def test_provide_context_transform_service_run_state():
    def check_provide_contents(dirname):
        environ = dict()
        local_state_file = LocalStateFile.load_for_directory(dirname)
        local_state_file.set_service_run_state("myservice", dict(port=42))
        requirement = EnvVarRequirement(RequirementsRegistry(), env_var="FOO")
        status = requirement.check_status(environ, local_state_file, 'default', UserConfigOverrides())
        context = ProvideContext(environ=environ,
                                 local_state_file=local_state_file,
                                 default_env_spec_name='default',
                                 status=status,
                                 mode=PROVIDE_MODE_DEVELOPMENT,
                                 frontend=NullFrontend())

        def transform_it(state):
            assert 42 == state['port']
            state['port'] = 43
            state['foo'] = 'bar'
            return 1234

        result = context.transform_service_run_state("myservice", transform_it)
        assert 1234 == result
        assert dict(port=43, foo='bar') == local_state_file.get_service_run_state("myservice")

    with_directory_contents(dict(), check_provide_contents)


def test_shutdown_service_run_state_nothing_to_do():
    def check(dirname):
        local_state_file = LocalStateFile.load_for_directory(dirname)
        status = shutdown_service_run_state(local_state_file, 'foo')
        assert status
        assert status.status_description == 'Nothing to do to shut down foo.'

    with_directory_contents(dict(), check)


def test_shutdown_service_run_state_command_success():
    def check(dirname):
        local_state_file = LocalStateFile.load_for_directory(dirname)
        true_commandline = tmp_script_commandline("""import sys
sys.exit(0)
""")
        local_state_file.set_service_run_state('FOO', {'shutdown_commands': [true_commandline]})
        status = shutdown_service_run_state(local_state_file, 'FOO')
        assert status
        assert status.status_description == "Successfully shut down FOO."

    with_directory_contents(dict(), check)


def test_shutdown_service_run_state_command_failure():
    def check(dirname):
        local_state_file = LocalStateFile.load_for_directory(dirname)
        false_commandline = tmp_script_commandline("""import sys
sys.exit(1)
""")
        local_state_file.set_service_run_state('FOO', {'shutdown_commands': [false_commandline]})
        status = shutdown_service_run_state(local_state_file, 'FOO')
        assert not status
        assert status.status_description == "Shutdown commands failed for FOO."
        assert status.errors == ["Shutting down FOO, command %r failed with code 1." % false_commandline]

    with_directory_contents(dict(), check)
