# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Class representing a command from the project file."""
from __future__ import absolute_import

from copy import copy
from distutils.spawn import find_executable

import os
import platform
import sys

from conda_kapsel.internal import conda_api

try:  # pragma: no cover
    from shlex import quote  # pragma: no cover
except ImportError:  # pragma: no cover
    from pipes import quote  # pragma: no cover


def _is_windows():
    # it's tempting to cache this but it hoses our test monkeypatching so don't.
    # or at least be aware you'll have to fix tests...
    return (platform.system() == 'Windows')


class CommandExecInfo(object):
    """Class describing an executable command."""

    def __init__(self, cwd, args, shell, env, notebook=None, bokeh_app=None):
        """Construct a CommandExecInfo."""
        self._cwd = cwd
        self._args = args
        self._shell = shell
        self._env = env
        self._notebook = notebook
        self._bokeh_app = bokeh_app
        assert shell is False or len(args) == 1

    @property
    def cwd(self):
        """Working directory to run the command in."""
        return self._cwd

    @property
    def args(self):
        """Command line argument vector to run the command.

        If the ``shell`` property is True, then pass args[0] as a string to Popen,
        rather than this entire list of args.
        """
        return self._args

    @property
    def shell(self):
        """Whether the command should be run with shell=True."""
        return self._shell

    @property
    def env(self):
        """Environment to run the command in."""
        return self._env

    @property
    def notebook(self):
        """Notebook filename relative to project directory, or None."""
        return self._notebook

    @property
    def bokeh_app(self):
        """Bokeh app filename relative to project directory, or None."""
        return self._bokeh_app

    def popen(self, **kwargs):
        """Convenience method runs the command using Popen.

        Args:
            kwargs: passed through to Popen

        Returns:
            Popen instance
        """
        import subprocess

        if self._shell:
            # on Windows, with shell=True Python interprets the args as NOT quoted
            # and quotes them, but assumes a single string parameter is pre-quoted
            # which is what we want.
            # on Unix, with shell=True we interpret args[0]
            # the same as a single string (it's the parameter after -c in sh -c)
            # and anything after args[0] is passed as another flag to sh.
            # (we never have anything after args[0])
            # So if we always use the single string to popen when shell=True, things
            # should work OK on all platforms.
            assert len(self._args) == 1
            args = self._args[0]
        else:

            args = self._args
        return subprocess.Popen(args=args, env=self._env, cwd=self._cwd, shell=self._shell, **kwargs)

    def execvpe(self):
        """Convenience method exec's the command replacing the current process.

        Returns:
            Does not return. May raise an OSError though.
        """
        args = copy(self._args)
        if self._shell:
            assert len(args) == 1
            if _is_windows():
                # The issue here is that in Lib/subprocess.py in
                # the Python distribution, if shell=True the code
                # jumps through some funky hoops setting flags on
                # the Windows API calls. We need to do that, rather
                # than calling os.execvpe which doesn't let us set those
                # flags. So we spawn the child and then exit.
                self.popen()
                sys.exit(0)
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


def _append_extra_args_to_command_line(command, extra_args):
    if extra_args is None:
        return command
    else:
        if _is_windows():  # pragma: no cover
            from conda_kapsel.internal.windows_cmdline import (windows_split_command_line, windows_join_command_line)
            args = windows_split_command_line(command)
            return windows_join_command_line(args + extra_args)
        else:
            new_command = command
            for arg in extra_args:
                new_command = new_command + " " + quote(arg)
            return new_command


