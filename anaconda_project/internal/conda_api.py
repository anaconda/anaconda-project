# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function, division, unicode_literals

import collections
import errno
import subprocess
import json
import os
import platform
import re
import shutil
import sys
import tempfile

from anaconda_project.internal import logged_subprocess
from anaconda_project.internal.directory_contains import subdirectory_relative_to_directory


class CondaError(Exception):
    """General Conda error."""

    def __init__(self, message, json=None):
        super(CondaError, self).__init__(message)
        self.json = json


class CondaEnvExistsError(CondaError):
    """Conda environment already exists."""

    pass


# this function exists so we can monkeypatch it in tests
def _get_conda_command(extra_args):
    # just use whatever conda is on the path
    cmd_list = ['conda']
    cmd_list.extend(extra_args)
    return cmd_list


def _call_conda(extra_args, json_mode=False):
    cmd_list = _get_conda_command(extra_args)

    try:
        p = logged_subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as e:
        raise CondaError("failed to run: %r: %r" % (" ".join(cmd_list), repr(e)))
    (out, err) = p.communicate()
    errstr = err.decode().strip()
    if p.returncode != 0:
        parsed = None
        message = errstr
        if json_mode:
            try:
                parsed = json.loads(out.decode())
                if parsed is not None and isinstance(parsed, dict):
                    message = parsed.get('message', message)
            except Exception:
                pass

        raise CondaError('%s: %s' % (" ".join(cmd_list), message), json=parsed)
    elif errstr != '':
        for line in errstr.split("\n"):
            print("%s %s: %s" % (cmd_list[0], cmd_list[1], line), file=sys.stderr)
    return out


def _call_and_parse_json(extra_args):
    out = _call_conda(extra_args, json_mode=True)
    try:
        return json.loads(out.decode())
    except ValueError as e:
        raise CondaError('Invalid JSON from conda: %s' % str(e))


def info():
    """Return a dictionary with configuration information.

    No guarantee is made about which keys exist.  Therefore this function
    should only be used for testing and debugging.
    """
    return _call_and_parse_json(['info', '--json'])


def resolve_env_to_prefix(name_or_prefix):
    """Convert an env name or path into a canonical prefix path.

    Returns:
        Absolute path of prefix or None if it isn't found.
    """
    if os.path.isabs(name_or_prefix):
        return name_or_prefix

    json = info()
    root_prefix = json.get('root_prefix', None)
    if name_or_prefix == 'root':
        return root_prefix

    envs = json.get('envs', [])
    for prefix in envs:
        if os.path.basename(prefix) == name_or_prefix:
            return prefix
    return None


def create(prefix, pkgs=None, channels=()):
    """Create an environment either by name or path with a specified set of packages."""
    if not pkgs or not isinstance(pkgs, (list, tuple)):
        raise TypeError('must specify a list of one or more packages to install into new environment')

    if os.path.exists(prefix):
        raise CondaEnvExistsError('Conda environment [%s] already exists' % prefix)

    cmd_list = ['create', '--yes', '--quiet', '--prefix', prefix]

    for channel in channels:
        cmd_list.extend(['--channel', channel])

    cmd_list.extend(pkgs)
    return _call_conda(cmd_list)


def install(prefix, pkgs=None, channels=()):
    """Install packages into an environment either by name or path with a specified set of packages."""
    if not pkgs or not isinstance(pkgs, (list, tuple)):
        raise TypeError('must specify a list of one or more packages to install into existing environment, not %r',
                        pkgs)

    cmd_list = ['install', '--yes', '--quiet']
    cmd_list.extend(['--prefix', prefix])

    for channel in channels:
        cmd_list.extend(['--channel', channel])

    cmd_list.extend(pkgs)
    return _call_conda(cmd_list)


def remove(prefix, pkgs=None):
    """Remove packages from an environment either by name or path."""
    if not pkgs or not isinstance(pkgs, (list, tuple)):
        raise TypeError('must specify a list of one or more packages to remove from existing environment')

    cmd_list = ['remove', '--yes', '--quiet']
    cmd_list.extend(['--prefix', prefix])

    cmd_list.extend(pkgs)
    return _call_conda(cmd_list)


