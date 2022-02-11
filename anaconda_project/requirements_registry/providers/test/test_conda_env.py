# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import

import os
import platform
import pytest
import stat
from contextlib import contextmanager
try:
    from backports.tempfile import TemporaryDirectory
except ImportError:
    from tempfile import TemporaryDirectory

import anaconda_project.internal.conda_api as conda_api
import anaconda_project.internal.pip_api as pip_api
from anaconda_project.test.environ_utils import minimal_environ
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents_completing_project_file
from anaconda_project.internal.test.test_conda_api import monkeypatch_conda_not_to_use_links
from anaconda_project.prepare import (prepare_without_interaction, prepare_in_stages, unprepare)
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME
from anaconda_project.project import Project
from anaconda_project import provide
from anaconda_project.requirements_registry.registry import RequirementsRegistry
from anaconda_project.requirements_registry.providers.conda_env import CondaEnvProvider
from anaconda_project.requirements_registry.requirements.conda_env import CondaEnvRequirement

if platform.system() == 'Windows':
    script_dir = "Scripts"
else:
    script_dir = "bin"

conda_env_var = conda_api.conda_prefix_variable()


def test_find_by_class_name_conda_env():
    registry = RequirementsRegistry()
    found = registry.find_provider_by_class_name(class_name="CondaEnvProvider")
    assert found is not None
    assert isinstance(found, CondaEnvProvider)


@pytest.mark.slow
def test_prepare_and_unprepare_project_scoped_env(monkeypatch):
    monkeypatch_conda_not_to_use_links(monkeypatch)

    def prepare_project_scoped_env(dirname):
        project = Project(dirname)
        fake_old_path = "foo" + os.pathsep + "bar"
        environ = dict(PROJECT_DIR=dirname, PATH=fake_old_path)
        result = prepare_without_interaction(project, environ=environ)
        assert result
        expected_env = os.path.join(dirname, "envs", "default")
        if platform.system() == 'Windows':
            expected_new_path = expected_env + os.pathsep + os.path.join(
                expected_env, script_dir) + os.pathsep + os.path.join(expected_env, "Library",
                                                                      "bin") + os.pathsep + "foo" + os.pathsep + "bar"
        else:
            expected_new_path = os.path.join(expected_env, script_dir) + os.pathsep + "foo" + os.pathsep + "bar"
        expected = dict(PROJECT_DIR=project.directory_path, PATH=expected_new_path)
        conda_api.environ_set_prefix(expected, expected_env)

        expected == result.environ
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
        result = prepare_without_interaction(project, environ=environ)
        assert result
        expected = dict(PROJECT_DIR=project.directory_path, PATH=expected_new_path)
        conda_api.environ_set_prefix(expected, expected_env)
        assert expected == result.environ
        assert conda_meta_mtime == os.path.getmtime(os.path.join(expected_env, "conda-meta"))

        # Now unprepare
        status = unprepare(project, result)
        assert status, status.errors
        assert status.status_description == ('Deleted environment files in %s.' % (expected_env))
        assert status.errors == []
        assert not os.path.exists(expected_env)

    with_directory_contents_completing_project_file(dict(), prepare_project_scoped_env)


def test_prepare_project_scoped_env_conda_create_fails(monkeypatch):
    def mock_create(prefix, pkgs, channels, stdout_callback, stderr_callback):
        raise conda_api.CondaError("error_from_conda_create")

    monkeypatch.setattr('anaconda_project.internal.conda_api.create', mock_create)

    def prepare_project_scoped_env_fails(dirname):
        project = Project(dirname)
        environ = minimal_environ(PROJECT_DIR=dirname)
        result = prepare_without_interaction(project, environ=environ)
        assert not result

        assert 'CONDA_DEFAULT_ENV' not in result.environ
        assert 'CONDA_ENV_PATH' not in result.environ

        # unprepare should not have anything to do
        status = unprepare(project, result)
        assert status
        assert status.errors == []
        assert status.status_description == "Nothing to clean up for environment 'default'."

    with_directory_contents_completing_project_file(dict(), prepare_project_scoped_env_fails)


