# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Setup script module with _atomic_replace function."""

from __future__ import print_function, absolute_import

import codecs
import errno
import os
import uuid


def _rename_over_existing(src, dest):
    try:
        # On Windows, this will throw EEXIST, on Linux it won't.
        # on Win32/Py2 it throws OSError instead of IOError
        os.rename(src, dest)
    except (OSError, IOError) as e:
        if e.errno == errno.EEXIST:
            # Clearly this song-and-dance is not in fact atomic,
            # but if something goes wrong putting the new file in
            # place at least the backup file might still be
            # around.
            backup = dest + ".bak-" + str(uuid.uuid4())
            os.rename(dest, backup)
            try:
                os.rename(src, dest)
            except Exception as e:
                os.rename(backup, dest)
                raise e
            finally:
                try:
                    os.remove(backup)
                except Exception:
                    pass


def atomic_replace(path, contents, encoding):
    import uuid

    tmp = path + "tmp-" + str(uuid.uuid4())
    try:
        with codecs.open(tmp, 'w', encoding) as file:
            file.write(contents)
            file.flush()
            file.close()
        _rename_over_existing(tmp, path)
    finally:
        try:
            os.remove(tmp)
        except (IOError, OSError):
            pass
