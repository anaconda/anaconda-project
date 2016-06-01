# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import os
import platform

from anaconda_project.test.project_utils import project_dir_disable_dedicated_env
from anaconda_project.test.environ_utils import minimal_environ, minimal_environ_no_conda_env
from anaconda_project.conda_environment import CondaEnvironment
from anaconda_project.local_state_file import LocalStateFile
from anaconda_project.plugins.registry import PluginRegistry
from anaconda_project.plugins.requirement import UserConfigOverrides
from anaconda_project.plugins.requirements.conda_env import CondaEnvRequirement

from anaconda_project.internal.test.tmpfile_utils import with_directory_contents

if platform.system() == 'Windows':
    conda_env_var = 'CONDA_DEFAULT_ENV'
else:
    conda_env_var = 'CONDA_ENV_PATH'


def _empty_default_requirement():
    return CondaEnvRequirement(registry=PluginRegistry(),
                               environments=dict(default=CondaEnvironment('default', [], [])))


def test_env_var_on_windows(monkeypatch):
    def mock_system():
        return 'Windows'

    monkeypatch.setattr('platform.system', mock_system)
    registry = PluginRegistry()
    requirement = CondaEnvRequirement(registry)
    assert requirement.env_var == 'CONDA_DEFAULT_ENV'


def test_env_var_on_linux(monkeypatch):
    def mock_system():
        return 'Linux'

    monkeypatch.setattr('platform.system', mock_system)
    registry = PluginRegistry()
    requirement = CondaEnvRequirement(registry)
    assert requirement.env_var == 'CONDA_ENV_PATH'


def test_conda_env_title_and_description():
    requirement = _empty_default_requirement()
    assert requirement.title == 'A Conda environment'
    assert requirement.description == 'The project needs a Conda environment containing all required packages.'


def test_conda_default_env_not_set():
    def check_conda_default_env_not_set(dirname):
        requirement = _empty_default_requirement()
        project_dir_disable_dedicated_env(dirname)
        local_state = LocalStateFile.load_for_directory(dirname)
        status = requirement.check_status(
            minimal_environ_no_conda_env(PROJECT_DIR=dirname),
            local_state,
            UserConfigOverrides())
        expected = "'{}' doesn't look like it contains a Conda environment yet.".format(os.path.join(dirname, 'envs',
                                                                                                     'default'))
        assert expected == status.status_description

    with_directory_contents(dict(), check_conda_default_env_not_set)


def test_conda_default_env_is_bogus():
    def check_conda_default_env_is_bogus(dirname):
        requirement = _empty_default_requirement()
        project_dir_disable_dedicated_env(dirname)
        local_state = LocalStateFile.load_for_directory(dirname)
        status = requirement.check_status(
            minimal_environ_no_conda_env(**{conda_env_var: "not_a_real_env_anyone_has",
                                            'PROJECT_DIR': dirname}), local_state, UserConfigOverrides())
        expected = "'not_a_real_env_anyone_has' doesn't look like it contains a Conda environment yet."
        assert expected == status.status_description

    with_directory_contents(dict(), check_conda_default_env_is_bogus)


def test_conda_fails_while_listing_installed(monkeypatch):
    def check_fails_while_listing_installed(dirname):
        def sabotaged_installed_command(prefix):
            from anaconda_project.internal import conda_api
            raise conda_api.CondaError("sabotage!")

        monkeypatch.setattr('anaconda_project.internal.conda_api.installed', sabotaged_installed_command)

        project_dir_disable_dedicated_env(dirname)
        local_state = LocalStateFile.load_for_directory(dirname)

        requirement = CondaEnvRequirement(
            registry=PluginRegistry(),
            environments=dict(default=CondaEnvironment('default', ['not_a_real_package'], [])))
        status = requirement.check_status(minimal_environ(PROJECT_DIR=dirname), local_state, UserConfigOverrides())
        assert status.status_description.startswith("Conda failed while listing installed packages in ")
        assert status.status_description.endswith(": sabotage!")

    with_directory_contents(dict(), check_fails_while_listing_installed)


def test_missing_package():
    def check_missing_package(dirname):
        requirement = CondaEnvRequirement(
            registry=PluginRegistry(),
            environments=dict(default=CondaEnvironment('default', ['boguspackage', 'boguspackage2'], [])))
        project_dir_disable_dedicated_env(dirname)
        local_state = LocalStateFile.load_for_directory(dirname)
        status = requirement.check_status(minimal_environ(PROJECT_DIR=dirname), local_state, UserConfigOverrides())
        assert "Conda environment is missing packages: boguspackage, boguspackage2" == status.status_description

    with_directory_contents(dict(), check_missing_package)


def test_conda_env_set_to_something_else_while_default_exists():
    def check(dirname):
        requirement = _empty_default_requirement()
        # make it look like we already created envs/default, so the requirement
        # has to fail because the env var is wrong rather than because the
        # env itself is missing.
        envdir = os.path.join(dirname, "envs", "default")
        os.makedirs(os.path.join(envdir, 'conda-meta'))
        local_state = LocalStateFile.load_for_directory(dirname)
        environ = minimal_environ(PROJECT_DIR=dirname)
        status = requirement.check_status(environ, local_state, UserConfigOverrides())
        expected = "%s is set to %s instead of %s." % (requirement.env_var, environ.get(requirement.env_var), envdir)
        assert expected == status.status_description

    with_directory_contents(dict(), check)
