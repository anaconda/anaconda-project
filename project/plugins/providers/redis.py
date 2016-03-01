"""Redis-related providers."""
from __future__ import print_function

import codecs
import errno
import os
import subprocess
import sys

from project.plugins.provider import Provider
import project.plugins.network_util as network_util

_DEFAULT_SYSTEM_REDIS_HOST = "localhost"
_DEFAULT_SYSTEM_REDIS_PORT = 6379
_DEFAULT_SYSTEM_REDIS_URL = "redis://%s:%d" % (_DEFAULT_SYSTEM_REDIS_HOST, _DEFAULT_SYSTEM_REDIS_PORT)


# future: this should introduce a requirement that redis-server is on path
class RedisProvider(Provider):
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

    def read_config(self, context):
        """Override superclass to return our config."""
        config = dict()
        section = self.config_section(context.requirement)
        default_lower_port = 6380  # one above 6379 default Redis
        default_upper_port = 6449  # entirely arbitrary
        default_port_range = "%d-%d" % (default_lower_port, default_upper_port)
        port_range_string = context.local_state_file.get_value(section + ['port_range'], default=default_port_range)
        parsed_port_range = self._parse_port_range(port_range_string)
        if parsed_port_range is None:
            print("Invalid port_range '%s', should be like '%s'" % (port_range_string, default_port_range),
                  file=sys.stderr)
            config['lower_port'] = default_lower_port
            config['upper_port'] = default_upper_port
        else:
            config['lower_port'] = parsed_port_range[0]
            config['upper_port'] = parsed_port_range[1]

        config['scope'] = context.local_state_file.get_value(section + ['scope'], default='all')

        return config

    def set_config_values_as_strings(self, context, values):
        """Override superclass to set our config values."""
        config = self.read_config(context)
        section = self.config_section(context.requirement)
        upper_port = config['upper_port']
        lower_port = config['lower_port']
        if 'lower_port' in values:
            lower_port = values['lower_port']
        if 'upper_port' in values:
            upper_port = values['upper_port']

        context.local_state_file.set_value(section + ['port_range'], "%s-%s" % (lower_port, upper_port))

        if 'scope' in values:
            context.local_state_file.set_value(section + ['scope'], values['scope'])

    def _previously_run_redis_url_if_alive(self, run_state):
        if 'port' in run_state and network_util.can_connect_to_socket(host='localhost', port=run_state['port']):
            return "redis://localhost:{port}".format(port=run_state['port'])
        else:
            return None

    def _can_connect_to_system_default(self):
        return network_util.can_connect_to_socket(host=_DEFAULT_SYSTEM_REDIS_HOST, port=_DEFAULT_SYSTEM_REDIS_PORT)

    def config_html(self, context, status):
        """Override superclass to provide our config html."""
        run_state = context.local_state_file.get_service_run_state(self.config_key)
        previous = self._previously_run_redis_url_if_alive(run_state)
        systemwide = self._can_connect_to_system_default()

        if systemwide:
            system_option = """
  <div>
    <label><input type="radio" name="scope" value="system"/>Always use system default Redis on %s port %d</label>
  </div>
""" % (_DEFAULT_SYSTEM_REDIS_HOST, _DEFAULT_SYSTEM_REDIS_PORT)
        else:
            system_option = ""

        if previous is not None:
            project_option = "Use the redis-server we started earlier at %s" % (previous)
        else:
            project_option = """Always start a
   project-dedicated redis-server, using a port between <input type="text" name="lower_port"/>
   and <input type="text" name="upper_port"/>
"""

        return """
<form>
  <div>
    <label><input type="radio" name="scope" value="all"/>Use system default Redis when it's running,
        otherwise start our own redis-server</label>
  </div>
  %s
  <div>
    <label><input type="radio" name="scope" value="project"/>%s</label>
  </div>
</form>
""" % (system_option, project_option)

    def _provide_system(self, requirement, context):
        if self._can_connect_to_system_default():
            context.append_log("Found system default Redis at %s" % _DEFAULT_SYSTEM_REDIS_URL)
            return _DEFAULT_SYSTEM_REDIS_URL
        else:
            context.append_error("Could not connect to system default Redis.")

    def _provide_project(self, requirement, context):
        def ensure_redis(run_state):
            # this is pretty lame, we'll want to get fancier at a
            # future time (e.g. use Chalmers, stuff like
            # that). The desired semantic is a new copy of Redis
            # dedicated to this project directory; it should not
            # require the user to have set up anything in advance,
            # e.g. if we use Chalmers we should automatically take
            # care of configuring/starting Chalmers itself.
            url = self._previously_run_redis_url_if_alive(run_state)
            if url is not None:
                context.append_log("Using redis-server we started previously at {url}".format(url=url))
                return url

            run_state.clear()

            workdir = context.ensure_work_directory("project_scoped_redis")
            pidfile = os.path.join(workdir, "redis.pid")
            logfile = os.path.join(workdir, "redis.log")

            # 6379 is the default Redis port; leave that one free
            # for a systemwide Redis. Try looking for a port above
            # it. This is a pretty huge hack and a race condition,
            # but Redis doesn't as far as I know have "let the OS
            # pick the port" mode.
            LOWER_PORT = context.config['lower_port']
            UPPER_PORT = context.config['upper_port']
            port = LOWER_PORT
            while port <= UPPER_PORT:
                if not network_util.can_connect_to_socket(host='localhost', port=port):
                    break
                port += 1
            if port > UPPER_PORT:
                context.append_error(("All ports from {lower} to {upper} were in use, " +
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

            command = ['redis-server', '--pidfile', pidfile, '--logfile', logfile, '--daemonize', 'yes', '--port',
                       str(port)]
            context.append_log("Starting " + repr(command))

            # we don't close_fds=True because on Windows that is documented to
            # keep us from collected stderr. But on Unix it's kinda broken not
            # to close_fds. Hmm.
            popen = subprocess.Popen(args=command, stderr=subprocess.PIPE, env=context.environ)
            # communicate() waits for the process to exit, which
            # is supposed to happen immediately due to --daemonize
            (out, err) = popen.communicate()
            assert out is None  # because we didn't PIPE it
            err = err.decode(errors='replace')

            if popen.returncode != 0:
                for line in err.split("\n"):
                    if line != "":
                        context.append_log(line)
                try:
                    with codecs.open(logfile, 'r', 'utf-8') as log:
                        for line in log.readlines():
                            context.append_log(line)
                except IOError as e:
                    # just be silent if redis-server failed before creating a log file,
                    # that's fine. Hopefully it had some stderr.
                    if e.errno != errno.ENOENT:
                        context.append_log("Failed to read {logfile}: {error}".format(logfile=logfile, error=e))

                context.append_error("redis-server process failed, exited " + "with code {code}".format(
                    code=popen.returncode))
                return None
            else:
                run_state['port'] = port
                url = "redis://localhost:{port}".format(port=port)

                # note: --port doesn't work, only -p, and the failure with --port is silent.
                run_state['shutdown_commands'] = [['redis-cli', '-p', str(port), 'shutdown']]

                return url

        return context.transform_service_run_state(self.config_key, ensure_redis)

    def provide(self, requirement, context):
        """Override superclass to start a project-scoped redis-server.

        If it locates or starts a redis-server, it sets the
        requirement's env var to that server's URL.

        """
        url = None
        scope = context.config['scope']

        if scope == 'system' or scope == 'all':
            url = self._provide_system(requirement, context)

        if url is None and (scope == 'project' or scope == 'all'):
            url = self._provide_project(requirement, context)

        if url is not None:
            context.environ[requirement.env_var] = url
