# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function, division, unicode_literals

import collections
import errno
import json
import os
import platform
import re
import shutil
import sys
import tempfile

from anaconda_project.internal import streaming_popen
from anaconda_project.internal.directory_contains import subdirectory_relative_to_directory
from anaconda_project.internal.py2_compat import is_string

CONDA_EXE = os.environ.get("CONDA_EXE", "conda")


class CondaError(Exception):
    """General Conda error."""
    def __init__(self, message, json=None):
        super(CondaError, self).__init__(message)
        self.json = json


class CondaEnvExistsError(CondaError):
    """Conda environment already exists."""

    pass


class CondaEnvMissingError(CondaError):
    """Conda environment missing."""

    pass


# this function exists so we can monkeypatch it in tests
def _get_conda_command(extra_args):
    # just use whatever conda is on the path
    cmd_list = [CONDA_EXE]
    cmd_list.extend(extra_args)
    return cmd_list


# This is obviously ridiculous, we'll work to
# find a better way (at least in newer versions
# of conda).
def _platform_hacked_conda_code(platform, bits):
    return """import conda
try:
    # this is conda 4.2 and 4.3

    # fix whether default channels have msys
    import conda.base.constants
    from conda.base.constants import DEFAULT_CHANNELS_UNIX, DEFAULT_CHANNELS_WIN
    if "{platform}" == 'win':
        corrected_channels = DEFAULT_CHANNELS_WIN
    else:
        corrected_channels = DEFAULT_CHANNELS_UNIX

    setattr(conda.base.constants, 'DEFAULT_CHANNELS', corrected_channels)

    from conda.base.context import Context

    class KapselHackedContext(Context):
        @property
        def subdir(self):
            return "{platform}-{bits}"

        @property
        def bits(self):
            return {bits}

    setattr(conda.base.context.context, "__class__", KapselHackedContext)
except ImportError:
    # this is conda 4.1
    import conda.config

    setattr(conda.config, "platform", "{platform}")
    setattr(conda.config, "bits", "{bits}")
    setattr(conda.config, "subdir", "{platform}-{bits}")

    # fix up the default urls
    msys_url = 'https://repo.continuum.io/pkgs/msys2'
    if "{platform}" == "win":
        if msys_url not in conda.config.defaults_:
            conda.config.defaults_.append(msys_url)
    else:
        if msys_url in conda.config.defaults_:
            conda.config.defaults_.remove(msys_url)


import conda.cli
import sys

sys.argv[0] = "conda"
sys.exit(conda.cli.main())
""".format(platform=platform, bits=bits).strip() + "\n"


def _get_platform_hacked_conda_command(extra_args, platform):
    """Get conda command and a string representing it in error messages."""
    if platform == current_platform() or platform is None:
        cmd_list = _get_conda_command(extra_args)
        return (cmd_list, " ".join(cmd_list))
    else:
        (platform_name, bits) = platform.split("-")

        conda_code = _platform_hacked_conda_code(platform_name, bits)

        # this has to run with the python from the root env,
        # so the conda modules will be found.
        root_prefix = _get_root_prefix()
        root_python = None
        for location in (('bin', 'python'), ('python.exe', ), ('Scripts', 'python.exe'), ('Library', 'bin',
                                                                                          'python.exe')):
            candidate = os.path.join(root_prefix, *location)
            if os.path.isfile(candidate):
                root_python = candidate
                break
        assert root_python is not None

        cmd_list = [root_python, '-c', conda_code]
        cmd_list.extend(extra_args)
        return (cmd_list, " ".join(["conda"] + cmd_list[3:]))


def _call_conda(extra_args, json_mode=False, platform=None, stdout_callback=None, stderr_callback=None):
    assert len(extra_args) > 0  # we deref extra_args[0] below

    (cmd_list, command_in_errors) = _get_platform_hacked_conda_command(extra_args, platform=platform)

    try:
        (p, stdout_lines, stderr_lines) = streaming_popen.popen(cmd_list,
                                                                stdout_callback=stdout_callback,
                                                                stderr_callback=stderr_callback)
    except OSError as e:
        raise CondaError("failed to run: %r: %r" % (command_in_errors, repr(e)))
    errstr = "".join(stderr_lines)
    if p.returncode != 0:
        parsed = None
        message = errstr
        if json_mode:
            try:
                out = "".join(stdout_lines)
                parsed = json.loads(out)
                if parsed is not None and isinstance(parsed, dict):
                    # some versions of conda do 'error' and others
                    # both 'error' and 'message' and they appear to
                    # be the same.
                    for field in ('message', 'error'):
                        if field in parsed:
                            message = parsed[field]
                            break
            except Exception:
                pass

        raise CondaError('%s: %s' % (command_in_errors, message), json=parsed)
    elif errstr != '' and stderr_callback is None:
        # this is a sort of fallback because not all of our code
        # passes in a callback yet.
        for line in stderr_lines:
            print("%s %s: %s" % ("conda", extra_args[0], line.strip()), file=sys.stderr)

    return "".join(stdout_lines)


