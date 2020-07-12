# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Redis-related providers."""
from __future__ import print_function

import codecs
import errno
import os
import subprocess
import sys
import time

from anaconda_project.requirements_registry.provider import (EnvVarProvider, ProviderAnalysis,
                                                             shutdown_service_run_state, delete_service_directory)
import anaconda_project.requirements_registry.network_util as network_util
from anaconda_project.provide import PROVIDE_MODE_DEVELOPMENT
from anaconda_project.frontend import _new_error_recorder
from anaconda_project.internal import py2_compat
from anaconda_project.internal import logged_subprocess

_DEFAULT_SYSTEM_REDIS_HOST = "localhost"
_DEFAULT_SYSTEM_REDIS_PORT = 6379
_DEFAULT_SYSTEM_REDIS_URL = "redis://%s:%d" % (_DEFAULT_SYSTEM_REDIS_HOST, _DEFAULT_SYSTEM_REDIS_PORT)


class _RedisProviderAnalysis(ProviderAnalysis):
    """Subtype of ProviderAnalysis with extra fields RedisProvider needs to track."""
    def __init__(self, config, missing_to_configure, missing_to_provide, existing_scoped_instance_url,
                 default_system_exists):
        super(_RedisProviderAnalysis, self).__init__(config, missing_to_configure, missing_to_provide)
        self.existing_scoped_instance_url = existing_scoped_instance_url
        self.default_system_exists = default_system_exists


