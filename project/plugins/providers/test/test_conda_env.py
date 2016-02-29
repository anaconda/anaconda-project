from __future__ import absolute_import

import os

import project.internal.conda_api as conda_api
from project.internal.test.tmpfile_utils import with_directory_contents
from project.prepare import prepare
from project.project import Project
from project.project_file import PROJECT_FILENAME
from project.local_state_file import LOCAL_STATE_DIRECTORY, LOCAL_STATE_FILENAME, LocalStateFile
from project.plugins.registry import PluginRegistry
from project.plugins.provider import ProviderConfigContext
from project.plugins.providers.conda_env import ProjectScopedCondaEnvProvider
from project.plugins.requirements.conda_env import CondaEnvRequirement


def test_find_by_class_name_conda_env():
    registry = PluginRegistry()
    found = registry.find_provider_by_class_name(class_name="ProjectScopedCondaEnvProvider")
    assert found is not None
    assert isinstance(found, ProjectScopedCondaEnvProvider)


def test_prepare_project_scoped_env():
    def prepare_project_scoped_env(dirname):
        project = Project(dirname)
        fake_old_path = "foo" + os.pathsep + "bar"
        environ = dict(PROJECT_DIR=dirname, PATH=fake_old_path)
        result = prepare(project, environ=environ)
        assert result
        expected_env = os.path.join(dirname, ".envs/default")
        expected_new_path = os.path.join(expected_env, "bin") + os.pathsep + "foo" + os.pathsep + "bar"
        assert dict(CONDA_DEFAULT_ENV=expected_env,
                    PROJECT_DIR=project.directory_path,
                    PATH=expected_new_path) == result.environ
        assert os.path.exists(os.path.join(expected_env, "conda-meta"))
        conda_meta_mtime = os.path.getmtime(os.path.join(expected_env, "conda-meta"))

        # bare minimum default env shouldn't include these
        # (contrast with the test later where we list them in
        # requirements)
        installed = conda_api.installed(expected_env)
        assert 'ipython' not in installed
        assert 'numpy' not in installed

        # Prepare it again should no-op (use the already-existing environment)
        environ = dict(PROJECT_DIR=dirname, PATH=fake_old_path)
        result = prepare(project, environ=environ)
        assert result
        assert dict(CONDA_DEFAULT_ENV=expected_env,
                    PROJECT_DIR=project.directory_path,
                    PATH=expected_new_path) == result.environ
        assert conda_meta_mtime == os.path.getmtime(os.path.join(expected_env, "conda-meta"))

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  CONDA_DEFAULT_ENV: {}
"""}, prepare_project_scoped_env)


def test_reading_autocreate_config():
    def read_config(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        requirement = CondaEnvRequirement(registry=PluginRegistry())
        provider = ProjectScopedCondaEnvProvider()
        config = provider.read_config(ProviderConfigContext(dict(), local_state, requirement))
        assert config['autocreate'] is True

    with_directory_contents(
        {
            LOCAL_STATE_DIRECTORY + "/" + LOCAL_STATE_FILENAME: """