class ProjectCommand(object):
    """Represents an command from the project file."""

    def __init__(self, name, attributes):
        """Construct a command with the given attributes.

        Args:
            name (str): name of the command
            attributes (dict): named attributes of the command
        """
        assert 'env_spec' in attributes
        self._name = name
        self._attributes = attributes

    @property
    def name(self):
        """Get name of the command."""
        return self._name

    @property
    def notebook(self):
        """Notebook filename relative to project directory, or None."""
        return self._attributes.get('notebook', None)

    @property
    def bokeh_app(self):
        """Bokeh app filename relative to project directory, or None."""
        return self._attributes.get('bokeh_app', None)

    @property
    def unix_shell_commandline(self):
        """Unix shell command line string, or None.

        This property is here to support displaying the command in
        a UI, but shouldn't be used to execute the command; use
        ``exec_info_for_environment()`` for executing.
        """
        return self._attributes.get('unix', None)

    @property
    def windows_cmd_commandline(self):
        """cmd.exe command line string, or None.

        This property is here to support displaying the command in
        a UI, but shouldn't be used to execute the command; use
        ``exec_info_for_environment()`` for executing.
        """
        return self._attributes.get('windows', None)

    @property
    def conda_app_entry(self):
        """Conda "app entry" style command line.

        This property is here to support displaying the command in
        a UI, but shouldn't be used to execute the command; use
        ``exec_info_for_environment()`` for executing.
        """
        return self._attributes.get('conda_app_entry', None)

    @property
    def auto_generated(self):
        """Get the boolean indicating if the command is auto generated."""
        return self._attributes.get('auto_generated', False)

    @property
    def default_env_spec_name(self):
        """Get the environment spec name used for this command unless user specified otherwise."""
        return self._attributes.get('env_spec')

    def _shell_field(self):
        if _is_windows():
            return 'windows'
        else:
            return 'unix'

    @property
    def description(self):
        """Helpful string showing what the command is."""
        description = self._attributes.get('description', None)

        if description is None:
            if self.bokeh_app is not None:
                description = "Bokeh app %s" % self.bokeh_app
        if description is None:
            if self.notebook is not None:
                description = "Notebook %s" % self.notebook
        # we don't change this by platform since we use it for
        # publication_info() and it'd be weird if it mattered
        # what platform you publish from.
        if description is None:
            description = self._attributes.get('unix', None)
        if description is None:
            description = self._attributes.get('windows', None)
        if description is None:
            description = self._attributes.get('conda_app_entry', None)
        # we should have validated that there was a command in here
        assert description is not None
        return description

    def _choose_args_and_shell(self, environ, extra_args=None):
        assert extra_args is None or isinstance(extra_args, list)

        args = None
        shell = False

        if self.notebook is not None:
            path = os.path.join(environ['PROJECT_DIR'], self.notebook)
            args = ['jupyter-notebook', path]

        if self.bokeh_app is not None:
            path = os.path.join(environ['PROJECT_DIR'], self.bokeh_app)
            args = ['bokeh', 'serve', path]

        if args is not None:
            if extra_args is not None:
                args = args + extra_args
            return args, False

        command = self._attributes.get(self._shell_field(), None)
        if command is not None:
            args = [_append_extra_args_to_command_line(command, extra_args)]
            shell = True

        if args is None:
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
                        arg = arg.replace('${PREFIX}', conda_api.environ_get_prefix(environ))
                    args.append(arg)
                if extra_args is not None:
                    args = args + extra_args

        # args can be None if the command doesn't work on our platform
        return (args, shell)

    def exec_info_for_environment(self, environ, extra_args=None):
        """Get a ``CommandExecInfo`` ready to be executed.

        Args:
            environ (dict): the environment containing a CONDA_PREFIX, PATH, and PROJECT_DIR
            extra_args (list of str): extra args to append to the command line
        Returns:
            argv as list of strings
        """
        conda_var = conda_api.conda_prefix_variable()
        for name in (conda_var, 'PATH', 'PROJECT_DIR'):
            if name not in environ:
                raise ValueError("To get a runnable command for the app, %s must be set." % (name))

        (args, shell) = self._choose_args_and_shell(environ, extra_args)

        if args is None:
            # command doesn't work on our platform for example
            return None

        # always look in the project directory. This is a little
        # odd because we don't add PROJECT_DIR to PATH for child
        # processes - maybe we should?
        path = os.pathsep.join([environ['PROJECT_DIR'], environ['PATH']])

        # if we're using a shell, then args[0] is a whole command
        # line and not a single program name, and the shell will
        # search the path for us.
        if not shell:
            executable = find_executable(args[0], path)
            # if we didn't find args[0] on the path, we leave it as-is
            # and wait for it to fail when we later try to run it.
            if executable is not None:
                # if the executable is in cwd, for some reason find_executable does not
                # return the full path to it, just a relative path.
                args[0] = os.path.abspath(executable)

        # conda.misc.launch() uses the home directory
        # instead of the project directory as cwd when
        # running an installed package, but for our
        # purposes where we know we have a project dir
        # that's user-interesting, project directory seems
        # more useful. This way apps can for example find
        # sample data files relative to the project
        # directory.
        return CommandExecInfo(cwd=environ['PROJECT_DIR'],
                               args=args,
                               env=environ,
                               shell=shell,
                               notebook=self.notebook,
                               bokeh_app=self.bokeh_app)