def installed(prefix):
    """Get a dict of package names to (name, version, build) tuples."""
    meta_dir = os.path.join(prefix, 'conda-meta')
    try:
        full_names = set(fn[:-5] for fn in os.listdir(meta_dir) if fn.endswith('.json'))
    except OSError as e:
        if e.errno == errno.ENOENT:
            full_names = set()
        else:
            raise CondaError(str(e))
    result = dict()
    for full_name in full_names:
        pieces = full_name.rsplit('-', 2)
        if len(pieces) == 3:
            result[pieces[0]] = tuple(pieces)
    return result


def resolve_dependencies(pkgs, channels=()):
    """Resolve packages into a full transitive list of (name, version, build) tuples."""
    if not pkgs or not isinstance(pkgs, (list, tuple)):
        raise TypeError('must specify a list of one or more packages to install into existing environment, not %r',
                        pkgs)

    # even with --dry-run, conda wants to create the prefix,
    # so we ensure it's somewhere out of the way
    prefix = tempfile.mkdtemp(prefix="kapsel_resolve_")

    cmd_list = ['create', '--yes', '--quiet', '--json', '--dry-run', '--prefix', prefix]

    for channel in channels:
        cmd_list.extend(['--channel', channel])

    cmd_list.extend(pkgs)
    try:
        parsed = _call_and_parse_json(cmd_list)
    finally:
        try:
            shutil.rmtree(prefix)
        except Exception:
            pass

    results = []
    actions = parsed.get('actions', [])
    for action in actions:
        links = action.get('LINK', [])
        for link in links:
            name = link.get('name', None)
            version = link.get('version', None)
            build_string = link.get('build_string', None)
            if name is not None and \
               version is not None and \
               build_string is not None:
                results.append((name, version, build_string))

    if len(results) == 0:
        raise CondaError("Could not understand JSON from Conda, could be a problem with this Conda version.",
                         json=parsed)

    return results


def _contains_conda_meta(path):
    conda_meta = os.path.join(path, "conda-meta")
    return os.path.isdir(conda_meta)


def _is_conda_bindir_unix(path):
    if path.endswith("/"):
        path = path[:-1]
    if not path.endswith("/bin"):
        return False
    possible_prefix = os.path.dirname(path)
    return _contains_conda_meta(possible_prefix)


def _path_endswith_windows(path, suffix):
    if path.endswith("\\") or path.endswith("/"):
        path = path[:-1]
    replaced = suffix.replace("\\", "/")
    return path.endswith("\\" + suffix) or \
        path.endswith("/" + suffix) or \
        path.endswith("\\" + replaced) or \
        path.endswith("/" + replaced)


def _is_conda_bindir_windows(path):
    # on Windows there are three conda binary locations:
    #   - the prefix itself (contains python.exe)
    #   - prefix\Library\bin
    #   - prefix\Scripts
    if path.endswith("\\") or path.endswith("/"):
        path = path[:-1]
    if _contains_conda_meta(path):
        return True
    elif _path_endswith_windows(path, "Library\\bin"):
        possible_prefix = os.path.dirname(os.path.dirname(path))
        return _contains_conda_meta(possible_prefix)
    elif _path_endswith_windows(path, "Scripts"):
        possible_prefix = os.path.dirname(path)
        return _contains_conda_meta(possible_prefix)
    else:
        return False


def _windows_bindirs(prefix):
    # activate.bat in conda-env does it in this order, [ prefix, Scripts, Library\bin ]
    dirs = [prefix]
    for item in ("Scripts", "Library\\bin"):
        dirs.append(os.path.join(prefix, item))
    return dirs


def _unix_bindirs(prefix):
    return [os.path.join(prefix, "bin")]


def _set_conda_env_in_path(path, prefix, bindirs_func, is_bindir_func):
    elements = path.split(os.pathsep)
    new_elements = []
    if prefix is not None:
        new_elements = bindirs_func(prefix)
    for element in elements:
        if element != "" and not is_bindir_func(element):
            new_elements.append(element)

    return os.pathsep.join(new_elements)


def _set_conda_env_in_path_unix(path, prefix):
    return _set_conda_env_in_path(path, prefix, _unix_bindirs, _is_conda_bindir_unix)


