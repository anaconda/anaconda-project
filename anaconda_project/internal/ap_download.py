#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Helper invoked by `prepare` tasks in pixi.toml files converted from
anaconda-project.yml. Fetches one download at a time, skipping if the
target file already exists.

Usage:
    python ap_download.py <url> <filename> [<description>]

Pure stdlib: urllib + os, so it runs in any conda env that has python.
"""
from __future__ import absolute_import, print_function

import os
import sys
import urllib.request


def main(argv):
    if len(argv) not in (2, 3):
        print('usage: python ap_download.py <url> <filename> [<description>]',
              file=sys.stderr)
        return 2

    url = argv[0]
    filename = argv[1]
    description = argv[2] if len(argv) == 3 else filename

    if os.path.exists(filename):
        print('[prepare] {}: exists at {}'.format(description, filename))
        return 0

    parent = os.path.dirname(filename)
    if parent:
        os.makedirs(parent, exist_ok=True)

    print('[prepare] {}: fetching {} -> {}'.format(description, url, filename))
    urllib.request.urlretrieve(url, filename)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
