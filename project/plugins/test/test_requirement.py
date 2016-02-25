from project.plugins.provider import ProviderRegistry
from project.plugins.requirement import RequirementRegistry, EnvVarRequirement


def test_find_by_env_var_unknown():
    registry = RequirementRegistry()
    found = registry.find_by_env_var(env_var='FOO', options=None)
    assert found is not None
    assert isinstance(found, EnvVarRequirement)
    assert found.env_var == 'FOO'
    assert "EnvVarRequirement(env_var='FOO')" == repr(found)


def test_autoguess_encrypted_option():
    assert not EnvVarRequirement(env_var='FOO').encrypted
    assert EnvVarRequirement(env_var='FOO', options=dict(encrypted=True)).encrypted

    assert EnvVarRequirement(env_var='FOO_PASSWORD').encrypted
    assert EnvVarRequirement(env_var='FOO_SECRET').encrypted
    assert EnvVarRequirement(env_var='FOO_SECRET_KEY').encrypted
    assert EnvVarRequirement(env_var='FOO_ENCRYPTED').encrypted

    assert not EnvVarRequirement(env_var='FOO_PASSWORD', options=dict(encrypted=False)).encrypted
    assert not EnvVarRequirement(env_var='FOO_SECRET', options=dict(encrypted=False)).encrypted
    assert not EnvVarRequirement(env_var='FOO_SECRET_KEY', options=dict(encrypted=False)).encrypted
    assert not EnvVarRequirement(env_var='FOO_ENCRYPTED', options=dict(encrypted=False)).encrypted


def test_empty_variable_treated_as_unset():
    requirement = EnvVarRequirement(env_var='FOO')
    status = requirement.check_status(dict(FOO=''), ProviderRegistry())
    assert not status
    assert "Environment variable FOO is not set." == status.status_description