def test_unprepare_gets_error_on_delete(monkeypatch):
    def mock_create(prefix, pkgs, channels, stdout_callback, stderr_callback):
        os.makedirs(os.path.join(prefix, "conda-meta"))

    monkeypatch.setattr('anaconda_project.internal.conda_api.create', mock_create)

    def prepare_project_scoped_env(dirname):
        project = Project(dirname)
        environ = minimal_environ(PROJECT_DIR=dirname)
        result = prepare_without_interaction(project, environ=environ)
        assert result
        expected_env = os.path.join(dirname, "envs", "default")

        # Now unprepare

        def mock_rmtree(path):
            raise IOError("I will never rm the tree!")

        monkeypatch.setattr('shutil.rmtree', mock_rmtree)

        status = unprepare(project, result)
        assert status.status_description == ('Failed to remove environment files in %s: I will never rm the tree!.' %
                                             (expected_env))
        assert not status

        assert os.path.exists(expected_env)

        # so we can rmtree our tmp directory
        monkeypatch.undo()

    with_directory_contents_completing_project_file(dict(), prepare_project_scoped_env)


def test_prepare_project_scoped_env_not_attempted_in_check_mode(monkeypatch):
    def mock_create(prefix, pkgs, channels, stdout_callback, stderr_callback):
        raise Exception("Should not have attempted to create env")

    monkeypatch.setattr('anaconda_project.internal.conda_api.create', mock_create)

    def prepare_project_scoped_env_not_attempted(dirname):
        project = Project(dirname)
        environ = minimal_environ(PROJECT_DIR=dirname)
        result = prepare_without_interaction(project, environ=environ, mode=provide.PROVIDE_MODE_CHECK)
        assert not result
        expected_env_path = os.path.join(dirname, "envs", "default")
        assert [('missing requirement to run this project: ' +
                 'The project needs a Conda environment containing all required packages.'),
                "  '%s' doesn't look like it contains a Conda environment yet." % expected_env_path] == result.errors

        # unprepare should not have anything to do
        status = unprepare(project, result)
        assert status
        assert status.errors == []
        assert status.status_description == ("Nothing to clean up for environment 'default'.")

    with_directory_contents_completing_project_file(dict(), prepare_project_scoped_env_not_attempted)


@pytest.mark.slow
def test_prepare_project_scoped_env_with_packages(monkeypatch):
    monkeypatch_conda_not_to_use_links(monkeypatch)

    def prepare_project_scoped_env_with_packages(dirname):
        project = Project(dirname)
        environ = minimal_environ(PROJECT_DIR=dirname)
        result = prepare_without_interaction(project, environ=environ)
        assert result

        prefix = result.environ[conda_env_var]
        installed = conda_api.installed(prefix)

        assert 'ipython' in installed
        assert 'numpy' in installed
        assert 'bokeh' not in installed

        # Preparing it again with new packages added should add those
        deps = project.project_file.get_value('packages')
        project.project_file.set_value('packages', deps + ['bokeh'])
        project.project_file.save()
        environ = minimal_environ(PROJECT_DIR=dirname)
        result = prepare_without_interaction(project, environ=environ)
        assert result

        prefix = result.environ[conda_env_var]
        installed = conda_api.installed(prefix)

        assert 'ipython' in installed
        assert 'numpy' in installed
        assert 'bokeh' in installed

        installed_pip = pip_api.installed(prefix)
        assert 'flake8' in installed_pip

        # Preparing it again with a bogus package should fail
        deps = project.project_file.get_value('packages')
        project.project_file.set_value(['packages'], deps + ['boguspackage'])
        project.project_file.save()
        environ = minimal_environ(PROJECT_DIR=dirname)
        result = prepare_without_interaction(project, environ=environ)
        assert not result

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
packages:
    - python=3.8
    - ipython
    - numpy=1.19
    - pip
    - pip:
      - flake8
