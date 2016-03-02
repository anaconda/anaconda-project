from project.plugins.registry import PluginRegistry
from project.plugins.requirements.master_password import MasterPasswordRequirement
from project.plugins.providers.master_password import MasterPasswordProvider

from project.internal.test.tmpfile_utils import tmp_local_state_file


def test_find_by_env_var_master_password():
    registry = PluginRegistry()
    found = registry.find_requirement_by_env_var(env_var='ANACONDA_MASTER_PASSWORD', options=dict())
    assert found is not None
    assert isinstance(found, MasterPasswordRequirement)
    assert found.env_var == 'ANACONDA_MASTER_PASSWORD'
    assert not found.encrypted


def test_master_password_not_set():
    requirement = MasterPasswordRequirement(registry=PluginRegistry())
    status = requirement.check_status(dict(), tmp_local_state_file())
    assert not status
    expected = "Anaconda master password isn't set as the ANACONDA_MASTER_PASSWORD environment variable."
    assert expected == status.status_description


def test_master_password_provider():
    requirement = MasterPasswordRequirement(registry=PluginRegistry())
    status = requirement.check_status(dict(), tmp_local_state_file())
    assert status.provider is not None
    assert isinstance(status.provider, MasterPasswordProvider)