# future: this should introduce a requirement that redis-server is on path
class RedisProvider(EnvVarProvider):
    """Runs a project-scoped Redis process (each project needing Redis gets its own)."""
    @classmethod
    def _parse_port_range(cls, s):
        pieces = s.split("-")
        if len(pieces) != 2:
            return None
        try:
            lower = int(pieces[0].strip())
            upper = int(pieces[1].strip())
        except ValueError:
            return None
        if lower <= 0 or upper <= 0:
            return None
        if lower > upper:
            return None
        return (lower, upper)

    def _config_section(self, requirement):
        return ["service_options", requirement.env_var]

    def read_config(self, requirement, environ, local_state_file, default_env_spec_name, overrides):
        """Override superclass to return our config."""
        config = super(RedisProvider, self).read_config(requirement, environ, local_state_file, default_env_spec_name,
                                                        overrides)

        assert 'source' in config

        section = self._config_section(requirement)

        scope = local_state_file.get_value(section + ['scope'], default='all')
        if config['source'] == 'unset':
            config['source'] = 'find_' + scope

        default_lower_port = 6380  # one above 6379 default Redis
        default_upper_port = 6449  # entirely arbitrary
        default_port_range = "%d-%d" % (default_lower_port, default_upper_port)
        port_range_string = local_state_file.get_value(section + ['port_range'], default=default_port_range)
        parsed_port_range = self._parse_port_range(port_range_string)
        if parsed_port_range is None:
            print("Invalid port_range '%s', should be like '%s'" % (port_range_string, default_port_range),
                  file=sys.stderr)
            config['lower_port'] = default_lower_port
            config['upper_port'] = default_upper_port
        else:
            config['lower_port'] = parsed_port_range[0]
            config['upper_port'] = parsed_port_range[1]

        return config

    def set_config_values_as_strings(self, requirement, environ, local_state_file, default_env_spec_name, overrides,
                                     values):
        """Override superclass to set our config values."""
        config = self.read_config(requirement, environ, local_state_file, default_env_spec_name, overrides=None)
        section = self._config_section(requirement)
        upper_port = config['upper_port']
        lower_port = config['lower_port']
        if 'lower_port' in values:
            lower_port = values['lower_port']
        if 'upper_port' in values:
            upper_port = values['upper_port']

        local_state_file.set_value(section + ['port_range'], "%s-%s" % (lower_port, upper_port))

        if 'source' in values:
            if values['source'] == 'find_all':
                scope = 'all'
            elif values['source'] == 'find_project':
                scope = 'project'
            elif values['source'] == 'find_system':
                scope = 'system'
            else:
                scope = None
            if scope is not None:
                local_state_file.set_value(section + ['scope'], scope)

            if values['source'] != 'environ':
                # clear out the previous setting; this is sort of a hack. The problem
                # is that we don't want to delete env vars set in actual os.environ on
                # the command line, in our first pass, and in some subtypes of EnvVarProvider
                # (CondaEnvProvider) we also don't want to use it by default. Otherwise
                # we should probably do this in EnvVarProvider. future: rethink this.
                # a possible fix is to track an initial_environ for the whole prepare
                # sequence, separately from the current running environ?
                environ.pop(requirement.env_var, None)

        # set a manually-specified value
        super(RedisProvider, self).set_config_values_as_strings(requirement, environ, local_state_file,
                                                                default_env_spec_name, overrides, values)

    def _previously_run_redis_url_if_alive(self, run_state):
        if 'port' in run_state and network_util.can_connect_to_socket(host='localhost', port=run_state['port']):
            return "redis://localhost:{port}".format(port=run_state['port'])
        else:
            return None

    def _can_connect_to_system_default(self):
        return network_util.can_connect_to_socket(host=_DEFAULT_SYSTEM_REDIS_HOST, port=_DEFAULT_SYSTEM_REDIS_PORT)

    def analyze(self, requirement, environ, local_state_file, default_env_spec_name, overrides):
        """Override superclass to store additional fields in the analysis."""
        analysis = super(RedisProvider, self).analyze(requirement, environ, local_state_file, default_env_spec_name,
                                                      overrides)
        run_state = local_state_file.get_service_run_state(requirement.env_var)
        previous = self._previously_run_redis_url_if_alive(run_state)
        systemwide = self._can_connect_to_system_default()

        return _RedisProviderAnalysis(analysis.config,
                                      analysis.missing_env_vars_to_configure,
                                      analysis.missing_env_vars_to_provide,
                                      existing_scoped_instance_url=previous,
                                      default_system_exists=systemwide)

    def _provide_system(self, requirement, context, frontend):
        if context.status.analysis.default_system_exists:
            frontend.info("Found system default Redis at %s" % _DEFAULT_SYSTEM_REDIS_URL)
            return _DEFAULT_SYSTEM_REDIS_URL

    def _provide_project(self, requirement, context, frontend):
        config = context.status.analysis.config

        def ensure_redis(run_state):
            # this is pretty lame, we'll want to get fancier at a
            # future time (e.g. use Chalmers, stuff like
            # that). The desired semantic is a new copy of Redis
            # dedicated to this project directory; it should not
            # require the user to have set up anything in advance,
            # e.g. if we use Chalmers we should automatically take
            # care of configuring/starting Chalmers itself.
            url = context.status.analysis.existing_scoped_instance_url
            if url is not None:
                frontend.info("Using redis-server we started previously at {url}".format(url=url))
                return url

            run_state.clear()

            workdir = context.ensure_service_directory(requirement.env_var)
            pidfile = os.path.join(workdir, "redis.pid")
            logfile = os.path.join(workdir, "redis.log")

            # 6379 is the default Redis port; leave that one free
            # for a systemwide Redis. Try looking for a port above
            # it. This is a pretty huge hack and a race condition,
            # but Redis doesn't as far as I know have "let the OS
            # pick the port" mode.
            LOWER_PORT = config['lower_port']
            UPPER_PORT = config['upper_port']
            port = LOWER_PORT
            while port <= UPPER_PORT:
                if not network_util.can_connect_to_socket(host='localhost', port=port):
                    break
                port += 1
            if port > UPPER_PORT:
                frontend.error(("All ports from {lower} to {upper} were in use, " +
                                "could not start redis-server on one of them.").format(lower=LOWER_PORT,
                                                                                       upper=UPPER_PORT))
                return None

            # be sure we don't get confused by an old log file
            try:
                os.remove(logfile)
            except IOError:  # pragma: no cover (py3 only)
                pass
            except OSError:  # pragma: no cover (py2 only)
                pass

            command = [
                'redis-server', '--pidfile', pidfile, '--logfile', logfile, '--daemonize', 'yes', '--port',
                str(port)
            ]
            frontend.info("Starting " + repr(command))

            # we don't close_fds=True because on Windows that is documented to
            # keep us from collected stderr. But on Unix it's kinda broken not
            # to close_fds. Hmm.
            try:
                popen = logged_subprocess.Popen(args=command,
                                                stderr=subprocess.PIPE,
                                                env=py2_compat.env_without_unicode(context.environ))
            except Exception as e:
                frontend.error("Error executing redis-server: %s" % (str(e)))
                return None

            # communicate() waits for the process to exit, which
            # is supposed to happen immediately due to --daemonize
            (out, err) = popen.communicate()
            assert out is None  # because we didn't PIPE it
            err = err.decode(errors='replace')

            url = None
            if popen.returncode == 0:
                # now we need to wait for Redis to be ready; we
                # are not sure whether it will create the port or
                # pidfile first, so wait for both.
                port_is_ready = False
                pidfile_is_ready = False
                MAX_WAIT_TIME = 10
                so_far = 0
                while so_far < MAX_WAIT_TIME:
                    increment = MAX_WAIT_TIME / 500.0
                    time.sleep(increment)
                    so_far += increment
                    if not port_is_ready:
                        if network_util.can_connect_to_socket(host='localhost', port=port):
                            port_is_ready = True

                    if not pidfile_is_ready:
                        if os.path.exists(pidfile):
                            pidfile_is_ready = True

                    if port_is_ready and pidfile_is_ready:
                        break

                # if we time out with no pidfile we forge ahead at this point
                if port_is_ready:
                    run_state['port'] = port
                    url = "redis://localhost:{port}".format(port=port)

                    # note: --port doesn't work, only -p, and the failure with --port is silent.
                    run_state['shutdown_commands'] = [['redis-cli', '-p', str(port), 'shutdown']]
                else:
                    frontend.info(
                        "redis-server started successfully, but we timed out trying to connect to it on port %d" %
                        (port))

            if url is None:
                for line in err.split("\n"):
                    if line != "":
                        frontend.info(line)
                try:
                    with codecs.open(logfile, 'r', 'utf-8') as log:
                        for line in log.readlines():
                            frontend.info(line)
                except IOError as e:
                    # just be silent if redis-server failed before creating a log file,
                    # that's fine. Hopefully it had some stderr.
                    if e.errno != errno.ENOENT:
                        frontend.info("Failed to read {logfile}: {error}".format(logfile=logfile, error=e))

                frontend.error(
                    "redis-server process failed or timed out, exited with code {code}".format(code=popen.returncode))

            return url

        return context.transform_service_run_state(requirement.env_var, ensure_redis)

    def provide(self, requirement, context):
        """Override superclass to start a project-scoped redis-server.

        If it locates or starts a redis-server, it sets the
        requirement's env var to that server's URL.

        """
        assert 'PATH' in context.environ

        url = None
        source = context.status.analysis.config['source']

        super_result = super(RedisProvider, self).provide(requirement, context)

        url = context.environ.get(requirement.env_var, None)

        frontend = _new_error_recorder(context.frontend)

        # we jump through a little hoop to avoid a "can't connect to system redis"
        # message if we're going to end up successfully starting a local one.
        system_failed = False
        if url is None and (source == 'find_system' or source == 'find_all'):
            url = self._provide_system(requirement, context, frontend)
            if url is None:
                system_failed = True

        if url is None and (source == 'find_project' or source == 'find_all'):
            # we will only start a local Redis in "dev" mode, not prod or check mode
            if context.mode == PROVIDE_MODE_DEVELOPMENT:
                url = self._provide_project(requirement, context, frontend)

        if url is None:
            if system_failed:
                frontend.error("Could not connect to system default Redis.")
        else:
            context.environ[requirement.env_var] = url

        return super_result.copy_with_additions(errors=frontend.pop_errors())

    def unprovide(self, requirement, environ, local_state_file, overrides, requirement_status=None):
        """Override superclass to shut down any redis-server we started."""
        status = shutdown_service_run_state(local_state_file, requirement.env_var)
        delete_service_directory(local_state_file, requirement.env_var)
        return status
