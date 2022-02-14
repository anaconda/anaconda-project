# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import codecs
import os
import platform
import pytest
import sys

from anaconda_project.test.project_utils import project_no_dedicated_env
from anaconda_project.internal.test.tmpfile_utils import (with_directory_contents,
                                                          with_directory_contents_completing_project_file)
from anaconda_project.test.environ_utils import minimal_environ, strip_environ
from anaconda_project.local_state_file import DEFAULT_LOCAL_STATE_FILENAME
from anaconda_project.local_state_file import LocalStateFile
from anaconda_project.requirements_registry.registry import RequirementsRegistry
from anaconda_project.requirements_registry.requirement import UserConfigOverrides
from anaconda_project.requirements_registry.providers.redis import RedisProvider
from anaconda_project.requirements_registry.requirements.redis import RedisRequirement
from anaconda_project.prepare import prepare_without_interaction, unprepare
from anaconda_project import provide
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME
from anaconda_project.internal import conda_api


# This is kind of an awkward way to do it for historical reasons,
# we print out the logs/errors captured by FakeFrontend, instead
# of rewriting the tests in here to have a frontend that prints.
def _prepare_printing_errors(project, environ=None, mode=provide.PROVIDE_MODE_DEVELOPMENT):
    result = prepare_without_interaction(project, environ=environ, mode=mode)
    for message in project.frontend.logs:
        print(message)
    for error in project.frontend.errors:
        print(error, file=sys.stderr)
    if not result:
        assert result.errors == project.frontend.errors
    return result


def _redis_requirement():
    return RedisRequirement(registry=RequirementsRegistry(), env_var="REDIS_URL")