def _set_conda_env_in_path_windows(path, prefix):
    return _set_conda_env_in_path(path, prefix, _windows_bindirs, _is_conda_bindir_windows)


def set_conda_env_in_path(path, prefix):
    """Remove any existing conda envs in the given path string, then add the given one.

    Args:
        path (str): value of the PATH environment variable
        prefix (str): the environment prefix, or None to remove all conda bindirs
    Returns:
        the new PATH value
    """
    if platform.system() == 'Windows':
        return _set_conda_env_in_path_windows(path, prefix)
    else:
        return _set_conda_env_in_path_unix(path, prefix)


ParsedSpec = collections.namedtuple('ParsedSpec', ['name', 'conda_constraint', 'pip_constraint'])

# this is copied from conda
_spec_pat = re.compile(r'''
(?P<name>[^=<>!\s]+)               # package name
\s*                                # ignore spaces
(
  (?P<cc>=[^=<>!]+(=[^=<>!]+)?)    # conda constraint
  |
  (?P<pc>[=<>!]{1,2}.+)            # new (pip-style) constraint(s)
)?
$                                  # end-of-line
''', re.VERBOSE)


def parse_spec(spec):
    """Parse a package name and version spec as conda would.

    Returns:
       ``ParsedSpec`` or None on failure
    """
    m = _spec_pat.match(spec)
    if m is None:
        return None
    pip_constraint = m.group('pc')
    if pip_constraint is not None:
        pip_constraint = pip_constraint.replace(' ', '')
    return ParsedSpec(name=m.group('name').lower(), conda_constraint=m.group('cc'), pip_constraint=pip_constraint)

# these are in order of preference. On pre-4.1.4 Windows,
# CONDA_PREFIX and CONDA_ENV_PATH aren't set, so we get to
# CONDA_DEFAULT_ENV.
_all_prefix_variables = ('CONDA_PREFIX', 'CONDA_ENV_PATH', 'CONDA_DEFAULT_ENV')


def conda_prefix_variable():
    # conda 4.1.4 and higher sets CONDA_PREFIX to the full prefix,
    # and CONDA_DEFAULT_ENV to the env name only, cross-platform.

    # Pre-4.1.4, on Windows, activate.bat never sets
    # CONDA_ENV_PATH but sets CONDA_DEFAULT_ENV to the full
    # path to the environment.

    # Pre-4.1.4, on Unix, activate script sets CONDA_ENV_PATH
    # to the full path, and sets CONDA_DEFAULT_ENV to either
    # just the env name or the full path.

    # if we're in a conda environment, then use CONDA_PREFIX if it
    # was set by conda, otherwise use CONDA_ENV_PATH if set,
    # otherwise use CONDA_DEFAULT_ENV if set.
    for name in _all_prefix_variables:
        if name in os.environ:
            return name

    # if we aren't in a conda environment, just hope we have a
    # newer conda...
    return 'CONDA_PREFIX'


def environ_get_prefix(environ):
    for name in _all_prefix_variables:
        if name in environ:
            return environ.get(name)
    return None


def environ_delete_prefix_variables(environ):
    for name in _all_prefix_variables:
        if name in environ:
            del environ[name]


_envs_dirs = None
_root_dir = None


def environ_set_prefix(environ, prefix, varname=conda_prefix_variable()):
    prefix = os.path.normpath(prefix)
    environ[varname] = prefix
    if varname != 'CONDA_DEFAULT_ENV':
        # This case matters on both Unix and Windows
        # with conda >= 4.1.4 since requirement.env_var
        # is CONDA_PREFIX, and matters on Unix only pre-4.1.4
        # when requirement.env_var is CONDA_ENV_PATH.
        global _envs_dirs
        global _root_dir
        if _envs_dirs is None:
            i = info()
            _envs_dirs = [os.path.normpath(d) for d in i.get('envs_dirs', [])]
            _root_dir = os.path.normpath(i.get('root_prefix'))
        if prefix == _root_dir:
            name = 'root'
        else:
            for d in _envs_dirs:
                name = subdirectory_relative_to_directory(prefix, d)
                if name != prefix:
                    break
        environ['CONDA_DEFAULT_ENV'] = name
