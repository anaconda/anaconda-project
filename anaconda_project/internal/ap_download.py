#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Helper invoked by `prepare` tasks in pixi.toml files converted from
anaconda-project.yml. Fetches one download at a time, skipping if the
target file already exists.

Usage:
    python ap_download.py <url> <filename> [<description>] \\
        [--md5 <hex> | --sha1 <hex> | --sha224 <hex> | --sha256 <hex> | \\
         --sha384 <hex> | --sha512 <hex>]

Pure stdlib: urllib + hashlib + os, so it runs in any conda env that
has python.

When a checksum flag is supplied, the file is verified after download
and removed if the hash doesn't match. An already-on-disk file is also
verified against the supplied checksum; a mismatch is treated as a
real error rather than silently re-fetching, since the file may have
been edited intentionally.
"""
from __future__ import absolute_import, print_function

import hashlib
import os
import sys
import urllib.request


_HASH_ALGORITHMS = ('md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512')


def _compute_hash(filename, algorithm):
    h = hashlib.new(algorithm)
    with open(filename, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _parse_args(argv):
    positional = []
    hash_algorithm = None
    hash_value = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg.startswith('--'):
            algo = arg[2:]
            if algo not in _HASH_ALGORITHMS:
                print('unknown flag: {}'.format(arg), file=sys.stderr)
                return None
            if hash_algorithm is not None:
                print('multiple checksum flags: {} and {}'.format(
                    hash_algorithm, algo), file=sys.stderr)
                return None
            if i + 1 >= len(argv):
                print('flag {} requires a value'.format(arg), file=sys.stderr)
                return None
            hash_algorithm = algo
            hash_value = argv[i + 1].lower()
            i += 2
        else:
            positional.append(arg)
            i += 1

    if len(positional) not in (2, 3):
        return None
    return positional, hash_algorithm, hash_value


def main(argv):
    parsed = _parse_args(argv)
    if parsed is None:
        print('usage: python ap_download.py <url> <filename> [<description>] '
              '[--md5|--sha1|--sha224|--sha256|--sha384|--sha512 <hex>]',
              file=sys.stderr)
        return 2

    positional, hash_algorithm, hash_value = parsed
    url = positional[0]
    filename = positional[1]
    description = positional[2] if len(positional) == 3 else filename

    if os.path.exists(filename):
        if hash_algorithm is not None:
            actual = _compute_hash(filename, hash_algorithm)
            if actual != hash_value:
                print('[prepare] {}: existing file at {} has wrong {} '
                      '(expected {}, got {})'.format(
                          description, filename, hash_algorithm,
                          hash_value, actual),
                      file=sys.stderr)
                return 1
        print('[prepare] {}: exists at {}'.format(description, filename))
        return 0

    parent = os.path.dirname(filename)
    if parent:
        os.makedirs(parent, exist_ok=True)

    print('[prepare] {}: fetching {} -> {}'.format(description, url, filename))
    urllib.request.urlretrieve(url, filename)

    if hash_algorithm is not None:
        actual = _compute_hash(filename, hash_algorithm)
        if actual != hash_value:
            os.remove(filename)
            print('[prepare] {}: {} mismatch (expected {}, got {}); '
                  'removed {}'.format(description, hash_algorithm,
                                      hash_value, actual, filename),
                  file=sys.stderr)
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