def test_reading_default_config():
    def read_config(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        requirement = _redis_requirement()
        provider = RedisProvider()
        config = provider.read_config(requirement, dict(), local_state, 'default', UserConfigOverrides())
        assert 6380 == config['lower_port']
        assert 6449 == config['upper_port']

    with_directory_contents(dict(), read_config)


def test_reading_valid_config():
    def read_config(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        requirement = _redis_requirement()
        provider = RedisProvider()
        config = provider.read_config(requirement, dict(), local_state, 'default', UserConfigOverrides())
        assert 7389 == config['lower_port']
        assert 7421 == config['upper_port']
        assert 'find_all' == config['source']

    with_directory_contents(
        {
            DEFAULT_LOCAL_STATE_FILENAME:
            """
service_options:
  REDIS_URL:
    port_range: 7389-7421
    autostart: false
         """
        }, read_config)


def _read_invalid_port_range(capsys, port_range):
    def read_config(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        requirement = _redis_requirement()
        provider = RedisProvider()
        config = provider.read_config(requirement, dict(), local_state, 'default', UserConfigOverrides())
        # revert to defaults
        assert 6380 == config['lower_port']
        assert 6449 == config['upper_port']
        # should have printed an error
        out, err = capsys.readouterr()
        assert ("Invalid port_range '%s', should be like '6380-6449'\n" % (port_range)) == err

    with_directory_contents(
        {DEFAULT_LOCAL_STATE_FILENAME: """
service_options:
  REDIS_URL:
    port_range: %s
         """ % port_range}, read_config)


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
        provider.set_config_values_as_strings(requirement, dict(), local_state, 'default', UserConfigOverrides(),
                                              dict(lower_port="6001"))
        config = provider.read_config(requirement, dict(), local_state, 'default', UserConfigOverrides())
        assert config['lower_port'] == 6001
        assert config['upper_port'] == 6449

        provider.set_config_values_as_strings(requirement, dict(), local_state, 'default', UserConfigOverrides(),
                                              dict(upper_port="6700"))
        config2 = provider.read_config(requirement, dict(), local_state, 'default', UserConfigOverrides())
        assert config2['lower_port'] == 6001
        assert config2['upper_port'] == 6700

        provider.set_config_values_as_strings(requirement, dict(), local_state, 'default', UserConfigOverrides(),
                                              dict(lower_port="5500", upper_port="6800"))
        config2 = provider.read_config(requirement, dict(), local_state, 'default', UserConfigOverrides())
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

    monkeypatch.setattr("anaconda_project.requirements_registry.network_util.can_connect_to_socket",
                        mock_can_connect_to_socket)

    return can_connect_args


def test_prepare_redis_url_with_dict_in_variables_section(monkeypatch):
    can_connect_args = _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch)

    def prepare_redis_url(dirname):
        project = project_no_dedicated_env(dirname)
        result = _prepare_printing_errors(project, environ=minimal_environ())
        assert result
        assert dict(REDIS_URL="redis://localhost:6379",
                    PROJECT_DIR=project.directory_path) == strip_environ(result.environ)
        assert dict(host='localhost', port=6379, timeout_seconds=0.5) == can_connect_args

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
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

    monkeypatch.setattr("anaconda_project.requirements_registry.network_util.can_connect_to_socket",
                        mock_can_connect_to_socket)

    return can_connect_args_list


@pytest.mark.skipif(platform.system() == 'Windows', reason='Windows has a hard time with read-only directories')
@pytest.mark.skipif(conda_api.current_platform() == 'osx-arm64', reason='We cannot install redis server on osx-arm64')
def test_prepare_and_unprepare_local_redis_server(monkeypatch):
    from anaconda_project.requirements_registry.network_util import can_connect_to_socket as real_can_connect_to_socket

    can_connect_args_list = _monkeypatch_can_connect_to_socket_on_nonstandard_port_only(
        monkeypatch, real_can_connect_to_socket)

    def start_local_redis(dirname):
        project = project_no_dedicated_env(dirname)
        result = _prepare_printing_errors(project, environ=minimal_environ())
        assert result

        local_state_file = LocalStateFile.load_for_directory(dirname)
        state = local_state_file.get_service_run_state('REDIS_URL')
        assert 'port' in state
        port = state['port']

        assert dict(REDIS_URL=("redis://localhost:" + str(port)),
                    PROJECT_DIR=project.directory_path) == strip_environ(result.environ)
        assert len(can_connect_args_list) >= 2

        servicedir = os.path.join(dirname, "services")
        redisdir = os.path.join(servicedir, "REDIS_URL")

        pidfile = os.path.join(redisdir, "redis.pid")
        logfile = os.path.join(redisdir, "redis.log")
        assert os.path.exists(pidfile)
        assert os.path.exists(logfile)

        assert real_can_connect_to_socket(host='localhost', port=port)

        # now clean it up
        status = unprepare(project, result)
        assert status

        assert not os.path.exists(pidfile)
        assert not os.path.exists(logfile)
        assert not os.path.exists(redisdir)
        assert not os.path.exists(servicedir)
        assert not real_can_connect_to_socket(host='localhost', port=port)

        local_state_file.load()
        assert dict() == local_state_file.get_service_run_state("REDIS_URL")

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, start_local_redis)


@pytest.mark.skipif(platform.system() == 'Windows', reason='Windows has a hard time with read-only directories')
@pytest.mark.skipif(conda_api.current_platform() == 'osx-arm64', reason='We cannot install redis server on osx-arm64')
def test_prepare_and_unprepare_local_redis_server_with_failed_unprovide(monkeypatch):
    from anaconda_project.requirements_registry.network_util import can_connect_to_socket as real_can_connect_to_socket

    _monkeypatch_can_connect_to_socket_on_nonstandard_port_only(monkeypatch, real_can_connect_to_socket)

    def start_local_redis(dirname):
        project = project_no_dedicated_env(dirname)
        result = _prepare_printing_errors(project, environ=minimal_environ())
        assert result

        # now clean it up, but arrange for that to fail
        local_state_file = LocalStateFile.load_for_directory(dirname)
        local_state_file.set_service_run_state('REDIS_URL', {'shutdown_commands': [['false']]})
        local_state_file.save()
        status = unprepare(project, result)
        assert not status
        assert status.status_description == 'Shutdown commands failed for REDIS_URL.'

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, start_local_redis)


