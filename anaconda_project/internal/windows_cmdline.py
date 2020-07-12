# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Windows command line manipulation."""
from __future__ import absolute_import

import subprocess


class WindowsCommandLineException(Exception):
    pass


def windows_split_command_line(command):
    from ctypes import windll, c_int, POINTER, byref
    from ctypes.wintypes import LPCWSTR, LPWSTR, HLOCAL

    CommandLineToArgvW = windll.shell32.CommandLineToArgvW
    CommandLineToArgvW.argtypes = [LPCWSTR, POINTER(c_int)]
    CommandLineToArgvW.restype = POINTER(LPWSTR)

    LocalFree = windll.kernel32.LocalFree
    LocalFree.argtypes = [HLOCAL]
    LocalFree.restype = HLOCAL

    argc = c_int(0)
    argv = CommandLineToArgvW(command, byref(argc))
    if not argv:
        # The docs say CommandLineToArgvW returns NULL on error, but they
        # don't describe any possible errors, so who knows when/if this happens.
        # Maybe only on low memory or something?
        raise WindowsCommandLineException("Windows could not parse command line: " + str(command))
    try:
        result = []
        i = 0
        while i < argc.value:
            try:
                result.append(str(argv[i]))
            except UnicodeEncodeError as e:
                message = ("Windows cannot represent this command line in its character encoding: " + command + ": " +
                           str(e))
                raise WindowsCommandLineException(message)
            i += 1
    finally:
        LocalFree(argv)
    return result


def windows_join_command_line(args):
    """Combine an argv into a Windows command line.

    Note: this can throw on some args you might pass in, but it should not throw
    on args you got from windows_split_command_line, because those are args
    that are representable as a command line. In other words, we throw on args
    that windows_split_command_line won't be able to reproduce.
    """
    if len(args) == 0:
        raise WindowsCommandLineException("Windows has no way to encode an empty arg list as a command line")

    # CommandLineToArgvW treats the first arg specially, which list2cmdline doesn't handle.
    # If the first arg starts with a quote, CommandLineToArgvW returns up to the second quote,
    # without interpreting any escapes. If the first arg doesn't start with a quote, then
    # no quoting/escaping is processed, the first arg is just left alone including embedded
    # quotes until a space (or control char) is encountered. So we can EITHER quote the whole
    # thing (if it contains no quotes) in order to embed spaces; OR don't quote it to embed
    # quotes but not spaces; but there is no way to have both quotes AND spaces in the first
    # arg, as far as I can tell. Also there's no way the first arg can start with a quote.
    if args[0].startswith('"'):
        # note: windows_split_command_line would never give us this args[0], because it would
        # strip off the leading quote
        raise WindowsCommandLineException("Windows does not allow the first arg to start with a quote: " + args[0])
    if '"' in args[0] and ' ' in args[0]:
        # note: windows_split_command_line would never give us this args[0], because it would
        # split on the space and make this two args
        raise WindowsCommandLineException("Windows does not allow the first arg to have both quotes and spaces: " +
                                          args[0])
    first_arg = args[0]
    if ' ' in first_arg:
        first_arg = '"%s"' % first_arg
    return first_arg + ' ' + subprocess.list2cmdline(args[1:])
