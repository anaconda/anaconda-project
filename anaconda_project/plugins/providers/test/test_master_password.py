# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.test.project_utils import project_no_dedicated_env
from anaconda_project.test.environ_utils import minimal_environ
from anaconda_project.prepare import (prepare_without_interaction, unprepare)
from anaconda_project.local_state_file import LocalStateFile
from anaconda_project.plugins.provider import ProvideContext
from anaconda_project.provide import PROVIDE_MODE_DEVELOPMENT
from anaconda_project.plugins.requirement import UserConfigOverrides
from anaconda_project.plugins.registry import PluginRegistry
from anaconda_project.project import Project
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME
from anaconda_project.plugins.requirements.master_password import MasterPasswordRequirement
from anaconda_project.plugins.providers.master_password import MasterPasswordProvider


def test_find_by_class_name():
    registry = PluginRegistry()
    found = registry.find_provider_by_class_name(class_name="MasterPasswordProvider")
    assert found is not None
    assert found.__class__.__name__ == "MasterPasswordProvider"


def _load_master_password_requirement(dirname):
    project = Project(dirname)
    for requirement in project.requirements:
        if isinstance(requirement, MasterPasswordRequirement):
            return requirement
    raise RuntimeError("No requirement for master password was in the project file, only %r" % (project.requirements))


def test_master_password_provider_with_value_not_set():
    def check_not_set(dirname):
        provider = MasterPasswordProvider()
        requirement = _load_master_password_requirement(dirname)
        local_state_file = LocalStateFile.load_for_directory(dirname)
        environ = dict()
        config = provider.read_config(requirement, environ, local_state_file, UserConfigOverrides())
        assert dict() == config
        status = requirement.check_status(environ, local_state_file, UserConfigOverrides())
        html = provider.config_html(requirement, environ, local_state_file, status)
        assert 'type="password"' in html
        context = ProvideContext(environ=dict(),
                                 local_state_file=local_state_file,
                                 status=status,
                                 mode=PROVIDE_MODE_DEVELOPMENT)
        provider.provide(requirement, context=context)
        assert 'ANACONDA_MASTER_PASSWORD' not in context.environ

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  ANACONDA_MASTER_PASSWORD: {}
"""}, check_not_set)


def test_master_password_provider_with_value_set_in_environment():
    def check_set_in_environment(dirname):
        provider = MasterPasswordProvider()
        requirement = _load_master_password_requirement(dirname)
        local_state_file = LocalStateFile.load_for_directory(dirname)
        environ = dict()
        config = provider.read_config(requirement, environ, local_state_file, UserConfigOverrides())
        assert dict() == config
        environ = dict(ANACONDA_MASTER_PASSWORD='from_environ')
        status = requirement.check_status(environ, local_state_file, UserConfigOverrides())
        context = ProvideContext(environ=environ,
                                 local_state_file=local_state_file,
                                 status=status,
                                 mode=PROVIDE_MODE_DEVELOPMENT)
        provider.provide(requirement, context=context)
        assert 'ANACONDA_MASTER_PASSWORD' in context.environ
        assert 'from_environ' == context.environ['ANACONDA_MASTER_PASSWORD']

    # set a default to be sure we prefer 'environ' instead
    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  ANACONDA_MASTER_PASSWORD: { default: 'from_default' }
"""}, check_set_in_environment)


