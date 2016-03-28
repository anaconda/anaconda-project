from __future__ import absolute_import, print_function

from project.internal.test.tmpfile_utils import with_directory_contents
from project.local_state_file import LocalStateFile
from project.plugins.provider import ProvideContext
from project.plugins.registry import PluginRegistry
from project.project import Project
from project.project_file import DEFAULT_PROJECT_FILENAME
from project.plugins.requirements.master_password import MasterPasswordRequirement
from project.plugins.providers.master_password import MasterPasswordProvider


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
        config = provider.read_config(requirement, environ, local_state_file)
        assert dict() == config
        status = requirement.check_status(environ, local_state_file)
        html = provider.config_html(requirement, environ, local_state_file, status)
        assert 'type="password"' in html
        context = ProvideContext(environ=dict(), local_state_file=local_state_file, status=status)
        provider.provide(requirement, context=context)
        assert 'ANACONDA_MASTER_PASSWORD' not in context.environ

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
runtime:
  ANACONDA_MASTER_PASSWORD: {}
"""}, check_not_set)


def test_master_password_provider_with_value_set_in_environment():
    def check_set_in_environment(dirname):
        provider = MasterPasswordProvider()
        requirement = _load_master_password_requirement(dirname)
        local_state_file = LocalStateFile.load_for_directory(dirname)
        environ = dict()
        config = provider.read_config(requirement, environ, local_state_file)
        assert dict() == config
        environ = dict(ANACONDA_MASTER_PASSWORD='from_environ')
        status = requirement.check_status(environ, local_state_file)
        context = ProvideContext(environ=environ, local_state_file=local_state_file, status=status)
        provider.provide(requirement, context=context)
        assert 'ANACONDA_MASTER_PASSWORD' in context.environ
        assert 'from_environ' == context.environ['ANACONDA_MASTER_PASSWORD']

    # set a default to be sure we prefer 'environ' instead
    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
runtime:
  ANACONDA_MASTER_PASSWORD: { default: 'from_default' }
"""}, check_set_in_environment)


def test_master_password_provider_with_value_set_in_keyring():
    def check_set_in_keyring(dirname):
        from project.internal import keyring
        keyring.set('ANACONDA_MASTER_PASSWORD', 'from_keyring')
        try:
            provider = MasterPasswordProvider()
            requirement = _load_master_password_requirement(dirname)
            local_state_file = LocalStateFile.load_for_directory(dirname)
            environ = dict()
            config = provider.read_config(requirement, environ, local_state_file)
            assert dict(value='from_keyring') == config
            environ = dict(ANACONDA_MASTER_PASSWORD='from_environ')
            status = requirement.check_status(environ, local_state_file)
            context = ProvideContext(environ=environ, local_state_file=local_state_file, status=status)
            provider.provide(requirement, context=context)
            assert 'ANACONDA_MASTER_PASSWORD' in context.environ
            assert 'from_keyring' == context.environ['ANACONDA_MASTER_PASSWORD']
        finally:
            keyring.set('ANACONDA_MASTER_PASSWORD', None)

    # set a default to be sure we prefer keyring
    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
runtime:
  ANACONDA_MASTER_PASSWORD: { default: 'from_default' }
"""}, check_set_in_keyring)


def test_master_password_provider_with_value_set_in_default():
    def check_set_in_default(dirname):
        provider = MasterPasswordProvider()
        requirement = _load_master_password_requirement(dirname)
        local_state_file = LocalStateFile.load_for_directory(dirname)
        environ = dict()
        config = provider.read_config(requirement, environ, local_state_file)
        assert dict() == config
        environ = dict()
        status = requirement.check_status(environ, local_state_file)
        context = ProvideContext(environ=environ, local_state_file=local_state_file, status=status)
        provider.provide(requirement, context=context)
        assert 'ANACONDA_MASTER_PASSWORD' in context.environ
        assert 'from_default' == context.environ['ANACONDA_MASTER_PASSWORD']

    # set a default to be sure we prefer keyring
    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
runtime:
  ANACONDA_MASTER_PASSWORD: { default: 'from_default' }
"""}, check_set_in_default)


def test_master_password_provider_with_list_set_in_default():
    def check_list_set_in_default(dirname):
        provider = MasterPasswordProvider()
        requirement = _load_master_password_requirement(dirname)
        local_state_file = LocalStateFile.load_for_directory(dirname)
        environ = dict()
        config = provider.read_config(requirement, environ, local_state_file)
        assert dict() == config
        environ = dict()
        status = requirement.check_status(environ, local_state_file)
        context = ProvideContext(environ=environ, local_state_file=local_state_file, status=status)
        provider.provide(requirement, context=context)
        assert 'ANACONDA_MASTER_PASSWORD' not in context.environ
        assert ["Value of 'ANACONDA_MASTER_PASSWORD' should be a string not []"] == context.errors

    # set a default to be sure we prefer keyring
    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
runtime:
  ANACONDA_MASTER_PASSWORD: { default: [] }
"""}, check_list_set_in_default)


def test_master_password_provider_saves_config_in_keyring():
    def check_configure_via_keyring(dirname):
        from project.internal import keyring
        try:
            provider = MasterPasswordProvider()
            requirement = _load_master_password_requirement(dirname)
            local_state_file = LocalStateFile.load_for_directory(dirname)
            environ = dict()
            config = provider.read_config(requirement, environ, local_state_file)
            assert dict() == config
            provider.set_config_values_as_strings(requirement, environ, local_state_file, dict(value='from_config'))
            assert keyring.get('ANACONDA_MASTER_PASSWORD') == 'from_config'
            environ = dict()
            status = requirement.check_status(environ, local_state_file)
            context = ProvideContext(environ=environ, local_state_file=local_state_file, status=status)
            provider.provide(requirement, context=context)
            assert 'ANACONDA_MASTER_PASSWORD' in context.environ
            assert 'from_config' == context.environ['ANACONDA_MASTER_PASSWORD']
        finally:
            keyring.set('ANACONDA_MASTER_PASSWORD', None)

    # set a default to be sure we prefer keyring we configure
    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
runtime:
  ANACONDA_MASTER_PASSWORD: { default: 'from_default' }
"""}, check_configure_via_keyring)
