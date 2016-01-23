from project.plugins.requirement import RequirementRegistry
from project.plugins.requirements.redis import DefaultRedisRequirement


def test_find_by_env_var_redis():
    registry = RequirementRegistry()
    found = registry.find_by_env_var(env_var='REDIS_URL', options=dict())
    assert found is not None
    assert isinstance(found, DefaultRedisRequirement)
    assert found.env_var == 'REDIS_URL'


def test_redis_url_not_set():
    requirement = DefaultRedisRequirement()
    why_not = requirement.why_not_provided(dict())
    assert "Environment variable REDIS_URL is not set" == why_not


def test_redis_url_bad_scheme():
    requirement = DefaultRedisRequirement()
    why_not = requirement.why_not_provided(dict(REDIS_URL="http://example.com/"))
    assert "REDIS_URL value 'http://example.com/' does not have 'redis:' scheme" == why_not


def _monkeypatch_can_connect_to_socket_fails(monkeypatch):
    can_connect_args = dict()

    def mock_can_connect_to_socket(host, port, timeout_seconds=0.5):
        can_connect_args['host'] = host
        can_connect_args['port'] = port
        can_connect_args['timeout_seconds'] = timeout_seconds
        return False

    monkeypatch.setattr("project.plugins.network_util.can_connect_to_socket", mock_can_connect_to_socket)

    return can_connect_args


def test_redis_url_cannot_connect(monkeypatch):
    requirement = DefaultRedisRequirement()
    can_connect_args = _monkeypatch_can_connect_to_socket_fails(monkeypatch)
    why_not = requirement.why_not_provided(dict(REDIS_URL="redis://example.com:1234/"))
    assert dict(host='example.com', port=1234, timeout_seconds=0.5) == can_connect_args
    assert "Cannot connect to redis://example.com:1234/ (from REDIS_URL)" == why_not
