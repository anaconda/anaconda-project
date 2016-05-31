# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from anaconda_project.plugins.registry import PluginRegistry
from anaconda_project.plugins.requirement import UserConfigOverrides
from anaconda_project.plugins.requirements.master_password import MasterPasswordRequirement
from anaconda_project.plugins.providers.master_password import MasterPasswordProvider

from anaconda_project.internal.test.tmpfile_utils import tmp_local_state_file


def test_find_by_env_var_master_password():
    registry = PluginRegistry()
    found = registry.find_requirement_by_env_var(env_var='ANACONDA_MASTER_PASSWORD', options=dict())
    assert found is not None
    assert isinstance(found, MasterPasswordRequirement)
    assert found.env_var == 'ANACONDA_MASTER_PASSWORD'
    assert not found.encrypted


def test_master_password_title_and_help():
    registry = PluginRegistry()
    found = registry.find_requirement_by_env_var(env_var='ANACONDA_MASTER_PASSWORD', options=dict())
    assert found is not None
    assert isinstance(found, MasterPasswordRequirement)
    assert found.title == 'ANACONDA_MASTER_PASSWORD'
    assert found.help == 'Anaconda master password (used to encrypt other passwords and credentials).'


def test_master_password_not_set():
    requirement = MasterPasswordRequirement(registry=PluginRegistry())
    status = requirement.check_status(dict(), tmp_local_state_file(), UserConfigOverrides())
    assert not status
    expected = "Anaconda master password isn't set as the ANACONDA_MASTER_PASSWORD environment variable."
    assert expected == status.status_description


def test_master_password_provider():
    requirement = MasterPasswordRequirement(registry=PluginRegistry())
    status = requirement.check_status(dict(), tmp_local_state_file(), UserConfigOverrides())
    assert status.provider is not None
    assert isinstance(status.provider, MasterPasswordProvider)
