"""Redis-related providers."""
import codecs
import errno
import os
import subprocess

from project.plugins.provider import Provider
import project.plugins.network_util as network_util


class DefaultRedisProvider(Provider):
    """Provides the default Redis service on localhost port 6379."""

    @property
    def title(self):
        """Override superclass to provide our title."""
        return "Default Redis port on localhost"

    def provide(self, requirement, context):
        """Override superclass to set the requirement's env var to the default Redis localhost URL."""
        context.environ[requirement.env_var] = "redis://localhost:6379"


# future: this should introduce a requirement that redis-server is on path
class ProjectScopedRedisProvider(Provider):
    """Runs a project-scoped Redis process (each project needing Redis gets its own)."""

    @property
    def title(self):
        """Override superclass to provide our title."""
        return "Run a dedicated redis-server process for this project."

    def provide(self, requirement, context):
        """Override superclass to start a project-scoped redis-server.

        If it locates or starts a redis-server, it sets the
        requirement's env var to that server's URL.

        """
        url = None  # this is a hack because yapf adds a blank line here and pep257 hates it

        def ensure_redis(run_state):
            # this is pretty lame, we'll want to get fancier at a
            # future time (e.g. use Chalmers, stuff like
            # that). The desired semantic is a new copy of Redis
            # dedicated to this project directory; it should not
            # require the user to have set up anything in advance,
            # e.g. if we use Chalmers we should automatically take
            # care of configuring/starting Chalmers itself.
            if 'port' in run_state and network_util.can_connect_to_socket(host='localhost', port=run_state['port']):
                url = "redis://localhost:{port}".format(port=run_state['port'])
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
            port = 6380
            UPPER_BOUND_PORT = 6450  # entirely arbitrary
            while port < UPPER_BOUND_PORT:
                if not network_util.can_connect_to_socket(host='localhost', port=port):
                    break
                port += 1
            if port == UPPER_BOUND_PORT:
                context.append_error(("All ports between 6380 and {upper} were in use, " +
                                      "could not start redis-server on one of them.").format(upper=UPPER_BOUND_PORT))
                return None

            # be sure we don't get confused by an old log file
            try:
                os.remove(logfile)
            except IOError:
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

        url = context.transform_service_run_state("project_scoped_redis", ensure_redis)
        if url is not None:
            context.environ[requirement.env_var] = url