def _call_and_parse_json(extra_args, platform=None):
    out = _call_conda(extra_args, json_mode=True, platform=platform)
    try:
        return json.loads(out)
    except ValueError as e:
        raise CondaError('Invalid JSON from conda: %s' % str(e))


def info(platform=None):
    """Return a dictionary with configuration information.

    No guarantee is made about which keys exist.  Therefore this function
    should only be used for testing and debugging.
    """
    return _call_and_parse_json(['info', '--json'], platform=platform)


def get_env_vars(env_prefix):
    """Return a dictionary of environment variables.

    These are Conda Environment variables that have been
    set using `conda env config vars`.
    """

    try:
        return _call_and_parse_json(['env', 'config', 'vars', 'list', '-p', env_prefix, '--json'])
    except CondaError as e:
        # conda env config was introduced in version 4.8
        if 'invalid choice' not in str(e).lower():
            raise
        else:
            return {}


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


_cached_root_prefix = None


def _get_root_prefix():
    global _cached_root_prefix

    if _cached_root_prefix is None:
        _cached_root_prefix = resolve_env_to_prefix('root')
    return _cached_root_prefix


def create(prefix, pkgs=None, channels=(), stdout_callback=None, stderr_callback=None):
    """Create an environment either by name or path with a specified set of packages."""
    if not pkgs or not isinstance(pkgs, (list, tuple)):
        raise TypeError('must specify a list of one or more packages to install into new environment')

    if os.path.exists(prefix):
        raise CondaEnvExistsError('Conda environment [%s] already exists' % prefix)

    cmd_list = ['create', '--yes', '--prefix', prefix]

    for channel in channels:
        cmd_list.extend(['--channel', channel])

    cmd_list.extend(pkgs)
    _call_conda(cmd_list, stdout_callback=stdout_callback, stderr_callback=stderr_callback)


def clone(prefix, source, stdout_callback=None, stderr_callback=None):
    """Clone a pre-existing env."""
    if not os.path.exists(source):
        raise CondaEnvMissingError('Conda environment [%s] does not exist to clone.' % source)

    cmd_list = ['create', '-p', prefix, '--clone', source]
    _call_conda(cmd_list, stdout_callback=stdout_callback, stderr_callback=stderr_callback)
    # If someone is using the .readonly flag-file approach, the clone command is going to copy
    # that. So we need to remove it if we find it in the new, copied environment.
    readonly_file = os.path.join(prefix, '.readonly')
    if os.path.exists(readonly_file):
        os.unlink(readonly_file)


def install(prefix, pkgs=None, channels=(), stdout_callback=None, stderr_callback=None):
    """Install packages into an environment either by name or path with a specified set of packages."""
    if not pkgs or not isinstance(pkgs, (list, tuple)):
        raise TypeError('must specify a list of one or more packages to install into existing environment, not %r',
                        pkgs)

    cmd_list = ['install', '--yes']
    cmd_list.extend(['--prefix', prefix])

    for channel in channels:
        cmd_list.extend(['--channel', channel])

    cmd_list.extend(pkgs)
    _call_conda(cmd_list, stdout_callback=stdout_callback, stderr_callback=stderr_callback)


def remove(prefix, pkgs=None, stdout_callback=None, stderr_callback=None):
    """Remove packages from an environment either by name or path."""
    if not pkgs or not isinstance(pkgs, (list, tuple)):
        raise TypeError('must specify a list of one or more packages to remove from existing environment')

    cmd_list = ['remove', '--yes']
    cmd_list.extend(['--prefix', prefix])

    cmd_list.extend(pkgs)
    _call_conda(cmd_list, stdout_callback=stdout_callback, stderr_callback=stderr_callback)


