# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import

import os
import platform
import pytest

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
from anaconda_project.requirements_registry.requirements.conda_env import (CondaBootstrapEnvRequirement,
                                                                           CondaEnvRequirement)
from anaconda_project.requirements_registry.providers.conda_env import CondaBootstrapEnvProvider

if platform.system() == 'Windows':
    script_dir = "Scripts"
else:
    script_dir = "bin"

conda_env_var = conda_api.conda_prefix_variable()


def test_find_by_class_name_conda_env():
    registry = RequirementsRegistry()
    found = registry.find_provider_by_class_name(class_name="CondaBootstrapEnvProvider")
    assert found is not None
    assert isinstance(found, CondaBootstrapEnvProvider)


@pytest.mark.slow
def test_prepare_and_unprepare_project_scoped_env(monkeypatch):
    monkeypatch_conda_not_to_use_links(monkeypatch)

    def prepare_project_scoped_env(dirname):
        project = Project(dirname)
        fake_old_path = "foo" + os.pathsep + "bar"
        environ = dict(PROJECT_DIR=dirname, PATH=fake_old_path)
        result = prepare_without_interaction(project, environ=environ)
        assert result
        expected_env = os.path.join(dirname, "envs", "bootstrap-env")
        if platform.system() == 'Windows':
            expected_new_path = expected_env + os.pathsep + os.path.join(
                expected_env, script_dir) + os.pathsep + os.path.join(expected_env, "Library",
                                                                      "bin") + os.pathsep + "foo" + os.pathsep + "bar"
        else:
            expected_new_path = os.path.join(expected_env, script_dir) + os.pathsep + "foo" + os.pathsep + "bar"
        expected = dict(PROJECT_DIR=project.directory_path, PATH=expected_new_path, BOOTSTRAP_ENV_PREFIX=expected_env)
        conda_api.environ_set_prefix(expected, expected_env)

        expected == result.environ
        assert os.path.exists(os.path.join(expected_env, "conda-meta"))
        conda_meta_mtime = os.path.getmtime(os.path.join(expected_env, "conda-meta"))

        # bare minimum bootstrap-env env shouldn't include these
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
        assert conda_meta_mtime == os.path.getmtime(os.path.join(expected_env, "conda-meta"))

        # Now unprepare
        status = unprepare(project, result)
        assert status

        # todo: this differs from standard CondaEnvProvider
        assert status.status_description == 'Success.'
        assert status.errors == []
        assert not os.path.exists(expected_env)

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
env_specs:
  bootstrap-env:
    packages:
        - python
"""}, prepare_project_scoped_env)


def test_prepare_project_scoped_env_not_attempted_in_check_mode(monkeypatch):
    def mock_create(prefix, pkgs, channels, stdout_callback, stderr_callback):
        raise Exception("Should not have attempted to create env")

    monkeypatch.setattr('anaconda_project.internal.conda_api.create', mock_create)

    def prepare_project_scoped_env_not_attempted(dirname):
        project = Project(dirname)
        environ = minimal_environ(PROJECT_DIR=dirname)
        result = prepare_without_interaction(project, environ=environ, mode=provide.PROVIDE_MODE_CHECK)
        assert not result
        # expected_env_path = os.path.join(dirname, "envs", "default")
        bootstrap_env_path = os.path.join(dirname, "envs", "bootstrap-env")
        for err in [
            ('missing requirement to run this project: ' +
             'The project needs a Conda bootstrap environment containing all required packages.'),
                "  '%s' doesn't look like it contains a Conda environment yet." % bootstrap_env_path,
        ]:
            assert err in result.errors

        # unprepare should not have anything to do
        status = unprepare(project, result)
        assert status
        assert status.errors == []

        # todo: would be good to understand the different message got with a "normal" env
        assert status.status_description == ("Success.")

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
env_specs:
  bootstrap-env:
    packages:
        - ipython
"""}, prepare_project_scoped_env_not_attempted)


@pytest.mark.slow
def test_prepare_project_scoped_env_with_packages(monkeypatch):
    monkeypatch_conda_not_to_use_links(monkeypatch)

    def prepare_project_scoped_env_with_packages(dirname):
        project = Project(dirname)
        environ = minimal_environ(PROJECT_DIR=dirname)
        result = prepare_without_interaction(project, environ=environ, env_spec_name='bootstrap-env')
        assert result

        envs_dir = os.path.join(dirname, "envs")
        env_name = 'bootstrap-env'
        prefix = os.path.join(envs_dir, env_name)
        installed = conda_api.installed(prefix)

        assert 'bokeh' not in installed

        deps = ['ipython', 'numpy', 'pip']
        for pkg in deps:
            assert pkg in installed

        deps += ['bokeh']

        # Preparing it again with new packages added should add those
        project.project_file.set_value('packages', deps)
        project.project_file.save()
        environ = minimal_environ(PROJECT_DIR=dirname)
        result = prepare_without_interaction(project, environ=environ)
        assert result

        prefix = result.environ[conda_env_var]
        installed = conda_api.installed(prefix)

        for pkg in deps:
            assert pkg in installed

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
        {DEFAULT_PROJECT_FILENAME: """
env_specs:
  bootstrap-env:
    packages:
        - ipython
        - numpy
        - pip:
            - flake8
"""}, prepare_project_scoped_env_with_packages)


def _conda_bootstrap_env_status(prepare_context):
    for status in prepare_context.statuses:
        if isinstance(status.requirement, CondaBootstrapEnvRequirement):
            return status
    raise AssertionError("no CondaBootstrapEnvProvider found")


def _conda_env_status(prepare_context):
    for status in prepare_context.statuses:
        if isinstance(status.requirement, CondaEnvRequirement):
            return status
    raise AssertionError("no CondaBootstrapEnvProvider found")


def test_configure_inherited(monkeypatch):
    """Test configure from empty env is the same as before and does not have a bootstrap env req"""

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

        status = _conda_bootstrap_env_status(prepare_context)
        req = status.requirement
        provider = status.provider

        config = provider.read_config(req, prepare_context.environ, prepare_context.local_state_file,
                                      prepare_context.default_env_spec_name, prepare_context.overrides)
        assert dict(env_name='bootstrap-env', source='project', value=os.path.join(envs_dir, 'bootstrap-env')) == config

        config['env_name'] = 'bar'

        provider.set_config_values_as_strings(req, prepare_context.environ, prepare_context.local_state_file,
                                              prepare_context.default_env_spec_name, prepare_context.overrides, config)

        config = provider.read_config(req, prepare_context.environ, prepare_context.local_state_file,
                                      prepare_context.default_env_spec_name, prepare_context.overrides)
        assert dict(env_name='bar', source='project', value=os.path.join(envs_dir, 'bar')) == config

        assert os.path.join(envs_dir, 'bar') == prepare_context.local_state_file.get_value(['variables', req.env_var])

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
env_specs:
  bootstrap-env:
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
