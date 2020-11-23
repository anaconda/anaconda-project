# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Class representing a command from the project file."""
from __future__ import absolute_import

from copy import copy
from collections import namedtuple

import os
import platform
import sys
from jinja2 import Template

from anaconda_project.verbose import _verbose_logger
from anaconda_project.internal import (conda_api, logged_subprocess, py2_compat)

try:  # pragma: no cover
    from shlex import quote  # pragma: no cover
except ImportError:  # pragma: no cover
    from pipes import quote  # pragma: no cover

try:
    from urllib.parse import quote as url_quote
except ImportError:  # pragma: no cover (py2 only)
    from urllib import quote as url_quote  # pragma: no cover (py2 only)

standard_command_attributes = ('description', 'env_spec', 'supports_http_options', 'bokeh_app', 'notebook', 'unix',
                               'windows', 'conda_app_entry', 'variables')
extra_command_attributes = ('registers_fusion_function', )
all_known_command_attributes = standard_command_attributes + extra_command_attributes


def _is_windows():
    # it's tempting to cache this but it hoses our test monkeypatching so don't.
    # or at least be aware you'll have to fix tests...
    return (platform.system() == 'Windows')


_ArgSpec = namedtuple('_ArgSpec', ['option', 'has_value'])

HTTP_SPECS = (_ArgSpec('--anaconda-project-host', True), _ArgSpec('--anaconda-project-address',
                                                                  True), _ArgSpec('--anaconda-project-port', True),
              _ArgSpec('--anaconda-project-url-prefix', True), _ArgSpec('--anaconda-project-no-browser', False),
              _ArgSpec('--anaconda-project-iframe-hosts', True), _ArgSpec('--anaconda-project-use-xheaders', False))


class _ArgsTransformer(object):
    specs = HTTP_SPECS

    def _parse_args_removing_known(self, results, args):
        if not args:
            return []

        arg = args[0]

        if arg == '--':
            return args

        for spec in self.specs:
            if spec.has_value:
                with_equals = spec.option + "="
                if arg == spec.option:
                    if len(args) == 1 or args[1].startswith("-"):
                        # This means there isn't a value for the option, which
                        # ideally might report a syntax error, but we have to
                        # do a significant refactoring to get a syntax error
                        # up to a user-visible place from here. Hopefully
                        # the command we are launching will complain about the
                        # empty value.
                        results[spec.option].append('')
                        return self._parse_args_removing_known(results, args[1:])
                    else:
                        results[spec.option].append(args[1])
                        return self._parse_args_removing_known(results, args[2:])
                elif arg.startswith(with_equals):
                    results[spec.option].append(arg[len(with_equals):])
                    return self._parse_args_removing_known(results, args[1:])
            elif arg == spec.option:
                results[spec.option] = [True]
                return self._parse_args_removing_known(results, args[1:])

        return [arg] + self._parse_args_removing_known(results, args[1:])

    def transform_args(self, args):
        results = {spec.option: [] for spec in self.specs}
        with_removed = self._parse_args_removing_known(results, args)
        # flatten results with deterministic sort to ease testing
        results_list = sorted(results.items(), key=lambda x: x[0])
        return self.add_args(results_list, with_removed)

    def add_args(self, results, args):
        # default implementation: drop all http-related args
        return args


class _BokehArgsTransformer(_ArgsTransformer):
    def add_args(self, results, args):
        added = []
        for (option, values) in results:
            if option in ('--anaconda-project-host', '--anaconda-project-port', '--anaconda-project-address'):
                for v in values:
                    added.append(option.replace('anaconda-project-', ''))
                    added.append(v)
            elif option == '--anaconda-project-url-prefix':
                for v in values:
                    added.append('--prefix')
                    added.append(v)
            elif option == '--anaconda-project-no-browser':
                if not values:
                    added.append('--show')
            elif option == '--anaconda-project-use-xheaders':
                if values and values[0] is True:
                    added.append('--use-xheaders')
            elif option == '--anaconda-project-iframe-hosts':
                # bokeh doesn't have a way to set this
                pass
            else:
                raise RuntimeError("unhandled http option for bokeh app")  # pragma: no cover

        return added + args


