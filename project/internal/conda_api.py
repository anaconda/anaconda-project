from __future__ import absolute_import, division, unicode_literals
from subprocess import Popen, PIPE
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
        p = Popen(cmd_list, stdout=PIPE, stderr=PIPE)
    except OSError:
        raise CondaError("failed to run: %r" % (" ".join(cmd_list)))
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


def create(prefix, pkgs=None):
    """Create an environment either by name or path with a specified set of packages."""
    if not pkgs or not isinstance(pkgs, (list, tuple)):
        raise TypeError('must specify a list of one or more packages to ' 'install into new environment')

    cmd_list = ['create', '--yes', '--quiet']
    ref = prefix
    search = [prefix]
    cmd_list = ['create', '--yes', '--quiet', '--prefix', prefix]

    if any(os.path.exists(prefix) for prefix in search):
        raise CondaEnvExistsError('Conda environment [%s] already exists' % ref)

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