"""
        }, prepare_project_scoped_env_with_packages)


def _conda_env_status(prepare_context):
    for status in prepare_context.statuses:
        if isinstance(status.requirement, CondaEnvRequirement):
            return status
    raise AssertionError("no CondaEnvRequirement found")


def test_configure_inherited(monkeypatch):
    def mock_conda_create(prefix, pkgs, channels, stdout_callback, stderr_callback):
        from anaconda_project.internal.makedirs import makedirs_ok_if_exists
        metadir = os.path.join(prefix, "conda-meta")
        makedirs_ok_if_exists(metadir)
        for p in pkgs:
            pkgmeta = os.path.join(metadir, "%s-0.1-pyNN.json" % p)
            open(pkgmeta, 'a').close()

    monkeypatch.setattr('anaconda_project.internal.conda_api.create', mock_conda_create)

    def check(dirname):
        envs_dir = os.path.join(dirname, "envs")

        project = Project(dirname)
        environ = minimal_environ(PROJECT_DIR=dirname)
        stage = prepare_in_stages(project, environ=environ)

        prepare_context = stage.configure()

        status = _conda_env_status(prepare_context)
        req = status.requirement
        provider = status.provider

        # check initial config

        config = provider.read_config(req, prepare_context.environ, prepare_context.local_state_file,
                                      prepare_context.default_env_spec_name, prepare_context.overrides)

        assert dict(env_name='default', source='project', value=os.path.join(envs_dir, 'default')) == config

        # set inherited mode

        config['source'] = 'inherited'

        provider.set_config_values_as_strings(req, prepare_context.environ, prepare_context.local_state_file,
                                              prepare_context.default_env_spec_name, prepare_context.overrides, config)

        config = provider.read_config(req, prepare_context.environ, prepare_context.local_state_file,
                                      prepare_context.default_env_spec_name, prepare_context.overrides)

        assert dict(env_name='default', source='inherited', value=os.environ.get(req.env_var)) == config

        # disable inherited mode again

        config['source'] = 'project'
        config['env_name'] = 'default'

        provider.set_config_values_as_strings(req, prepare_context.environ, prepare_context.local_state_file,
                                              prepare_context.default_env_spec_name, prepare_context.overrides, config)

        config = provider.read_config(req, prepare_context.environ, prepare_context.local_state_file,
                                      prepare_context.default_env_spec_name, prepare_context.overrides)

        assert dict(env_name='default', source='project', value=os.path.join(envs_dir, 'default')) == config

    with_directory_contents_completing_project_file(dict(), check)


def test_configure_different_env_spec(monkeypatch):
    def mock_conda_create(prefix, pkgs, channels, stdout_callback, stderr_callback):
        from anaconda_project.internal.makedirs import makedirs_ok_if_exists
        metadir = os.path.join(prefix, "conda-meta")
        makedirs_ok_if_exists(metadir)
        for p in pkgs:
            pkgmeta = os.path.join(metadir, "%s-0.1-pyNN.json" % p)
            open(pkgmeta, 'a').close()

    monkeypatch.setattr('anaconda_project.internal.conda_api.create', mock_conda_create)

    def check(dirname):
        envs_dir = os.path.join(dirname, "envs")

        project = Project(dirname)
        environ = minimal_environ(PROJECT_DIR=dirname)
        stage = prepare_in_stages(project, environ=environ)

        prepare_context = stage.configure()

        status = _conda_env_status(prepare_context)
        req = status.requirement
        provider = status.provider

        config = provider.read_config(req, prepare_context.environ, prepare_context.local_state_file,
                                      prepare_context.default_env_spec_name, prepare_context.overrides)
        assert dict(env_name='default', source='project', value=os.path.join(envs_dir, 'default')) == config

        config['env_name'] = 'bar'

        provider.set_config_values_as_strings(req, prepare_context.environ, prepare_context.local_state_file,
                                              prepare_context.default_env_spec_name, prepare_context.overrides, config)

        config = provider.read_config(req, prepare_context.environ, prepare_context.local_state_file,
                                      prepare_context.default_env_spec_name, prepare_context.overrides)
        assert dict(env_name='bar', source='project', value=os.path.join(envs_dir, 'bar')) == config

        assert os.path.join(envs_dir, 'bar') == prepare_context.local_state_file.get_value(['variables', req.env_var])

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
env_specs:
  default:
    packages: []
    channels: []
  foo:
    packages: []
    channels: []
  bar:
    packages: []
    channels: []
"""
        }, check)


@contextmanager
def _readonly_env(env_name, packages):
    with TemporaryDirectory(prefix="ro-envs-") as ro_envs:
        ro_prefix = os.path.join(ro_envs, env_name)
        conda_meta = os.path.join(ro_prefix, 'conda-meta')
        conda_api.create(prefix=ro_prefix, pkgs=packages)

        readonly_mode = stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
        os.chmod(ro_prefix, readonly_mode)
        os.chmod(conda_meta, readonly_mode)

        yield ro_prefix

        write_mode = (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH) ^ readonly_mode
        os.chmod(ro_prefix, write_mode)
        os.chmod(conda_meta, write_mode)


