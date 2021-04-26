# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import collections
import os
import re
import sys

from anaconda_project.internal import streaming_popen


class PipError(Exception):
    """General pip error."""

    pass


class PipNotInstalledError(PipError):
    """Pip isn't even installed in this environment."""

    pass


# this function exists so we can monkeypatch it in tests
def _get_pip_command(prefix, extra_args):
    # we need to use the pip from the prefix
    unix_pip = os.path.join(prefix, "bin", "pip")
    win_pip = os.path.join(prefix, "Scripts", "pip.exe")
    pips = [pip for pip in [unix_pip, win_pip] if os.path.exists(pip)]
    if len(pips) == 0:
        raise PipNotInstalledError("'pip' command is not installed in the environment %s" % prefix)
    cmd_list = [pips[0]]
    cmd_list.extend(extra_args)
    return cmd_list


def _call_pip(prefix, extra_args, stdout_callback=None, stderr_callback=None):
    cmd_list = _get_pip_command(prefix, extra_args)

    try:
        (p, stdout_lines, stderr_lines) = streaming_popen.popen(cmd_list,
                                                                stdout_callback=stdout_callback,
                                                                stderr_callback=stderr_callback)
    except OSError as e:
        raise PipError("failed to run: %r: %r" % (" ".join(cmd_list), repr(e)))
    errstr = "".join(stderr_lines)
    if p.returncode != 0:
        raise PipError('%s: %s' % (" ".join(cmd_list), errstr))
    elif errstr != '':
        for line in errstr.split("\n"):
            print("%s %s: %s" % (cmd_list[0], cmd_list[1], line), file=sys.stderr)
    return "".join(stdout_lines)


def install(prefix, pkgs=None, stdout_callback=None, stderr_callback=None):
    """Install packages into an environment."""
    if not pkgs or not isinstance(pkgs, (list, tuple)):
        raise TypeError('must specify a list of one or more packages to install into existing environment, not %r' %
                        pkgs)

    args = ['install']
    args.extend(pkgs)

    return _call_pip(prefix, extra_args=args, stdout_callback=stdout_callback, stderr_callback=stderr_callback)


def remove(prefix, pkgs=None, stdout_callback=None, stderr_callback=None):
    """Remove packages from an environment."""
    if not pkgs or not isinstance(pkgs, (list, tuple)):
        raise TypeError('must specify a list of one or more packages to remove from existing environment')

    args = ['uninstall', '--yes']
    args.extend(pkgs)
    return _call_pip(prefix, extra_args=args, stdout_callback=stdout_callback, stderr_callback=stderr_callback)


def installed(prefix):
    """Get a dict of package names to (name, version) tuples."""
    if not os.path.isdir(prefix):
        return dict()

    try:
        # Use freeze instead of list so we get a consistent format across
        # different versions of pip
        out = _call_pip(prefix, extra_args=['freeze'])
        # on Windows, $ in a regex doesn't match \r\n, we need to get rid of \r
        out = out.replace("\r\n", "\n")
    except PipNotInstalledError:
        out = ""  # if pip isn't installed, there are no pip packages
    # the output to parse ("legacy" format mode) looks like this:
    #   ympy (0.7.6.1)
    #   tables (3.2.2)
    #   terminado (0.5)
    line_re = re.compile(r"^(.+)==(.+)$", flags=re.MULTILINE)
    result = dict()
    for match in line_re.finditer(out):
        result[match.group(1)] = (match.group(1), match.group(2))
    return result


ParsedPipSpec = collections.namedtuple('ParsedPipSpec', ['name'])

_spec_pat = re.compile(r' *([a-zA-Z0-9][-_.a-zA-Z0-9]+)')

_egg_fragment_re = re.compile(r'[#&]egg=([^&]*)')

_egg_fragment_postfix_re = re.compile(r'^(.*?)(?:-dev|-\d.*)$')

_url_schemes = set(('http', 'https', 'file', 'ftp', 'git', 'git+http', 'git+https', 'git+ssh', 'git+git', 'git+file',
                    'hg', 'hg+http', 'hg+https', 'hg+ssh', 'hg+static-http'
                    'bzr', 'bzr+http', 'bzr+https', 'bzr+ssh', 'bzr+sftp', 'bzr+ftp', 'bzr+lp', 'svn', 'svn+ssh',
                    'svn+http', 'svn+https', 'svn+svn'))


def _is_pip_understood_url(s):
    if ':' in s:
        scheme = s.split(':', 1)[0]
        return scheme.lower() in _url_schemes
    else:
        return False


def _extract_name(spec):
    m = _spec_pat.match(spec)
    if m is not None:
        return m.group(1)
    else:
        return None


def _extract_name_from_egg_fragment(url):
    m = _egg_fragment_re.search(url)
    if m is not None:
        fragment = _extract_name(m.group(1))
        if fragment is not None:
            # it's allowed to put "#egg=foo-1.2" but then pip just
            # ignores the "-1.2"
            m = _egg_fragment_postfix_re.search(fragment)
            if m is not None:
                return m.group(1)
            else:
                return fragment
    else:
        return None


def parse_spec(spec):
    """Parse a pip spec, right now we only understand the name portion.

    Parsing it exactly as pip would is extremely complicated, and
    we would pretty much have to import the pip code.
    So for now we'll "fail late" when we invoke pip.

    What we understand currently is an url with a "#egg=foo"
    fragment, and a plain package name (possibly with version info
    on it). We don't understand filesystem paths yet.

    Returns:
       ``ParsedPipSpec`` or None on failure

    """
    if _is_pip_understood_url(spec):
        name = _extract_name_from_egg_fragment(spec)
    else:
        name = _extract_name(spec)

    if name is None:
        return None
    else:
        return ParsedPipSpec(name=name)