def _parse_dist(dist):
    # the "dist" is the basename of a package inside
    # conda-meta, like "numpy-1.10.4-py34_1"
    pieces = dist.rsplit('-', 2)
    if len(pieces) == 3:
        return tuple(pieces)
    else:
        return None


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
        pieces = _parse_dist(full_name)
        if pieces is not None:
            result[pieces[0]] = pieces
    return result


def resolve_dependencies(pkgs, channels=(), platform=None):
    """Resolve packages into a full transitive list of (name, version, build) tuples."""
    if not pkgs or not isinstance(pkgs, (list, tuple)):
        raise TypeError('must specify a list of one or more packages to install into existing environment, not %r',
                        pkgs)

    # even with --dry-run, conda wants to create the prefix,
    # so we ensure it's somewhere out of the way.
    prefix = tempfile.mkdtemp(prefix="_anaconda_project_resolve_")

    # conda 4.1 (and possibly other versions) will complain
    # if the directory already exists. An evil attacker
    # on a multiuser system could replace this with a file
    # after we remove it, and then conda's mkdir would fail.
    os.rmdir(prefix)

    cmd_list = ['create', '--yes', '--quiet', '--json', '--dry-run', '--prefix', prefix]

    for channel in channels:
        cmd_list.extend(['--channel', channel])

    cmd_list.extend(pkgs)
    try:
        parsed = _call_and_parse_json(cmd_list, platform=platform)
    finally:
        try:
            if os.path.isdir(prefix):
                shutil.rmtree(prefix)
        except Exception:
            pass

    results = []
    actions = parsed.get('actions', [])
    # old conda gives us one dict, newer a list of dicts
    if isinstance(actions, dict):
        actions = [actions]

    for action in actions:
        if isinstance(action, dict):
            links = action.get('LINK', [])
            for link in links:
                found = None
                # 4.1 conda gives us a string like
                # 'python-3.6.0-0 2' and 4.3 gives us a
                # dict with the fields already decomposed.
                if isinstance(link, dict):
                    name = link.get('name', None)
                    version = link.get('version', None)
                    build_string = link.get('build_string', None)
                    if name is not None and \
                       version is not None and \
                       build_string is not None:
                        found = (name, version, build_string)
                elif is_string(link):
                    # we have a string like 'python-3.6.0-0 2'
                    pieces = link.split()
                    if len(pieces) > 0:
                        # 'found' can be None if we didn't understand the string
                        found = _parse_dist(pieces[0])

                if found is not None:
                    results.append(found)

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


ParsedSpec = collections.namedtuple(
    'ParsedSpec', ['name', 'conda_constraint', 'pip_constraint', 'exact_version', 'exact_build_string'])

# this is copied from conda
_spec_pat = re.compile(
    r'''
(?P<name>[^=<>!\s]+)               # package name
\s*                                # ignore spaces
(
  (?P<cc>=[^=<>!]+(=[^=<>!]+)?)    # conda constraint
  |
  (?P<pc>[=<>!]{1,2}.+)            # new (pip-style) constraint(s)
)?
$                                  # end-of-line
''', re.VERBOSE)

_conda_constraint_pat = re.compile('=(?P<version>[^=<>!]+)(?P<build>=[^=<>!]+)?', re.VERBOSE)


def parse_spec(spec):
    """Parse a package name and version spec as conda would.

    Returns:
       ``ParsedSpec`` or None on failure
    """
    if not is_string(spec):
        raise TypeError("Expected a string not %r" % spec)

    m = _spec_pat.match(spec)
    if m is None:
        return None
    name = m.group('name').lower()
    pip_constraint = m.group('pc')
    if pip_constraint is not None:
        pip_constraint = pip_constraint.replace(' ', '')

    conda_constraint = m.group('cc')

    exact_version = None
    exact_build_string = None
    if conda_constraint is not None:
        m = _conda_constraint_pat.match(conda_constraint)
        assert m is not None
        exact_version = m.group('version')
        for special in ('|', '*', ','):
            if special in exact_version:
                exact_version = None
                break
        if exact_version is not None:
            exact_build_string = m.group('build')
            if exact_build_string is not None:
                assert exact_build_string[0] == '='
                exact_build_string = exact_build_string[1:]

    return ParsedSpec(name=name,
                      conda_constraint=conda_constraint,
                      pip_constraint=pip_constraint,
                      exact_version=exact_version,
                      exact_build_string=exact_build_string)


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


