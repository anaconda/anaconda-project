from __future__ import absolute_import

import os

import project.internal.conda_api as conda_api
from project.internal.test.tmpfile_utils import with_directory_contents
from project.prepare import prepare
from project.project import Project
from project.project_file import PROJECT_FILENAME
from project.plugins.provider import ProviderRegistry
from project.plugins.providers.conda_env import ProjectScopedCondaEnvProvider


def test_find_by_class_name_conda_env():
    registry = ProviderRegistry()
    found = registry.find_by_class_name(class_name="ProjectScopedCondaEnvProvider")
    assert found is not None
    assert isinstance(found, ProjectScopedCondaEnvProvider)
    assert "Conda environment inside the project directory" == found.title


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
                    PATH=expected_new_path) == environ
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
                    PATH=expected_new_path) == environ
        assert conda_meta_mtime == os.path.getmtime(os.path.join(expected_env, "conda-meta"))

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  CONDA_DEFAULT_ENV: {}
"""}, prepare_project_scoped_env)


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
        assert dict(CONDA_DEFAULT_ENV='root', PROJECT_DIR=project.directory_path) == environ

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

        prefix = environ['CONDA_DEFAULT_ENV']
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

        prefix = environ['CONDA_DEFAULT_ENV']
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
