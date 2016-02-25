from project.plugins.requirement import RequirementRegistry
from project.plugins.provider import ProviderRegistry
from project.plugins.requirements.master_password import MasterPasswordRequirement
from project.plugins.providers.master_password import MasterPasswordProvider


def test_find_by_env_var_master_password():
    registry = RequirementRegistry()
    found = registry.find_by_env_var(env_var='ANACONDA_MASTER_PASSWORD', options=dict())
    assert found is not None
    assert isinstance(found, MasterPasswordRequirement)
    assert found.env_var == 'ANACONDA_MASTER_PASSWORD'
    assert not found.encrypted


def test_master_password_not_set():
    requirement = MasterPasswordRequirement()
    status = requirement.check_status(dict(), ProviderRegistry())
    assert not status
    expected = "Anaconda master password isn't set as the ANACONDA_MASTER_PASSWORD environment variable."
    assert expected == status.status_description


def test_master_password_providers():
    registry = ProviderRegistry()
    requirement = MasterPasswordRequirement()
    status = requirement.check_status(dict(), registry)
    len(status.possible_providers) == 1
    assert isinstance(status.possible_providers[0], MasterPasswordProvider)
