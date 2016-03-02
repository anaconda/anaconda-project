from project.plugins.registry import PluginRegistry
from project.plugins.requirement import EnvVarRequirement

from project.internal.test.tmpfile_utils import tmp_local_state_file


def test_find_by_env_var_unknown():
    registry = PluginRegistry()
    found = registry.find_requirement_by_env_var(env_var='FOO', options=None)
    assert found is not None
    assert isinstance(found, EnvVarRequirement)
    assert found.env_var == 'FOO'
    assert "EnvVarRequirement(env_var='FOO')" == repr(found)


def test_autoguess_encrypted_option():
    def req(env_var, options=None):
        return EnvVarRequirement(registry=PluginRegistry(), env_var=env_var, options=options)

    assert not req(env_var='FOO').encrypted
    assert req(env_var='FOO', options=dict(encrypted=True)).encrypted

    assert req(env_var='FOO_PASSWORD').encrypted
    assert req(env_var='FOO_SECRET').encrypted
    assert req(env_var='FOO_SECRET_KEY').encrypted
    assert req(env_var='FOO_ENCRYPTED').encrypted

    assert not req(env_var='FOO_PASSWORD', options=dict(encrypted=False)).encrypted
    assert not req(env_var='FOO_SECRET', options=dict(encrypted=False)).encrypted
    assert not req(env_var='FOO_SECRET_KEY', options=dict(encrypted=False)).encrypted
    assert not req(env_var='FOO_ENCRYPTED', options=dict(encrypted=False)).encrypted


def test_empty_variable_treated_as_unset():
    requirement = EnvVarRequirement(registry=PluginRegistry(), env_var='FOO')
    status = requirement.check_status(dict(FOO=''), tmp_local_state_file())
    assert not status
    assert "Environment variable FOO is not set." == status.status_description
