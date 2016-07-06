# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import os

from conda_kapsel.test.project_utils import project_dir_disable_dedicated_env
from conda_kapsel.test.environ_utils import (minimal_environ, minimal_environ_no_conda_env)
from conda_kapsel.env_spec import EnvSpec
from conda_kapsel.local_state_file import LocalStateFile
from conda_kapsel.plugins.registry import PluginRegistry
from conda_kapsel.plugins.requirement import UserConfigOverrides
from conda_kapsel.plugins.requirements.conda_env import CondaEnvRequirement

from conda_kapsel.internal.test.tmpfile_utils import with_directory_contents
from conda_kapsel.internal import conda_api

conda_env_var = conda_api.conda_prefix_variable()


def _empty_default_requirement():
    return CondaEnvRequirement(registry=PluginRegistry(), env_specs=dict(default=EnvSpec('default', [], [])))


def test_env_var():
    registry = PluginRegistry()
    requirement = CondaEnvRequirement(registry)
    assert requirement.env_var == conda_env_var


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
            'default',
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
            minimal_environ_no_conda_env(**{'PROJECT_DIR': dirname}),
            local_state,
            'default',
            UserConfigOverrides(inherited_env="not_a_real_env_anyone_has"))
        expected = "'not_a_real_env_anyone_has' doesn't look like it contains a Conda environment yet."
        assert expected == status.status_description

    with_directory_contents(dict(), check_conda_default_env_is_bogus)


def test_conda_fails_while_listing_installed(monkeypatch):
    def check_fails_while_listing_installed(dirname):
        def sabotaged_installed_command(prefix):
            from conda_kapsel.internal import conda_api
            raise conda_api.CondaError("sabotage!")

        monkeypatch.setattr('conda_kapsel.internal.conda_api.installed', sabotaged_installed_command)

        project_dir_disable_dedicated_env(dirname)
        local_state = LocalStateFile.load_for_directory(dirname)

        requirement = CondaEnvRequirement(registry=PluginRegistry(),
                                          env_specs=dict(default=EnvSpec('default', ['not_a_real_package'], [])))
        environ = minimal_environ(PROJECT_DIR=dirname)
        status = requirement.check_status(environ,
                                          local_state,
                                          'default',
                                          UserConfigOverrides(inherited_env=environ.get(conda_env_var)))
        assert status.status_description.startswith("Conda failed while listing installed packages in ")
        assert status.status_description.endswith(": sabotage!")

    with_directory_contents(dict(), check_fails_while_listing_installed)


def test_missing_package():
    def check_missing_package(dirname):
        requirement = CondaEnvRequirement(
            registry=PluginRegistry(),
            env_specs=dict(default=EnvSpec('default', ['boguspackage', 'boguspackage2'], [])))
        project_dir_disable_dedicated_env(dirname)
        local_state = LocalStateFile.load_for_directory(dirname)
        environ = minimal_environ(PROJECT_DIR=dirname)
        status = requirement.check_status(environ,
                                          local_state,
                                          'default',
                                          UserConfigOverrides(inherited_env=environ.get(conda_env_var)))
        assert "Conda environment is missing packages: boguspackage, boguspackage2" == status.status_description

    with_directory_contents(dict(), check_missing_package)