@pytest.mark.skipif(platform.system() == 'Windows', reason='Windows has a hard time with read-only directories')
@pytest.mark.skipif(conda_api.current_platform() == 'osx-arm64', reason='We cannot install redis server on osx-arm64')
def test_prepare_and_unprepare_two_local_redis_servers_with_failed_unprovide(monkeypatch):
    from anaconda_project.requirements_registry.network_util import can_connect_to_socket as real_can_connect_to_socket

    _monkeypatch_can_connect_to_socket_on_nonstandard_port_only(monkeypatch, real_can_connect_to_socket)

    def start_local_redis(dirname):
        project = project_no_dedicated_env(dirname)
        result = _prepare_printing_errors(project, environ=minimal_environ())
        assert result

        # now clean it up, but arrange for that to double-fail
        local_state_file = LocalStateFile.load_for_directory(dirname)
        local_state_file.set_service_run_state('REDIS_URL', {'shutdown_commands': [['false']]})
        local_state_file.set_service_run_state('REDIS_URL_2', {'shutdown_commands': [['false']]})
        local_state_file.save()
        status = unprepare(project, result)
        assert not status
        assert status.status_description == 'Failed to clean up REDIS_URL, REDIS_URL_2.'

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
  REDIS_URL_2: redis
"""}, start_local_redis)


@pytest.mark.skipif(platform.system() == 'Windows', reason='Windows has a hard time with read-only directories')
@pytest.mark.skipif(conda_api.current_platform() == 'osx-arm64', reason='We cannot install redis server on osx-arm64')
def test_prepare_local_redis_server_twice_reuses(monkeypatch):
    from anaconda_project.requirements_registry.network_util import can_connect_to_socket as real_can_connect_to_socket

    can_connect_args_list = _monkeypatch_can_connect_to_socket_on_nonstandard_port_only(
        monkeypatch, real_can_connect_to_socket)

    def start_local_redis(dirname):
        project = project_no_dedicated_env(dirname)
        result = _prepare_printing_errors(project, environ=minimal_environ())
        assert result
        assert 'REDIS_URL' in result.environ

        local_state_file = LocalStateFile.load_for_directory(dirname)
        state = local_state_file.get_service_run_state("REDIS_URL")
        assert 'port' in state
        port = state['port']

        assert dict(REDIS_URL=("redis://localhost:" + str(port)),
                    PROJECT_DIR=project.directory_path) == strip_environ(result.environ)
        assert len(can_connect_args_list) >= 2

        pidfile = os.path.join(dirname, "services/REDIS_URL/redis.pid")
        logfile = os.path.join(dirname, "services/REDIS_URL/redis.log")
        assert os.path.exists(pidfile)
        assert os.path.exists(logfile)

        assert real_can_connect_to_socket(host='localhost', port=port)

        # be sure we generate the config html that would use the old one
        requirement = _redis_requirement()
        status = requirement.check_status(result.environ, local_state_file, 'default', UserConfigOverrides())

        # now try again, and we should re-use the exact same server
        pidfile_mtime = os.path.getmtime(pidfile)
        with codecs.open(pidfile, 'r', 'utf-8') as file:
            pidfile_content = file.read()
        result2 = _prepare_printing_errors(project, environ=minimal_environ())
        assert result2

        # port should be the same, and set in the environment
        assert dict(REDIS_URL=("redis://localhost:" + str(port)),
                    PROJECT_DIR=project.directory_path) == strip_environ(result2.environ)

        # no new pid file
        assert pidfile_mtime == os.path.getmtime(pidfile)
        with codecs.open(pidfile, 'r', 'utf-8') as file:
            pidfile_content2 = file.read()
        assert pidfile_content == pidfile_content2

        # now clean it up
        status = unprepare(project, result2)
        assert status

        assert not os.path.exists(pidfile)
        assert not real_can_connect_to_socket(host='localhost', port=port)

        local_state_file.load()
        assert dict() == local_state_file.get_service_run_state("REDIS_URL")

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, start_local_redis)


@pytest.mark.skipif(platform.system() == 'Windows', reason='Windows has a hard time with read-only directories')
@pytest.mark.skipif(conda_api.current_platform() == 'osx-arm64', reason='We cannot install redis server on osx-arm64')
def test_prepare_local_redis_server_times_out(monkeypatch, capsys):
    from anaconda_project.requirements_registry.network_util import can_connect_to_socket as real_can_connect_to_socket

    _monkeypatch_can_connect_to_socket_on_nonstandard_port_only(monkeypatch, real_can_connect_to_socket)

    def start_local_redis_and_time_out(dirname):
        project = project_no_dedicated_env(dirname)

        from time import sleep as real_sleep

        killed = {}

        def mock_sleep_kills_redis(seconds):
            # first time the Redis provider sleeps to wait for the
            # server to appear, we kill the server; after that
            # we make sleep into a no-op so we rapidly time out.
            if 'done' in killed:
                return

            pidfile = os.path.join(dirname, "services", "REDIS_URL", "redis.pid")
            count = 0
            while count < 15:
                if os.path.exists(pidfile):
                    break
                real_sleep(0.1)
                count = count + 1

            assert os.path.exists(pidfile)

            with codecs.open(pidfile, 'r', 'utf-8') as f:
                for line in f.readlines():
                    try:
                        import signal
                        os.kill(int(line.strip()), signal.SIGKILL)
                    except Exception:
                        pass

            # be sure it's gone
            real_sleep(0.1)
            killed['done'] = True

        monkeypatch.setattr('time.sleep', mock_sleep_kills_redis)

        result = _prepare_printing_errors(project, environ=minimal_environ())
        assert not result

        out, err = capsys.readouterr()
        assert "redis-server started successfully, but we timed out trying to connect to it on port" in out
        assert "redis-server process failed or timed out, exited with code 0" in err

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, start_local_redis_and_time_out)


def _monkeypatch_can_connect_to_socket_always_succeeds_on_nonstandard(monkeypatch):
    can_connect_args_list = []

    def mock_can_connect_to_socket(host, port, timeout_seconds=0.5):
        can_connect_args = dict()
        can_connect_args['host'] = host
        can_connect_args['port'] = port
        can_connect_args['timeout_seconds'] = timeout_seconds
        can_connect_args_list.append(can_connect_args)
        return port != 6379

    monkeypatch.setattr("anaconda_project.requirements_registry.network_util.can_connect_to_socket",
                        mock_can_connect_to_socket)

    return can_connect_args_list


def test_fail_to_prepare_local_redis_server_no_port_available(monkeypatch, capsys):
    can_connect_args_list = _monkeypatch_can_connect_to_socket_always_succeeds_on_nonstandard(monkeypatch)

    def start_local_redis(dirname):
        project = project_no_dedicated_env(dirname)
        result = _prepare_printing_errors(project, environ=minimal_environ())
        assert not result
        assert 73 == len(can_connect_args_list)

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, start_local_redis)

    out, err = capsys.readouterr()
    assert "All ports from 6380 to 6449 were in use, could not start redis-server on one of them." in err
    assert "REDIS_URL" in err
    assert "missing requirement" in err
    assert "" == out


def test_do_not_start_local_redis_server_in_prod_mode(monkeypatch, capsys):
    can_connect_args_list = _monkeypatch_can_connect_to_socket_always_succeeds_on_nonstandard(monkeypatch)

    def no_start_local_redis(dirname):
        project = project_no_dedicated_env(dirname)
        result = _prepare_printing_errors(project, environ=minimal_environ(), mode=provide.PROVIDE_MODE_PRODUCTION)
        assert not result
        assert 3 == len(can_connect_args_list)

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, no_start_local_redis)

    out, err = capsys.readouterr()
    assert "Could not connect to system default Redis." in err
    assert "REDIS_URL" in err
    assert "missing requirement" in err
    assert "" == out


def test_do_not_start_local_redis_server_in_check_mode(monkeypatch, capsys):
    can_connect_args_list = _monkeypatch_can_connect_to_socket_always_succeeds_on_nonstandard(monkeypatch)

    def no_start_local_redis(dirname):
        project = project_no_dedicated_env(dirname)
        result = _prepare_printing_errors(project, environ=minimal_environ(), mode=provide.PROVIDE_MODE_CHECK)
        assert not result
        assert 3 == len(can_connect_args_list)

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, no_start_local_redis)

    out, err = capsys.readouterr()
    assert "Could not connect to system default Redis." in err
    assert "REDIS_URL" in err
    assert "missing requirement" in err
    assert "" == out


def _monkeypatch_can_connect_to_socket_always_fails(monkeypatch):
    def mock_can_connect_to_socket(host, port, timeout_seconds=0.5):
        return False

    monkeypatch.setattr("anaconda_project.requirements_registry.network_util.can_connect_to_socket",
                        mock_can_connect_to_socket)


def test_fail_to_prepare_local_redis_server_scope_system(monkeypatch, capsys):
    _monkeypatch_can_connect_to_socket_always_fails(monkeypatch)

    def check_no_autostart(dirname):
        project = project_no_dedicated_env(dirname)
        result = _prepare_printing_errors(project, environ=minimal_environ())
        assert not result

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
""",
            DEFAULT_LOCAL_STATE_FILENAME: """
service_options:
  REDIS_URL:
    scope: system
"""
        }, check_no_autostart)

    out, err = capsys.readouterr()
    assert out == ""
    assert err == (
        "Could not connect to system default Redis.\n" +
        "missing requirement to run this project: A running Redis server, located by a redis: URL set as REDIS_URL.\n" +
        "  Environment variable REDIS_URL is not set.\n")