runtime:
  CONDA_DEFAULT_ENV:
    providers:
      ProjectScopedCondaEnvProvider:
        autocreate: true
         """
        }, read_config)


def test_setting_autocreate_config():
    def check_set_config(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        requirement = CondaEnvRequirement(registry=PluginRegistry())
        provider = ProjectScopedCondaEnvProvider()
        context = ProviderConfigContext(dict(), local_state, requirement)
        config = provider.read_config(context)
        assert config['autocreate'] is True
        provider.set_config_values_as_strings(context, dict(autocreate='False'))
        config = provider.read_config(context)
        assert config['autocreate'] is False
        provider.set_config_values_as_strings(context, dict(autocreate='True'))
        config = provider.read_config(context)
        assert config['autocreate'] is True

    with_directory_contents({}, check_set_config)


def test_config_html():
    def check_config_html(dirname):
        requirement = CondaEnvRequirement(registry=PluginRegistry())
        provider = ProjectScopedCondaEnvProvider()
        status = requirement.check_status(dict())
        html = provider.config_html(status)
        assert "Autocreate an environment" in html
        status._has_been_provided = True
        html = provider.config_html(status)
        assert html is None

    with_directory_contents({}, check_config_html)


def test_prepare_no_op_if_autocreate_disabled(capsys):
    def prepare_does_nothing_with_autocreate_false(dirname):
        project = Project(dirname)
        fake_old_path = "foo" + os.pathsep + "bar"
        environ = dict(PROJECT_DIR=dirname, PATH=fake_old_path)
        result = prepare(project, environ=environ)
        assert not result
        expected_env = os.path.join(dirname, ".envs/default")
        assert not os.path.exists(os.path.join(expected_env, "conda-meta"))

        out, err = capsys.readouterr()
        assert out == "Not trying to create a Conda environment.\n"
        assert err == ("missing requirement to run this project: A Conda environment inside the project directory\n" +
                       "  A Conda environment hasn't been activated for this project (CONDA_DEFAULT_ENV is unset).\n")

    with_directory_contents(
        {PROJECT_FILENAME: """
runtime:
  CONDA_DEFAULT_ENV: {}
    """,
         LOCAL_STATE_DIRECTORY + "/" + LOCAL_STATE_FILENAME: """
runtime:
  CONDA_DEFAULT_ENV:
    providers:
      ProjectScopedCondaEnvProvider:
        autocreate: false
         """}, prepare_does_nothing_with_autocreate_false)


def test_prepare_project_scoped_env_conda_create_fails(monkeypatch):
    def mock_create(prefix, pkgs):
        raise conda_api.CondaError("error_from_conda_create")

    monkeypatch.setattr('project.internal.conda_api.create', mock_create)

    def prepare_project_scoped_env(dirname):
        project = Project(dirname)
        environ = dict(PROJECT_DIR=dirname)
        result = prepare(project, environ=environ)
        assert not result

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  CONDA_DEFAULT_ENV: {}
"""}, prepare_project_scoped_env)


def test_prepare_in_root_env():
    def prepare_in_root_env(dirname):
        project = Project(dirname)
        environ = dict(PROJECT_DIR=dirname, CONDA_DEFAULT_ENV='root')
        result = prepare(project, environ=environ)
        assert result
        assert dict(CONDA_DEFAULT_ENV='root', PROJECT_DIR=project.directory_path) == result.environ

    with_directory_contents(
        {PROJECT_FILENAME: """
runtime:
    CONDA_DEFAULT_ENV: { project_scoped: false }
"""}, prepare_in_root_env)


def test_prepare_project_scoped_env_with_packages():
    def prepare_project_scoped_env(dirname):
        project = Project(dirname)
        environ = dict(PROJECT_DIR=dirname)
        result = prepare(project, environ=environ)
        assert result

        prefix = result.environ['CONDA_DEFAULT_ENV']
        installed = conda_api.installed(prefix)

        assert 'ipython' in installed
        assert 'numpy' in installed
        assert 'ipython-notebook' not in installed

        # Preparing it again with new packages added should add those
        reqs = project.project_file.requirements_run
        project.project_file.set_value(['requirements', 'run'], reqs + ['ipython-notebook'])
        project.project_file.save()
        environ = dict(PROJECT_DIR=dirname)
        result = prepare(project, environ=environ)
        assert result

        prefix = result.environ['CONDA_DEFAULT_ENV']
        installed = conda_api.installed(prefix)

        assert 'ipython' in installed
        assert 'numpy' in installed
        assert 'ipython-notebook' in installed

        # Preparing it again with a bogus package should fail
        reqs = project.project_file.requirements_run
        project.project_file.set_value(['requirements', 'run'], reqs + ['boguspackage'])
        project.project_file.save()
        environ = dict(PROJECT_DIR=dirname)
        result = prepare(project, environ=environ)
        assert not result

    with_directory_contents(
        {PROJECT_FILENAME: """
requirements:
  run:
    - ipython
    - numpy
"""}, prepare_project_scoped_env)
