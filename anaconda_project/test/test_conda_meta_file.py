# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
import os

from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.conda_meta_file import (CondaMetaFile, META_DIRECTORY, DEFAULT_RELATIVE_META_PATH,
                                          possible_meta_file_names)


def _use_existing_meta_file(relative_name):
    def check_file(dirname):
        filename = os.path.join(dirname, relative_name)
        assert os.path.exists(filename)
        meta_file = CondaMetaFile.load_for_directory(dirname)
        assert 'foo' == meta_file.name

    sample_content = "package:\n  name: foo\n"
    with_directory_contents({relative_name: sample_content}, check_file)


def test_use_existing_meta_file_default_name():
    _use_existing_meta_file(DEFAULT_RELATIVE_META_PATH)


def test_use_existing_meta_file_all_names():
    for name in possible_meta_file_names:
        _use_existing_meta_file(os.path.join(META_DIRECTORY, name))