def test_redis_server_configure_custom_port_range(monkeypatch, capsys):
    can_connect_args_list = _monkeypatch_can_connect_to_socket_always_succeeds_on_nonstandard(monkeypatch)

    def start_local_redis(dirname):
        project = project_no_dedicated_env(dirname)
        result = _prepare_printing_errors(project, environ=minimal_environ())
        assert not result
        assert 36 == len(can_connect_args_list)

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
    """,
            DEFAULT_LOCAL_STATE_FILENAME: """
service_options:
  REDIS_URL:
    port_range: 7389-7421
"""
        }, start_local_redis)

    out, err = capsys.readouterr()
    assert "All ports from 7389 to 7421 were in use, could not start redis-server on one of them." in err
    assert "REDIS_URL" in err
    assert "missing requirement" in err
    assert "" == out


def _fail_to_prepare_local_redis_server_exec_fails(monkeypatch, capsys, logfile_fail_mode):
    # this test will fail if you don't have Redis installed, since
    # it actually starts it.
    from anaconda_project.requirements_registry.network_util import can_connect_to_socket as real_can_connect_to_socket

    _monkeypatch_can_connect_to_socket_on_nonstandard_port_only(monkeypatch, real_can_connect_to_socket)

    def start_local_redis(dirname):
        logfile = os.path.join(dirname, "services/REDIS_URL/redis.log")

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
                # `pip list` goes through this codepath while redis launch
                # happens to specify args= as a kwarg
                assert 'pip' in args[0][0]
                return real_Popen(*args, **kwargs)
            kwargs['args'] = ['python', failscript, logfile, logfile_fail_mode]
            return real_Popen(*args, **kwargs)

        monkeypatch.setattr("subprocess.Popen", mock_Popen)

        project = project_no_dedicated_env(dirname)
        result = _prepare_printing_errors(project, environ=minimal_environ())
        assert not result

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
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


def test_fail_to_prepare_local_redis_server_not_on_path(monkeypatch, capsys):
    from anaconda_project.requirements_registry.network_util import can_connect_to_socket as real_can_connect_to_socket

    _monkeypatch_can_connect_to_socket_on_nonstandard_port_only(monkeypatch, real_can_connect_to_socket)

    def start_local_redis(dirname):
        from subprocess import Popen as real_Popen

        def mock_Popen(*args, **kwargs):
            if 'args' not in kwargs:
                # `pip list` goes through this codepath while redis launch
                # happens to specify args= as a kwarg
                assert 'pip' in args[0][0]
                return real_Popen(*args, **kwargs)
            kwargs['args'] = ['this-is-not-on-the-path']
            return real_Popen(*args, **kwargs)

        monkeypatch.setattr("subprocess.Popen", mock_Popen)

        project = project_no_dedicated_env(dirname)
        result = _prepare_printing_errors(project, environ=minimal_environ())
        assert not result

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, start_local_redis)

    # this doesn't capture "It did not work stdout" because
    # of some pytest detail I don't understand.
    out, err = capsys.readouterr()

    assert "REDIS_URL" in err
    assert "missing requirement" in err
    assert "Error executing redis-server: " in err


def test_set_scope_in_local_state(monkeypatch):
    can_connect_args = _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch)

    def prepare_after_setting_scope(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        requirement = _redis_requirement()
        provider = RedisProvider()
        environ = minimal_environ()
        config = provider.read_config(requirement, environ, local_state, 'default', UserConfigOverrides())
        assert config['source'] == 'find_all'
        provider.set_config_values_as_strings(requirement, environ, local_state, 'default', UserConfigOverrides(),
                                              dict(source='find_project'))
        config = provider.read_config(requirement, environ, local_state, 'default', UserConfigOverrides())
        assert config['source'] == 'find_project'
        provider.set_config_values_as_strings(requirement, environ, local_state, 'default', UserConfigOverrides(),
                                              dict(source='find_all'))
        config = provider.read_config(requirement, environ, local_state, 'default', UserConfigOverrides())
        assert config['source'] == 'find_all'
        provider.set_config_values_as_strings(requirement, environ, local_state, 'default', UserConfigOverrides(),
                                              dict(source='environ'))
        config = provider.read_config(requirement, environ, local_state, 'default', UserConfigOverrides())
        assert config['source'] == 'find_all'  # default if no env var set
        provider.set_config_values_as_strings(requirement, environ, local_state, 'default', UserConfigOverrides(),
                                              dict(source='environ'))
        environ_with_redis_url = environ.copy()
        environ_with_redis_url['REDIS_URL'] = 'blah'
        config = provider.read_config(requirement, environ_with_redis_url, local_state, 'default',
                                      UserConfigOverrides())
        assert config['source'] == 'environ'  # default when the env var IS set

        # use local variable when env var not set
        provider.set_config_values_as_strings(requirement, environ, local_state, 'default', UserConfigOverrides(),
                                              dict(source='variables', value='foo'))
        config = provider.read_config(requirement, environ, local_state, 'default', UserConfigOverrides())
        assert config['source'] == 'variables'
        assert config['value'] == 'foo'

        # use local variable when env var _is_ set
        provider.set_config_values_as_strings(requirement, environ_with_redis_url, local_state, 'default',
                                              UserConfigOverrides(), dict(source='variables', value='foo'))
        config = provider.read_config(requirement, environ, local_state, 'default', UserConfigOverrides())
        assert config['source'] == 'variables'
        assert config['value'] == 'foo'

        # set to use system, which should override using the local state
        provider.set_config_values_as_strings(requirement, environ, local_state, 'default', UserConfigOverrides(),
                                              dict(source='find_system'))
        config = provider.read_config(requirement, environ, local_state, 'default', UserConfigOverrides())
        assert config['source'] == 'find_system'

        project = project_no_dedicated_env(dirname)
        result = _prepare_printing_errors(project, environ=minimal_environ())
        assert result
        assert dict(REDIS_URL="redis://localhost:6379",
                    PROJECT_DIR=project.directory_path) == strip_environ(result.environ)
        assert dict(host='localhost', port=6379, timeout_seconds=0.5) == can_connect_args

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, prepare_after_setting_scope)
