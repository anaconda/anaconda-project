from __future__ import absolute_import

import codecs
import os

from project.internal.test.tmpfile_utils import with_directory_contents
from project.local_state_file import LOCAL_STATE_DIRECTORY, LOCAL_STATE_FILENAME
from project.local_state_file import LocalStateFile
from project.plugins.registry import PluginRegistry
from project.plugins.provider import ProviderConfigContext
from project.plugins.providers.redis import RedisProvider
from project.plugins.requirements.redis import RedisRequirement
from project.prepare import prepare, unprepare
from project.project import Project
from project.project_file import PROJECT_FILENAME


def _redis_requirement():
    return RedisRequirement(registry=PluginRegistry(), env_var="REDIS_URL")


def test_find_by_service_redis():
    registry = PluginRegistry()
    found = registry.find_providers_by_service(requirement=None, service="redis")
    assert 1 == len(found)
    assert isinstance(found[0], RedisProvider)


def test_reading_default_config():
    def read_config(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        requirement = _redis_requirement()
        provider = RedisProvider()
        config = provider.read_config(ProviderConfigContext(dict(), local_state, requirement))
        assert 6380 == config['lower_port']
        assert 6449 == config['upper_port']

    with_directory_contents(dict(), read_config)


def test_reading_valid_config():
    def read_config(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        requirement = _redis_requirement()
        provider = RedisProvider()
        config = provider.read_config(ProviderConfigContext(dict(), local_state, requirement))
        assert 7389 == config['lower_port']
        assert 7421 == config['upper_port']
        assert 'all' == config['scope']

    with_directory_contents(
        {
            LOCAL_STATE_DIRECTORY + "/" + LOCAL_STATE_FILENAME: """
runtime:
  REDIS_URL:
    providers:
      RedisProvider:
        port_range: 7389-7421
        autostart: false
         """
        }, read_config)


def _read_invalid_port_range(capsys, port_range):
    def read_config(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        requirement = _redis_requirement()
        provider = RedisProvider()
        config = provider.read_config(ProviderConfigContext(dict(), local_state, requirement))
        # revert to defaults
        assert 6380 == config['lower_port']
        assert 6449 == config['upper_port']
        # should have printed an error
        out, err = capsys.readouterr()
        assert ("Invalid port_range '%s', should be like '6380-6449'\n" % (port_range)) == err

    with_directory_contents(
        {
            LOCAL_STATE_DIRECTORY + "/" + LOCAL_STATE_FILENAME: """
runtime:
  REDIS_URL:
    providers:
      RedisProvider:
        port_range: %s
         """ % port_range
        }, read_config)


def test_garbage_port_range(capsys):
    _read_invalid_port_range(capsys, "abcdefg")


def test_backward_port_range(capsys):
    _read_invalid_port_range(capsys, "100-99")


def test_non_integer_port_range(capsys):
    _read_invalid_port_range(capsys, "A-Z")


def test_zero_lower_port(capsys):
    _read_invalid_port_range(capsys, "0-1")


def test_zero_upper_port(capsys):
    _read_invalid_port_range(capsys, "1-0")


def test_set_config_values_as_strings():
    def set_config(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        requirement = _redis_requirement()
        provider = RedisProvider()
        provider.set_config_values_as_strings(
            ProviderConfigContext(dict(), local_state, requirement),
            dict(lower_port="6001"))
        config = provider.read_config(ProviderConfigContext(dict(), local_state, requirement))
        assert config['lower_port'] == 6001
        assert config['upper_port'] == 6449

        provider.set_config_values_as_strings(
            ProviderConfigContext(dict(), local_state, requirement),
            dict(upper_port="6700"))
        config2 = provider.read_config(ProviderConfigContext(dict(), local_state, requirement))
        assert config2['lower_port'] == 6001
        assert config2['upper_port'] == 6700

        provider.set_config_values_as_strings(
            ProviderConfigContext(dict(), local_state, requirement),
            dict(lower_port="5500",
                 upper_port="6800"))
        config2 = provider.read_config(ProviderConfigContext(dict(), local_state, requirement))
        assert config2['lower_port'] == 5500
        assert config2['upper_port'] == 6800

    with_directory_contents(dict(), set_config)


def _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch):
    can_connect_args = dict()

    def mock_can_connect_to_socket(host, port, timeout_seconds=0.5):
        can_connect_args['host'] = host
        can_connect_args['port'] = port
        can_connect_args['timeout_seconds'] = timeout_seconds
        return True

    monkeypatch.setattr("project.plugins.network_util.can_connect_to_socket", mock_can_connect_to_socket)

    return can_connect_args


def test_prepare_redis_url_with_dict_in_runtime_section(monkeypatch):
    can_connect_args = _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch)

    def prepare_redis_url(dirname):
        project = Project(dirname)
        result = prepare(project, environ=dict())
        assert result
        assert dict(REDIS_URL="redis://localhost:6379", PROJECT_DIR=project.directory_path) == result.environ
        assert dict(host='localhost', port=6379, timeout_seconds=0.5) == can_connect_args

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  REDIS_URL: {}
"""}, prepare_redis_url)


def test_prepare_redis_url_with_list_in_runtime_section(monkeypatch):
    can_connect_args = _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch)

    def prepare_redis_url(dirname):
        project = Project(dirname)
        result = prepare(project, environ=dict())
        assert result
        assert dict(REDIS_URL="redis://localhost:6379", PROJECT_DIR=project.directory_path) == result.environ
        assert dict(host='localhost', port=6379, timeout_seconds=0.5) == can_connect_args

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  - REDIS_URL
"""}, prepare_redis_url)