class _TemplateArgsTransformer(_ArgsTransformer):
    """ArgsTransformer that supports jinja2 templating."""
    def add_args(self, results, args):
        return args

    def arg_to_identifier(self, arg):
        """Turn a commandline argument into a Python identifier for jinja2."""
        return arg.replace('--', '').replace('-', '_')

    def parse_and_template(self, command, environ, extra_args):
        results = {spec.option: [] for spec in self.specs}
        self._parse_args_removing_known(results, extra_args)
        extra_args = _TemplateArgsTransformer().transform_args(extra_args)
        items = {k: (v[-1] if len(v) == 1 else v) for k, v in results.items() if v}
        # Aliasing of HTTP options (e.g anaconda_project_port to port)
        replacements = {}
        for k, v in items.items():
            if k.startswith('--anaconda-project-'):
                replacement = k.replace('--anaconda-project-', '')
                if replacement not in items:
                    replacements[replacement] = v

        if 'host' in replacements:
            host = replacements['host']
            replacements['host'] = host[-1] if isinstance(host, list) else host
            replacements['hosts'] = host if isinstance(host, list) else [host]

        items.update(replacements)
        items.update(environ)

        normalized = {self.arg_to_identifier(k): v for k, v in items.items()}
        templated_command = Template(command).render(normalized)
        return [_append_extra_args_to_command_line(templated_command, extra_args)]


class _NotebookArgsTransformer(_ArgsTransformer):
    def __init__(self, command):
        self.command = command

    def add_args(self, results, args):
        added = []

        # Notes about default_url
        #  * it should not include the base_url above, because Jupyter adds that
        #  * if the notebook is in a subdir, the subdir is not included in the
        #    url, only the basename
        #  * jupyter-notebook doesn't seem to encode or decode in any way
        #    so we need to do the url %hexcode escaping here
        filename = os.path.basename(self.command.notebook)
        default_url_arg = '--NotebookApp.default_url=/notebooks/%s' % url_quote(filename)
        added.append(default_url_arg)

        for (option, values) in results:
            # currently we do nothing with --anaconda-project-host for notebooks, is this ok?
            if option == '--anaconda-project-host':
                pass
            # pass through --port
            elif option == '--anaconda-project-port':
                for v in values:
                    added.append(option.replace('anaconda-project-', ''))
                    added.append(v)
            elif option == '--anaconda-project-address':
                for v in values:
                    added.append('--ip')
                    added.append(v)
            elif option == '--anaconda-project-no-browser':
                if values and values[0] is True:
                    added.append('--no-browser')
            # rename --anaconda-project-url-prefix to --NotebookApp.base_url
            elif option == '--anaconda-project-url-prefix':
                for v in values:
                    # notebook does not support the two-arg form
                    # without '=' here, for some reason.
                    added.append('--NotebookApp.base_url=' + v)
            elif option == '--anaconda-project-iframe-hosts':
                if len(values) > 0:
                    # the quoting here is sort of a headache. We need to get
                    # a python dictionary literal onto the command line for
                    # jupyter, containing the Content-Security-Policy header value.
                    # The single quotes around 'self' should be in the header value
                    # sent to the browser.
                    full_list = "'self' " + " ".join(values)
                    python_dict_literal = """{ 'headers': { 'Content-Security-Policy': "frame-ancestors """ + \
                                          full_list + '" } }'
                    added.append('--NotebookApp.tornado_settings=' + python_dict_literal)
            elif option == '--anaconda-project-use-xheaders':
                if values and values[0] is True:
                    added.append('--NotebookApp.trust_xheaders=True')
            else:
                raise RuntimeError("unhandled http option for notebooks")  # pragma: no cover

        return added + args


class CommandExecInfo(object):
    """Class describing an executable command."""
    def __init__(self, cwd, args, shell, env, notebook=None, bokeh_app=None):
        """Construct a CommandExecInfo."""
        self._cwd = cwd
        self._args = args
        self._shell = shell
        self._env = env
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

    def popen(self, **kwargs):
        """Convenience method runs the command using Popen.

        Args:
            kwargs: passed through to Popen

        Returns:
            Popen instance
        """
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
        return logged_subprocess.Popen(args=args,
                                       env=py2_compat.env_without_unicode(self._env),
                                       cwd=self._cwd,
                                       shell=self._shell,
                                       **kwargs)

    def execvpe(self):
        """Convenience method exec's the command replacing the current process.

        Returns:
            Does not return. May raise an OSError though.
        """

        conda_prefix = self.env.get('CONDA_PREFIX', False)
        if conda_prefix:
            # make sure to add any Conda Environment variables to the environ
            conda_env_vars = conda_api.get_env_vars(conda_prefix)
            for k, v in conda_env_vars.items():
                # by only updating non-existant variables
                # the variables in anaconda-project.yml take
                # precedence over any that were set in the env itself.
                if k not in self.env:
                    self.env[k] = v

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
                sys.exit(self.popen().wait())
            else:
                # this is all shell=True does on unix
                args = ['/bin/sh', '-c'] + args

        try:
            old_dir = os.getcwd()
            os.chdir(self._cwd)
            sys.stderr.flush()
            sys.stdout.flush()
            _verbose_logger().info("$ %s", " ".join(args))
            os.execvpe(args[0], args, self._env)
        finally:
            # avoid side effect if exec fails (or is mocked in tests)
            os.chdir(old_dir)