@pytest.mark.slow
@pytest.mark.skipif(platform.system() == 'Windows', reason='Windows has a hard time with read-only directories')
def test_clone_readonly_environment_with_deviations(monkeypatch):
    def clone_readonly_and_prepare(dirname):
        with _readonly_env(env_name='default', packages=('python=3.8', )) as ro_prefix:
            readonly = conda_api.installed(ro_prefix)
            assert 'python' in readonly
            assert 'requests' not in readonly

            ro_envs = os.path.dirname(ro_prefix)
            environ = minimal_environ(PROJECT_DIR=dirname,
                                      ANACONDA_PROJECT_ENVS_PATH=':{}'.format(ro_envs),
                                      ANACONDA_PROJECT_READONLY_ENVS_POLICY='clone')
            monkeypatch.setattr('os.environ', environ)

            project = Project(dirname)
            result = prepare_without_interaction(project)
            assert result
            assert result.env_prefix == os.path.join(dirname, 'envs', 'default')

            cloned = conda_api.installed(result.env_prefix)

            assert 'python' in cloned
            assert 'requests' in cloned

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
packages:
  - python=3.8
  - requests
env_specs:
  default: {}
"""}, clone_readonly_and_prepare)


@pytest.mark.slow
@pytest.mark.skipif(platform.system() == 'Windows', reason='Windows has a hard time with read-only directories')
def test_replace_readonly_environment_with_deviations(monkeypatch):
    def replace_readonly_and_prepare(dirname):
        with _readonly_env(env_name='default', packages=('python=3.8', )) as ro_prefix:
            readonly = conda_api.installed(ro_prefix)
            assert 'python' in readonly
            assert 'requests' not in readonly

            ro_envs = os.path.dirname(ro_prefix)
            environ = minimal_environ(PROJECT_DIR=dirname,
                                      ANACONDA_PROJECT_ENVS_PATH=':{}'.format(ro_envs),
                                      ANACONDA_PROJECT_READONLY_ENVS_POLICY='replace')
            monkeypatch.setattr('os.environ', environ)

            project = Project(dirname)
            result = prepare_without_interaction(project)
            assert result
            assert result.env_prefix == os.path.join(dirname, 'envs', 'default')

            replaced = conda_api.installed(result.env_prefix)

            assert 'python' in replaced
            assert 'requests' in replaced

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
packages:
  - python=3.8
  - requests
env_specs:
  default: {}
"""}, replace_readonly_and_prepare)


@pytest.mark.slow
@pytest.mark.skipif(platform.system() == 'Windows', reason='Windows has a hard time with read-only directories')
def test_fail_readonly_environment_with_deviations_unset_policy(monkeypatch):
    def clone_readonly_and_prepare(dirname):
        with _readonly_env(env_name='default', packages=('python=3.8', )) as ro_prefix:
            readonly = conda_api.installed(ro_prefix)
            assert 'python' in readonly
            assert 'requests' not in readonly

            ro_envs = os.path.dirname(ro_prefix)
            environ = minimal_environ(PROJECT_DIR=dirname, ANACONDA_PROJECT_ENVS_PATH=':{}'.format(ro_envs))
            monkeypatch.setattr('os.environ', environ)

            project = Project(dirname)
            result = prepare_without_interaction(project)
            assert result.failed
            assert '  Conda environment is missing packages: requests and the environment is read-only' in result.errors

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
packages:
  - python=3.8
  - requests
env_specs:
  default: {}
"""}, clone_readonly_and_prepare)


@pytest.mark.slow
@pytest.mark.skipif(platform.system() == 'Windows', reason='Windows has a hard time with read-only directories')
def test_fail_readonly_environment_with_deviations_set_policy(monkeypatch):
    def clone_readonly_and_prepare(dirname):
        with _readonly_env(env_name='default', packages=('python=3.8', )) as ro_prefix:
            readonly = conda_api.installed(ro_prefix)
            assert 'python' in readonly
            assert 'requests' not in readonly

            ro_envs = os.path.dirname(ro_prefix)
            environ = minimal_environ(PROJECT_DIR=dirname,
                                      ANACONDA_PROJECT_ENVS_PATH=':{}'.format(ro_envs),
                                      ANACONDA_PROJECT_READONLY_ENVS_POLICY='fail')
            monkeypatch.setattr('os.environ', environ)

            project = Project(dirname)
            result = prepare_without_interaction(project)
            assert result.failed
            assert '  Conda environment is missing packages: requests and the environment is read-only' in result.errors

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
packages:
  - python=3.8
  - requests
env_specs:
  default: {}
"""}, clone_readonly_and_prepare)