def _monkeypatch_can_connect_to_socket_on_nonstandard_port_only(monkeypatch, real_can_connect_to_socket):
    can_connect_args_list = []

    def mock_can_connect_to_socket(host, port, timeout_seconds=0.5):
        can_connect_args = dict()
        can_connect_args['host'] = host
        can_connect_args['port'] = port
        can_connect_args['timeout_seconds'] = timeout_seconds
        can_connect_args_list.append(can_connect_args)
        if port == 6379:
            return False
        else:
            return real_can_connect_to_socket(host, port, timeout_seconds)

    monkeypatch.setattr("project.plugins.network_util.can_connect_to_socket", mock_can_connect_to_socket)

    return can_connect_args_list


def test_prepare_and_unprepare_local_redis_server(monkeypatch):
    # this test will fail if you don't have Redis installed, since
    # it actually starts it.
    from project.plugins.network_util import can_connect_to_socket as real_can_connect_to_socket

    can_connect_args_list = _monkeypatch_can_connect_to_socket_on_nonstandard_port_only(monkeypatch,
                                                                                        real_can_connect_to_socket)

    def start_local_redis(dirname):
        project = Project(dirname)
        result = prepare(project, environ=dict())
        assert result

        local_state_file = LocalStateFile.load_for_directory(dirname)
        state = local_state_file.get_service_run_state("RedisProvider")
        assert 'port' in state
        port = state['port']

        assert dict(REDIS_URL=("redis://localhost:" + str(port)), PROJECT_DIR=project.directory_path) == result.environ
        assert len(can_connect_args_list) >= 2

        pidfile = os.path.join(dirname, ".anaconda/run/project_scoped_redis/redis.pid")
        logfile = os.path.join(dirname, ".anaconda/run/project_scoped_redis/redis.log")
        assert os.path.exists(pidfile)
        assert os.path.exists(logfile)

        assert real_can_connect_to_socket(host='localhost', port=port)

        # now clean it up
        unprepare(project)

        assert not os.path.exists(pidfile)
        assert not real_can_connect_to_socket(host='localhost', port=port)

        local_state_file.load()
        assert dict() == local_state_file.get_service_run_state("RedisProvider")

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  REDIS_URL: {}
"""}, start_local_redis)


def test_prepare_local_redis_server_twice_reuses(monkeypatch):
    # this test will fail if you don't have Redis installed, since
    # it actually starts it.
    from project.plugins.network_util import can_connect_to_socket as real_can_connect_to_socket

    can_connect_args_list = _monkeypatch_can_connect_to_socket_on_nonstandard_port_only(monkeypatch,
                                                                                        real_can_connect_to_socket)

    def start_local_redis(dirname):
        project = Project(dirname)
        result = prepare(project, environ=dict())
        assert result
        assert 'REDIS_URL' in result.environ

        local_state_file = LocalStateFile.load_for_directory(dirname)
        state = local_state_file.get_service_run_state("RedisProvider")
        assert 'port' in state
        port = state['port']

        assert dict(REDIS_URL=("redis://localhost:" + str(port)), PROJECT_DIR=project.directory_path) == result.environ
        assert len(can_connect_args_list) >= 2

        pidfile = os.path.join(dirname, ".anaconda/run/project_scoped_redis/redis.pid")
        logfile = os.path.join(dirname, ".anaconda/run/project_scoped_redis/redis.log")
        assert os.path.exists(pidfile)
        assert os.path.exists(logfile)

        assert real_can_connect_to_socket(host='localhost', port=port)

        # be sure we generate the config html that would use the old one
        requirement = _redis_requirement()
        status = requirement.check_status(result.environ)
        config_context = ProviderConfigContext(result.environ, local_state_file, requirement)
        html = RedisProvider().config_html(config_context, status)
        assert 'Use the redis-server we started earlier' in html

        # now try again, and we should re-use the exact same server
        pidfile_mtime = os.path.getmtime(pidfile)
        with codecs.open(pidfile, 'r', 'utf-8') as file:
            pidfile_content = file.read()
        result2 = prepare(project, environ=dict())
        assert result2

        # port should be the same, and set in the environment
        assert dict(REDIS_URL=("redis://localhost:" + str(port)), PROJECT_DIR=project.directory_path) == result2.environ

        # no new pid file
        assert pidfile_mtime == os.path.getmtime(pidfile)
        with codecs.open(pidfile, 'r', 'utf-8') as file:
            pidfile_content2 = file.read()
        assert pidfile_content == pidfile_content2

        # now clean it up
        unprepare(project)

        assert not os.path.exists(pidfile)
        assert not real_can_connect_to_socket(host='localhost', port=port)

        local_state_file.load()
        assert dict() == local_state_file.get_service_run_state("RedisProvider")

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  REDIS_URL: {}
"""}, start_local_redis)


