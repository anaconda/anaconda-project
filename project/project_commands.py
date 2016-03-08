"""Class representing a command from the project file."""
from __future__ import absolute_import

from copy import copy
from distutils.spawn import find_executable

import os
import sys


class CommandExecInfo(object):
    """Class describing an executable command."""

    def __init__(self, cwd, args, shell, env):
        """Construct a CommandExecInfo."""
        self._cwd = cwd
        self._args = args
        self._shell = shell
        self._env = env

    @property
    def cwd(self):
        """Working directory to run the command in."""
        return self._cwd

    @property
    def args(self):
        """Command line argument vector to run the command."""
        return self._args

    @property
    def shell(self):
        """Whether the command should be run with shell=True."""
        return self._shell

    @property
    def env(self):
        """Environment to run the command in."""
        return self._env

    def popen(self, **kwargs):
        """Convenience method runs the command using Popen.

        Args:
            kwargs: passed through to Popen

        Returns:
            Popen instance
        """
        import subprocess

        return subprocess.Popen(args=self._args, env=self._env, cwd=self._cwd, shell=self._shell, **kwargs)

    def execvpe(self):
        """Convenience method exec's the command replacing the current process.

        Returns:
            Does not return. May raise an OSError though.
        """
        args = copy(self._args)
        if self._shell:
            import platform
            if platform.system() == 'Windows':
                # The issue here is that in Lib/subprocess.py in
                # the Python distribution, if shell=True the code
                # jumps through some funky hoops setting flags on
                # the Windows API calls. We can't easily simulate
                # that for execvpe.  Not sure what to do.
                raise RuntimeError("Cannot exec with a shell on Windows")
            else:
                # this is all shell=True does on unix
                args = ['/bin/sh', '-c'] + args

        try:
            old_dir = os.getcwd()
            os.chdir(self._cwd)
            sys.stderr.flush()
            sys.stdout.flush()
            os.execvpe(args[0], args, self._env)
        finally:
            # avoid side effect if exec fails (or is mocked in tests)
            os.chdir(old_dir)


class ProjectCommand(object):
    """Represents an command from the project file."""

    def __init__(self, name, attributes):
        """Construct a command with the given attributes.

        Args:
            name (str): name of the command
            attributes (dict): named attributes of the command
        """
        self._name = name
        self._attributes = attributes.copy()

    @property
    def name(self):
        """Get name of the command."""
        return self._name

    def exec_info_for_environment(self, environ):
        """Get a ``CommandExecInfo`` ready to be executed.

        Args:
            environ (dict): the environment containing a CONDA_ENV_PATH, PATH, and PROJECT_DIR
        Returns:
            argv as list of strings
        """
        for name in ('CONDA_ENV_PATH', 'PATH', 'PROJECT_DIR'):
            if name not in environ:
                raise ValueError("To get a runnable command for the app, %s must be set." % (name))

        args = None
        shell = False

        # see conda.misc::launch for what we're copying
        app_entry = self._attributes.get('conda_app_entry', None)
        if app_entry is not None:
            # conda.misc uses plain split and not shlex or
            # anything like that, we need to match its
            # interpretation
            parsed = app_entry.split()
            args = []
            for arg in parsed:
                if '${PREFIX}' in arg:
                    arg = arg.replace('${PREFIX}', environ['CONDA_ENV_PATH'])
                args.append(arg)

        # this should have been validated when loading the project file
        assert args is not None

        # always look in the project directory. This is a little
        # odd because we don't add PROJECT_DIR to PATH for child
        # processes - maybe we should?
        path = os.pathsep.join([environ['PROJECT_DIR'], environ['PATH']])
        executable = find_executable(args[0], path)
        if executable is not None:
            # if the executable is in cwd, for some reason find_executable does not
            # return the full path to it, just a relative path.
            args[0] = os.path.abspath(executable)
        # if we didn't find args[0] on the path, we leave it as-is
        # and wait for it to fail when we later try to run it.

        # conda.misc.launch() uses the home directory
        # instead of the project directory as cwd when
        # running an installed package, but for our
        # purposes where we know we have a project dir
        # that's user-interesting, project directory seems
        # more useful. This way apps can for example find
        # sample data files relative to the project
        # directory.
        return CommandExecInfo(cwd=environ['PROJECT_DIR'], args=args, env=environ, shell=shell)
