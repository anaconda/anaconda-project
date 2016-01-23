from project.plugins.provider import ProviderRegistry
from project.plugins.providers.redis import DefaultRedisProvider


def test_find_by_service_redis():
    registry = ProviderRegistry()
    found = registry.find_by_service(requirement=None, service="redis")
    assert 1 == len(found)
    assert isinstance(found[0], DefaultRedisProvider)
    assert "Default Redis port on localhost" == found[0].title
