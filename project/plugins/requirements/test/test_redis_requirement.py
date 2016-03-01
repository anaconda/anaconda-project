from project.local_state_file import LocalStateFile
from project.plugins.registry import PluginRegistry
from project.plugins.requirements.redis import RedisRequirement

from project.internal.test.tmpfile_utils import with_directory_contents


def test_find_by_env_var_redis():
    registry = PluginRegistry()
    found = registry.find_requirement_by_env_var(env_var='REDIS_URL', options=dict())
    assert found is not None
    assert isinstance(found, RedisRequirement)
    assert found.env_var == 'REDIS_URL'


def test_redis_url_not_set():
    def check_not_set(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        requirement = RedisRequirement(registry=PluginRegistry())
        status = requirement.check_status(dict(), local_state)
        assert not status
        assert "Environment variable REDIS_URL is not set." == status.status_description

    with_directory_contents({}, check_not_set)


def test_redis_url_bad_scheme():
    def check_bad_scheme(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        requirement = RedisRequirement(registry=PluginRegistry())
        status = requirement.check_status(dict(REDIS_URL="http://example.com/"), local_state)
        assert not status
        assert "REDIS_URL value 'http://example.com/' does not have 'redis:' scheme." == status.status_description

    with_directory_contents({}, check_bad_scheme)


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
    def check_cannot_connect(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        requirement = RedisRequirement(registry=PluginRegistry())
        can_connect_args = _monkeypatch_can_connect_to_socket_fails(monkeypatch)
        status = requirement.check_status(dict(REDIS_URL="redis://example.com:1234/"), local_state)
        assert dict(host='example.com', port=1234, timeout_seconds=0.5) == can_connect_args
        assert not status
        expected = "Cannot connect to Redis at redis://example.com:1234/."
        assert expected == status.status_description

    with_directory_contents({}, check_cannot_connect)