def test_master_password_provider_with_value_set_in_keyring():
    def check_set_in_keyring(dirname):
        from anaconda_project.internal import keyring
        keyring.set('ANACONDA_MASTER_PASSWORD', 'from_keyring')
        try:
            provider = MasterPasswordProvider()
            requirement = _load_master_password_requirement(dirname)
            local_state_file = LocalStateFile.load_for_directory(dirname)
            environ = dict()
            config = provider.read_config(requirement, environ, local_state_file, UserConfigOverrides())
            assert dict(value='from_keyring') == config
            environ = dict(ANACONDA_MASTER_PASSWORD='from_environ')
            status = requirement.check_status(environ, local_state_file, UserConfigOverrides())
            context = ProvideContext(environ=environ,
                                     local_state_file=local_state_file,
                                     status=status,
                                     mode=PROVIDE_MODE_DEVELOPMENT)
            provider.provide(requirement, context=context)
            assert 'ANACONDA_MASTER_PASSWORD' in context.environ
            assert 'from_keyring' == context.environ['ANACONDA_MASTER_PASSWORD']
        finally:
            keyring.set('ANACONDA_MASTER_PASSWORD', None)

    # set a default to be sure we prefer keyring
    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  ANACONDA_MASTER_PASSWORD: { default: 'from_default' }
"""}, check_set_in_keyring)


def test_master_password_provider_with_value_set_in_default():
    def check_set_in_default(dirname):
        provider = MasterPasswordProvider()
        requirement = _load_master_password_requirement(dirname)
        local_state_file = LocalStateFile.load_for_directory(dirname)
        environ = dict()
        config = provider.read_config(requirement, environ, local_state_file, UserConfigOverrides())
        assert dict() == config
        environ = dict()
        status = requirement.check_status(environ, local_state_file, UserConfigOverrides())
        context = ProvideContext(environ=environ,
                                 local_state_file=local_state_file,
                                 status=status,
                                 mode=PROVIDE_MODE_DEVELOPMENT)
        provider.provide(requirement, context=context)
        assert 'ANACONDA_MASTER_PASSWORD' in context.environ
        assert 'from_default' == context.environ['ANACONDA_MASTER_PASSWORD']

    # set a default to be sure we prefer keyring
    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  ANACONDA_MASTER_PASSWORD: { default: 'from_default' }
"""}, check_set_in_default)


def test_master_password_provider_saves_config_in_keyring():
    def check_configure_via_keyring(dirname):
        from anaconda_project.internal import keyring
        try:
            provider = MasterPasswordProvider()
            requirement = _load_master_password_requirement(dirname)
            local_state_file = LocalStateFile.load_for_directory(dirname)
            environ = dict()
            config = provider.read_config(requirement, environ, local_state_file, UserConfigOverrides())
            assert dict() == config
            provider.set_config_values_as_strings(requirement,
                                                  environ,
                                                  local_state_file,
                                                  UserConfigOverrides(),
                                                  dict(value='from_config'))
            assert keyring.get('ANACONDA_MASTER_PASSWORD') == 'from_config'
            environ = dict()
            status = requirement.check_status(environ, local_state_file, UserConfigOverrides())
            context = ProvideContext(environ=environ,
                                     local_state_file=local_state_file,
                                     status=status,
                                     mode=PROVIDE_MODE_DEVELOPMENT)
            provider.provide(requirement, context=context)
            assert 'ANACONDA_MASTER_PASSWORD' in context.environ
            assert 'from_config' == context.environ['ANACONDA_MASTER_PASSWORD']
        finally:
            keyring.set('ANACONDA_MASTER_PASSWORD', None)

    # set a default to be sure we prefer keyring we configure
    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  ANACONDA_MASTER_PASSWORD: { default: 'from_default' }
"""}, check_configure_via_keyring)


def test_master_password_provider_prepare_and_unprepare():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        result = prepare_without_interaction(project,
                                             environ=minimal_environ(PROJECT_DIR=dirname,
                                                                     ANACONDA_MASTER_PASSWORD='from_environ'))
        assert 'ANACONDA_MASTER_PASSWORD' in result.environ
        assert 'from_environ' == result.environ['ANACONDA_MASTER_PASSWORD']

        status = unprepare(project, result)
        assert status
        assert status.status_description == 'Success.'
        assert status.logs == ['Nothing to clean up for master password.', 'Not cleaning up environments.']

    # set a default to be sure we prefer 'environ' instead
    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  ANACONDA_MASTER_PASSWORD: { default: 'from_default' }
"""}, check)
