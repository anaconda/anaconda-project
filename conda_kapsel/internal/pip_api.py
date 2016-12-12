# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import collections
import subprocess
import os
import re
import sys

from conda_kapsel.internal import logged_subprocess


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


def _call_pip(prefix, extra_args):
    cmd_list = _get_pip_command(prefix, extra_args)

    try:
        p = logged_subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as e:
        raise PipError("failed to run: %r: %r" % (" ".join(cmd_list), repr(e)))
    (out, err) = p.communicate()
    errstr = err.decode().strip()
    if p.returncode != 0:
        raise PipError('%s: %s' % (" ".join(cmd_list), errstr))
    elif errstr != '':
        for line in errstr.split("\n"):
            print("%s %s: %s" % (cmd_list[0], cmd_list[1], line), file=sys.stderr)
    return out


def install(prefix, pkgs=None):
    """Install packages into an environment."""
    if not pkgs or not isinstance(pkgs, (list, tuple)):
        raise TypeError('must specify a list of one or more packages to install into existing environment')

    # --no-deps is because we don't want to pull in pip versions of
    # everything that conda has.
    args = ['install', '--quiet', '--no-deps']
    args.extend(pkgs)

    return _call_pip(prefix, extra_args=args)


def remove(prefix, pkgs=None):
    """Remove packages from an environment."""
    if not pkgs or not isinstance(pkgs, (list, tuple)):
        raise TypeError('must specify a list of one or more packages to remove from existing environment')

    args = ['uninstall', '--quiet', '--yes']
    args.extend(pkgs)
    return _call_pip(prefix, extra_args=args)


def installed(prefix):
    """Get a dict of package names to (name, version) tuples."""
    if not os.path.isdir(prefix):
        return dict()

    # In pip 9, there's a big ugly deprecation warning by default if
    # you type `pip list`, unless you do `pip list --format=legacy`
    # pip 8 of course does not support --format=legacy, so that
    # can't be done unconditionally.
    format_args = ["--format=legacy"]
    try:
        out = _call_pip(prefix, extra_args=['--version']).decode('utf-8')

        if out.startswith("pip "):
            try:
                major_version = int(out[4])
                if major_version <= 8:
                    format_args = []
            except ValueError:
                # didn't get an integer, who knows
                pass
    except PipNotInstalledError:
        pass

    try:
        out = _call_pip(prefix, extra_args=(['list'] + format_args)).decode('utf-8')
        # on Windows, $ in a regex doesn't match \r\n, we need to get rid of \r
        out = out.replace("\r\n", "\n")
    except PipNotInstalledError:
        out = ""  # if pip isn't installed, there are no pip packages
    # the output to parse ("legacy" format mode) looks like this:
    #   ympy (0.7.6.1)
    #   tables (3.2.2)
    #   terminado (0.5)
    line_re = re.compile("^ *([^ ]+) *\(([^)]+)\)$", flags=re.MULTILINE)
    result = dict()
    for match in line_re.finditer(out):
        result[match.group(1)] = (match.group(1), match.group(2))
    return result


ParsedPipSpec = collections.namedtuple('ParsedPipSpec', ['name'])

_spec_pat = re.compile(' *([a-zA-Z0-9][-_.a-zA-Z0-9]+)')


def parse_spec(spec):
    """Parse a pip spec, right now we only understand the name portion.

    Parsing it exactly as pip would is extremely complicated, and
    we would pretty much have to import the pip code.
    So for now we'll "fail late" when we invoke pip.

    Returns:
       ``ParsedPipSpec`` or None on failure

    """
    m = _spec_pat.match(spec)
    if m is None:
        return None
    name = m.group(1)
    return ParsedPipSpec(name=name)
