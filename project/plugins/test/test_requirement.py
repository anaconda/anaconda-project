from project.plugins.requirement import RequirementRegistry, EnvVarRequirement


def test_find_by_env_var_unknown():
    registry = RequirementRegistry()
    found = registry.find_by_env_var(env_var='FOO', options=None)
    assert found is not None
    assert isinstance(found, EnvVarRequirement)
    assert found.env_var == 'FOO'
