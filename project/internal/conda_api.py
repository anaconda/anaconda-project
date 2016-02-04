from __future__ import absolute_import, division, unicode_literals
import errno
import subprocess
import json
import os


class CondaError(Exception):
    """General Conda error."""

    pass


class CondaEnvExistsError(CondaError):
    """Conda environment already exists."""

    pass


def _call_conda(extra_args):
    # just use whatever conda is on the path
    cmd_list = ['conda']

    cmd_list.extend(extra_args)

    try:
        p = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as e:
        raise CondaError("failed to run: %r: %r" % (" ".join(cmd_list), repr(e)))
    (out, err) = p.communicate()
    errstr = err.decode().strip()
    if errstr:
        raise CondaError('%s: %s' % (" ".join(cmd_list), errstr))
    return out


def _call_and_parse_json(extra_args):
    out = _call_conda(extra_args)
    return json.loads(out.decode())


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


def create(prefix, pkgs=None):
    """Create an environment either by name or path with a specified set of packages."""
    if not pkgs or not isinstance(pkgs, (list, tuple)):
        raise TypeError('must specify a list of one or more packages to ' 'install into new environment')

    if os.path.exists(prefix):
        raise CondaEnvExistsError('Conda environment [%s] already exists' % prefix)

    cmd_list = ['create', '--yes', '--quiet', '--prefix', prefix]

    cmd_list.extend(pkgs)
    return _call_conda(cmd_list)


def install(prefix, pkgs=None):
    """Install packages into an environment either by name or path with a specified set of packages."""
    if not pkgs or not isinstance(pkgs, (list, tuple)):
        raise TypeError('must specify a list of one or more packages to ' 'install into existing environment')

    cmd_list = ['install', '--yes', '--quiet']
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


def _is_conda_bindir(path):
    # TODO: I think Windows uses Scripts
    if not (path.endswith("/bin") or path.endswith("/bin/")):
        return False
    possible_prefix = os.path.dirname(path)
    conda_meta = os.path.join(possible_prefix, "conda-meta")
    return os.path.isdir(conda_meta)


def set_conda_env_in_path(path, prefix):
    """Remove any existing conda envs in the given path string, then add the given one.

    Args:
        path (str): value of the PATH environment variable
        prefix (str): the environment prefix, or None to remove all conda bindirs
    Returns:
        the new PATH value
    """
    elements = path.split(os.pathsep)
    new_elements = []
    if prefix is not None:
        # TODO: I think Windows uses Scripts
        new_elements.append(os.path.join(prefix, "bin"))
    for element in elements:
        if element != "" and not _is_conda_bindir(element):
            new_elements.append(element)
    return os.pathsep.join(new_elements)
