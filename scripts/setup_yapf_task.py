# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Setup script auxiliary process so we can "yapf" in parallel."""

from __future__ import print_function, absolute_import

from setup_atomic_replace import atomic_replace

import codecs
import sys


def _format_file(path):
    import platform
    from yapf.yapflib.yapf_api import FormatFile
    config = """{
column_limit : 120
}"""

    try:
        # It might be tempting to use the "inplace" option to
        # FormatFile, but it doesn't do an atomic replace, which
        # is dangerous, so don't use it unless you submit a fix to
        # yapf.
        (contents, encoding, changed) = FormatFile(path, style_config=config)
        if platform.system() == 'Windows':
            # yapf screws up line endings on windows
            with codecs.open(path, 'r', encoding) as file:
                old_contents = file.read()
            contents = contents.replace("\r\n", "\n")
            if len(old_contents) == 0:
                # windows yapf seems to force a newline? I dunno
                contents = ""
            changed = (old_contents != contents)
    except Exception as e:
        error = "yapf crashed on {path}: {error}".format(path=path, error=e)
        print(error, file=sys.stderr)
        return False

    if changed:
        atomic_replace(path, contents, encoding)
        print("Reformatted:     " + path)
        return False
    else:
        return True
        # print("No reformatting: " + path)


exit_code = 0
for filename in sys.argv[1:]:
    if not _format_file(filename):
        exit_code = 1
sys.exit(exit_code)
