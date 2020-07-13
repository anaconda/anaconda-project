# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import os
import shutil
import tempfile
import zipfile

from anaconda_project.internal import rename


# we overwrite as long as the zip contains a file and target_path
# is a file, or the zip is a dir and target_path is a dir, but if
# they don't match we don't overwrite. Hopefully this will catch
# most mistaken collisions.
def unpack_zip(zip_path, target_path, errors):
    try:
        with zipfile.ZipFile(zip_path, mode='r') as zf:
            target_dir, target_file = os.path.split(target_path)
            tmp_dir = tempfile.mkdtemp(prefix=(target_path + "_tmp"), dir=target_dir)
            try:
                zf.extractall(tmp_dir)
                extracted = os.listdir(tmp_dir)
                if len(extracted) == 0:
                    errors.append("Zip archive was empty.")
                    return False
                elif len(extracted) == 1 and extracted[0] == target_file:
                    # don't keep a pointless directory level, if
                    # the zip just contains a single directory or
                    # file with the same name as the target
                    src_path = os.path.join(tmp_dir, extracted[0])
                else:
                    src_path = tmp_dir
                src_is_dir = os.path.isdir(src_path)
                target_is_dir = os.path.isdir(target_path)
                if os.path.exists(target_path) and (src_is_dir != target_is_dir):
                    if src_is_dir:
                        errors.append("%s exists and isn't a directory, not unzipping a directory over it." %
                                      target_path)
                    else:
                        errors.append("%s exists and is a directory, not unzipping a plain file over it." % target_path)
                    return False
                else:
                    rename.rename_over_existing(src_path, target_path)
            finally:
                if os.path.isdir(tmp_dir):
                    shutil.rmtree(path=tmp_dir)
            return True
    except Exception as e:
        errors.append("Failed to unzip %s: %s" % (zip_path, str(e)))
        return False
