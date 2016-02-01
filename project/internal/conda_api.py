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
        raise Exception("could not invoke %r\n" % extra_args)
    return p.communicate()


def _call_and_parse(extra_args):
    stdout, stderr = _call_conda(extra_args)
    if stderr.decode().strip():
        raise Exception('conda %r:\nSTDERR:\n%s\nEND' % (extra_args, stderr.decode()))
    return json.loads(stdout.decode())


def info():
    """Return a dictionary with configuration information.

    No guarantee is made about which keys exist.  Therefore this function
    should only be used for testing and debugging.
    """
    return _call_and_parse(['info', '--json'])


def create(name=None, prefix=None, pkgs=None):
    """Create an environment either by name or path with a specified set of packages."""
    if not pkgs or not isinstance(pkgs, (list, tuple)):
        raise TypeError('must specify a list of one or more packages to ' 'install into new environment')

    cmd_list = ['create', '--yes', '--quiet']
    if name:
        ref = name
        search = [os.path.join(d, name) for d in info()['envs_dirs']]
        cmd_list = ['create', '--yes', '--quiet', '--name', name]
    elif prefix:
        ref = prefix
        search = [prefix]
        cmd_list = ['create', '--yes', '--quiet', '--prefix', prefix]
    else:
        raise TypeError('must specify either an environment name or a path ' 'for new environment')

    if any(os.path.exists(prefix) for prefix in search):
        raise CondaEnvExistsError('Conda environment [%s] already exists' % ref)

    cmd_list.extend(pkgs)
    (out, err) = _call_conda(cmd_list)
    if err.decode().strip():
        raise CondaError('conda %s: %s' % (" ".join(cmd_list), err.decode()))
    return out


def install(name=None, prefix=None, pkgs=None):
    """Install packages into an environment either by name or path with a specified set of packages."""
    if not pkgs or not isinstance(pkgs, (list, tuple)):
        raise TypeError('must specify a list of one or more packages to ' 'install into existing environment')

    cmd_list = ['install', '--yes', '--quiet']
    if name:
        cmd_list.extend(['--name', name])
    elif prefix:
        cmd_list.extend(['--prefix', prefix])
    else:  # just install into the current environment, whatever that is
        pass

    cmd_list.extend(pkgs)
    (out, err) = _call_conda(cmd_list)
    if err.decode().strip():
        raise CondaError('conda %s: %s' % (" ".join(cmd_list), err.decode()))
    return out