def _append_extra_args_to_command_line(command, extra_args):
    if not extra_args:
        return command
    else:
        if _is_windows():  # pragma: no cover
            from anaconda_project.internal.windows_cmdline import (windows_split_command_line,
                                                                   windows_join_command_line)
            args = windows_split_command_line(command)
            return windows_join_command_line(args + extra_args)
        else:
            new_command = command
            for arg in extra_args:
                new_command = new_command + " " + quote(arg)
            return new_command


class ProjectCommand(object):
    """Represents a command from the project file."""
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
    def supports_http_options(self):
        """Can accept the --anaconda-project-* options for HTTP servers."""
        default = (self.notebook is not None or self.bokeh_app is not None)
        return self._attributes.get('supports_http_options', default)

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
    def args(self):
        """Argv to exec directly, or None.

        This isn't allowed in the config file but we do generate
        it on the fly when we run stuff that isn't a configured
        project command.
        """
        return self._attributes.get('args', None)

    @property
    def conda_app_entry(self):
        """Conda "app entry" style command line.

        This property is here to support displaying the command in
        a UI, but shouldn't be used to execute the command; use
        ``exec_info_for_environment()`` for executing.
        """
        return self._attributes.get('conda_app_entry', None)

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
        if description is None:
            description = getattr(self, 'command', None)
        # we should have validated that there was a command in here
        assert description is not None
        return description

    @property
    def extras(self):
        """Dictionary of extra attributes not covered by other properties.

        These are typically 'plugin specific' (only for notebook, only for bokeh,
        etc.)
        """
        result = dict()
        for k in self._attributes.keys():
            if k in extra_command_attributes:
                result[k] = self._attributes[k]
        return result

    def _choose_args_and_shell(self, environ, extra_args=None):
        assert extra_args is None or isinstance(extra_args, list)

        args = None
        shell = False

        if not self.supports_http_options and (self.notebook or self.bokeh_app):
            # drop the http arguments
            extra_args = _ArgsTransformer().transform_args(extra_args)

        if self.notebook is not None:
            path = os.path.join(environ['PROJECT_DIR'], self.notebook)
            args = ['jupyter-notebook', path]
            if self.supports_http_options:
                extra_args = _NotebookArgsTransformer(self).transform_args(extra_args)

        if self.bokeh_app is not None:
            path = os.path.join(environ['PROJECT_DIR'], self.bokeh_app)
            args = ['bokeh', 'serve', path]
            if self.supports_http_options:
                extra_args = _BokehArgsTransformer().transform_args(extra_args)

        if self.args is not None:
            args = self.args

        if args is not None:
            if extra_args is not None:
                args = args + extra_args
            return args, False

        command = self._attributes.get(self._shell_field(), None)
        if (command is not None) and self.supports_http_options:
            args = [_append_extra_args_to_command_line(command, extra_args)]
            shell = True
        elif command:
            shell = True
            args = _TemplateArgsTransformer().parse_and_template(command, environ, extra_args)

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
            # We used to use spawn.find_executable but it is not
            # consistent across platforms. Specifically, for Windows
            # it seems to insist unnecessarily on an .exe extension
            # (unnecessary for our purposes at least)
            extensions = ['', '.bat', '.exe'] if _is_windows() else ['']
            executable = None
            for pdir in path.split(os.pathsep):
                for ext in extensions:
                    fpath = os.path.join(pdir, args[0] + ext)
                    if os.path.exists(fpath):
                        executable = fpath
                        break
                if executable is not None:
                    args[0] = os.path.abspath(executable)
                    break
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

        # add/update env vars from the command
        cmd_vars = self._attributes.get('variables', {})
        for k, v in cmd_vars.items():
            if k not in environ:
                environ[k] = v

        return CommandExecInfo(cwd=environ['PROJECT_DIR'], args=args, env=environ, shell=shell)

    def missing_packages(self, env_spec):
        """List packages required by this command which are not in the env spec.

        This is used to be sure if you add a notebook command you depend on
        notebook, and if you add a Bokeh command you depend on bokeh, etc.
        """
        missing = []
        # we assume 'anaconda' has both bokeh and notebook
        # already...  ideally we'd do a dependency resolution and
        # handle any transitive pull-in of bokeh or notebook, but
        # we aren't that clever right now.  when/if we do package
        # pinning we might have the dep resolution cached and we
        # could easily look in the pinned list instead of the root
        # dependency list.
        if 'anaconda' not in env_spec.conda_package_names_set:
            if self.bokeh_app is not None and 'bokeh' not in env_spec.conda_package_names_set:
                missing.append('bokeh')
            if self.notebook is not None and 'notebook' not in env_spec.conda_package_names_set:
                missing.append('notebook')

        return missing
