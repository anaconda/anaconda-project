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
import re
import sys


class CondaError(Exception):
    """General Conda error."""

    pass


class CondaEnvExistsError(CondaError):
    """Conda environment already exists."""

    pass


# this function exists so we can monkeypatch it in tests
def _get_conda_command(extra_args):
    # just use whatever conda is on the path
    cmd_list = ['conda']
    cmd_list.extend(extra_args)
    return cmd_list


def _call_conda(extra_args):
    cmd_list = _get_conda_command(extra_args)

    try:
        p = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as e:
        raise CondaError("failed to run: %r: %r" % (" ".join(cmd_list), repr(e)))
    (out, err) = p.communicate()
    errstr = err.decode().strip()
    if p.returncode != 0:
        raise CondaError('%s: %s' % (" ".join(cmd_list), errstr))
    elif errstr != '':
        for line in errstr.split("\n"):
            print("%s %s: %s" % (cmd_list[0], cmd_list[1], line), file=sys.stderr)
    return out


def _call_and_parse_json(extra_args):
    out = _call_conda(extra_args)
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
        raise TypeError('must specify a list of one or more packages to install into existing environment')

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
    import platform
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