def _monkeypatch_can_connect_to_socket_always_succeeds_on_nonstandard(monkeypatch):
    can_connect_args_list = []

    def mock_can_connect_to_socket(host, port, timeout_seconds=0.5):
        can_connect_args = dict()
        can_connect_args['host'] = host
        can_connect_args['port'] = port
        can_connect_args['timeout_seconds'] = timeout_seconds
        can_connect_args_list.append(can_connect_args)
        return port != 6379

    monkeypatch.setattr("project.plugins.network_util.can_connect_to_socket", mock_can_connect_to_socket)

    return can_connect_args_list


def test_fail_to_prepare_local_redis_server_no_port_available(monkeypatch, capsys):
    can_connect_args_list = _monkeypatch_can_connect_to_socket_always_succeeds_on_nonstandard(monkeypatch)

    def start_local_redis(dirname):
        project = Project(dirname)
        result = prepare(project, environ=dict())
        assert not result
        assert 71 == len(can_connect_args_list)

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  REDIS_URL: {}
"""}, start_local_redis)

    out, err = capsys.readouterr()
    assert "All ports from 6380 to 6449 were in use, could not start redis-server on one of them." in err
    assert "REDIS_URL" in err
    assert "missing requirement" in err
    assert "" == out


def _monkeypatch_can_connect_to_socket_always_fails(monkeypatch):
    def mock_can_connect_to_socket(host, port, timeout_seconds=0.5):
        return False

    monkeypatch.setattr("project.plugins.network_util.can_connect_to_socket", mock_can_connect_to_socket)


def test_fail_to_prepare_local_redis_server_scope_system(monkeypatch, capsys):
    _monkeypatch_can_connect_to_socket_always_fails(monkeypatch)

    def check_no_autostart(dirname):
        project = Project(dirname)
        result = prepare(project, environ=dict())
        assert not result

    with_directory_contents(
        {PROJECT_FILENAME: """
runtime:
  REDIS_URL: {}
""",
         LOCAL_STATE_DIRECTORY + "/" + LOCAL_STATE_FILENAME: """
runtime:
  REDIS_URL:
    providers:
      RedisProvider:
        scope: system
"""}, check_no_autostart)

    out, err = capsys.readouterr()
    assert out == ""
    assert err == ("Could not connect to system default Redis.\n" +
                   "missing requirement to run this project: A running Redis server, located " +
                   "by a redis: URL set as REDIS_URL\n" + "  Environment variable REDIS_URL is not set.\n")


def test_redis_server_configure_custom_port_range(monkeypatch, capsys):
    can_connect_args_list = _monkeypatch_can_connect_to_socket_always_succeeds_on_nonstandard(monkeypatch)

    def start_local_redis(dirname):
        project = Project(dirname)
        result = prepare(project, environ=dict())
        assert not result
        assert 34 == len(can_connect_args_list)

    with_directory_contents(
        {PROJECT_FILENAME: """