# This isn't all (e.g. leaves out arm, power).  it's sort of "all
# that people typically publish for"
default_platforms = ('linux-64', 'osx-64', 'win-64')
assert tuple(sorted(default_platforms)) == default_platforms

# osx-32 isn't in here since it isn't much used
default_platforms_plus_32_bit = ('linux-32', 'linux-64', 'osx-64', 'win-32', 'win-64')
assert tuple(sorted(default_platforms_plus_32_bit)) == default_platforms_plus_32_bit

_non_x86_linux_machines = {'armv6l', 'armv7l', 'ppc64le'}

# this list will get outdated, unfortunately.
_known_platforms = tuple(
    sorted(list(default_platforms_plus_32_bit) + ['osx-32'] + [("linux-%s" % m) for m in _non_x86_linux_machines]))

known_platform_names = ('linux', 'osx', 'win')
assert tuple(sorted(known_platform_names)) == known_platform_names

unix_platform_names = ('linux', 'osx')
assert tuple(sorted(unix_platform_names)) == unix_platform_names

_known_platform_groups = dict()

# Fill in the 'linux', 'osx', 'win' groups
for name in known_platform_names:
    result = []
    for p in default_platforms_plus_32_bit:
        if p.startswith(name):
            result.append(p)
    _known_platform_groups[name] = tuple(result)
    assert tuple(sorted(_known_platform_groups[name])) == _known_platform_groups[name]


# fill in the 'unix' group
def _known_unix_platforms():
    result = []
    for unix_name in unix_platform_names:
        for p in default_platforms_plus_32_bit:
            if p.startswith(unix_name):
                result.append(p)
    return tuple(result)


_known_platform_groups['unix'] = _known_unix_platforms()
assert tuple(sorted(_known_platform_groups['unix'])) == _known_platform_groups['unix']

# fill in the 'all' group
_known_platform_groups['all'] = default_platforms_plus_32_bit

# this isn't just _known_platform_groups.keys() because we want to be
# in order from most to least general
_known_platform_groups_keys = ('all', 'unix') + known_platform_names
assert set(_known_platform_groups_keys) == set(_known_platform_groups.keys())


def current_platform():
    m = platform.machine()
    if m in _non_x86_linux_machines:
        return 'linux-%s' % m
    else:
        _platform_map = {
            'linux2': 'linux',
            'linux': 'linux',
            'darwin': 'osx',
            'win32': 'win',
        }
        p = _platform_map.get(sys.platform, 'unknown')
        return '%s-%d' % (p, (8 * tuple.__itemsize__))


_default_platforms_with_current = tuple(sorted(list(set(default_platforms + (current_platform(), )))))


def default_platforms_with_current():
    return _default_platforms_with_current


def parse_platform(platform):
    """Split platform into OS name and architecture."""
    assert '-' in platform
    # platforms can have multiple hyphens e.g. linux-cos5-64 Our
    # goal here is to separate the general name from the
    # bit-width.
    pieces = platform.rsplit("-", 1)
    return (pieces[0], pieces[1])


def validate_platform_list(platforms):
    """Split platform list into known, unknown, and invalid platforms.

    Also, sort the list into canonical order.

    We return a tuple, the second list in the tuple
    is a subset of the first, and indicates platforms
    we don't know about. These may create a warning.
    The third list is not in the other two and indicates
    unusably-invalid platform names.

    Returns:
       Tuple of known platforms and unknown platforms.
    """
    result = set()
    unknown = set()
    invalid = set()
    for p in platforms:
        if '-' not in p:
            invalid.add(p)
        else:
            result.add(p)
            if p not in _known_platforms:
                unknown.add(p)

    # unknown platforms aren't necessarily an error, we just
    # don't do anything smart with them.
    return (sort_platform_list(result), sort_platform_list(unknown), sort_platform_list(invalid))


def sort_platform_list(platforms):
    """Sort platform list (including "grouping" names) from more to less general."""
    remaining = set(platforms)
    result = []
    for known in (_known_platform_groups_keys + _known_platforms):
        if known in remaining:
            result.append(known)
            remaining.remove(known)

    result = result + sorted(list(remaining))

    return result
