from project.plugins.provider import ProviderRegistry, EnvVarProvider


def test_find_by_env_var():
    registry = ProviderRegistry()
    found = registry.find_by_env_var(requirement=None, env_var="FOO")
    assert 1 == len(found)
    assert isinstance(found[0], EnvVarProvider)


def test_env_var_provider():
    provider = EnvVarProvider()
    assert "Manually set environment variable" == provider.title
    # just check this doesn't throw or anything, for now
    provider.provide(requirement=None, environ=dict())


def test_fail_to_find_by_service():
    registry = ProviderRegistry()
    found = registry.find_by_service(requirement=None, service="nope")
    assert 0 == len(found)
