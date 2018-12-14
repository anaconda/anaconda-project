# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import errno
import os
import uuid


def rename_over_existing(src, dest):
    try:
        # On Windows, this will throw EEXIST, on Linux it won't.
        # on Win32 / Python 2.7 it throws OSError instead of IOError
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
        else:
            raise e