runtime:
  REDIS_URL: {}
    """,
         LOCAL_STATE_DIRECTORY + "/" + LOCAL_STATE_FILENAME: """
runtime:
  REDIS_URL:
    providers:
      RedisProvider:
        port_range: 7389-7421
"""}, start_local_redis)

    out, err = capsys.readouterr()
    assert "All ports from 7389 to 7421 were in use, could not start redis-server on one of them." in err
    assert "REDIS_URL" in err
    assert "missing requirement" in err
    assert "" == out


def _fail_to_prepare_local_redis_server_exec_fails(monkeypatch, capsys, logfile_fail_mode):
    # this test will fail if you don't have Redis installed, since
    # it actually starts it.
    from project.plugins.network_util import can_connect_to_socket as real_can_connect_to_socket

    _monkeypatch_can_connect_to_socket_on_nonstandard_port_only(monkeypatch, real_can_connect_to_socket)

    def start_local_redis(dirname):
        logfile = os.path.join(dirname, ".anaconda/run/project_scoped_redis/redis.log")

        from subprocess import Popen as real_Popen

        failscript = os.path.join(dirname, "fail.py")
        with codecs.open(failscript, 'w', 'utf-8') as file:
            file.write("""
from __future__ import print_function
import codecs
import sys
import os
print('It did not work stdout')
print('It did not work stderr', file=sys.stderr)
logfile = sys.argv[1]
fail_mode = sys.argv[2]
if fail_mode == 'no_logfile':
    pass
elif fail_mode == 'is_dir':
    os.makedirs(logfile)
else:
    with codecs.open(logfile, 'w', 'utf-8') as f:
        f.write('This is in the logfile')
sys.exit(1)
""")

        def mock_Popen(*args, **kwargs):
            if 'args' not in kwargs:
                raise RuntimeError("this mock only works if 'args' provided")
            kwargs['args'] = ['python', failscript, logfile, logfile_fail_mode]
            return real_Popen(*args, **kwargs)

        monkeypatch.setattr("subprocess.Popen", mock_Popen)

        project = Project(dirname)
        result = prepare(project, environ=dict())
        assert not result

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  REDIS_URL: {}
"""}, start_local_redis)

    # this doesn't capture "It did not work stdout" because
    # of some pytest detail I don't understand.
    out, err = capsys.readouterr()

    assert "REDIS_URL" in err
    assert "missing requirement" in err
    # the failed process writes this to stderr, but prepare() moves it to stdout
    assert "Starting " in out
    assert "It did not work stderr" in out
    if logfile_fail_mode == 'logfile_ok':
        assert "This is in the logfile" in out
    else:
        assert "This is in the logfile" not in out
    if logfile_fail_mode == 'is_dir':
        assert "Failed to read" in out
    else:
        assert "Failed to read" not in out


def test_fail_to_prepare_local_redis_server_exec_fails(monkeypatch, capsys):
    _fail_to_prepare_local_redis_server_exec_fails(monkeypatch, capsys, logfile_fail_mode='logfile_ok')


def test_fail_to_prepare_local_redis_server_exec_fails_no_logfile(monkeypatch, capsys):
    _fail_to_prepare_local_redis_server_exec_fails(monkeypatch, capsys, logfile_fail_mode='no_logfile')


def test_fail_to_prepare_local_redis_server_exec_fails_logfile_is_dir(monkeypatch, capsys):
    _fail_to_prepare_local_redis_server_exec_fails(monkeypatch, capsys, logfile_fail_mode='is_dir')


def test_set_scope_in_local_state(monkeypatch):
    can_connect_args = _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch)

    def prepare_after_setting_scope(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        requirement = _redis_requirement()
        provider = RedisProvider()
        config_context = ProviderConfigContext(dict(), local_state, requirement)
        config = provider.read_config(config_context)
        assert config['scope'] == 'all'
        provider.set_config_values_as_strings(config_context, dict(scope='system'))
        config = provider.read_config(config_context)
        assert config['scope'] == 'system'

        project = Project(dirname)
        result = prepare(project, environ=dict())
        assert result
        assert dict(REDIS_URL="redis://localhost:6379", PROJECT_DIR=project.directory_path) == result.environ
        assert dict(host='localhost', port=6379, timeout_seconds=0.5) == can_connect_args

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  REDIS_URL: {}
"""}, prepare_after_setting_scope)
