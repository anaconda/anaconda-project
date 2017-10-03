# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import os
import pytest

from anaconda_project.internal.makedirs import makedirs_ok_if_exists
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents


def test_makedirs_ok_if_exists():
    def do_test(dirname):
        dir1 = os.path.join(dirname, "foo")
        dir2 = os.path.join(dir1, "bar")
        dir3 = os.path.join(dir2, "baz")
        assert os.path.isdir(dirname)
        assert not os.path.isdir(dir1)
        assert not os.path.isdir(dir2)
        assert not os.path.isdir(dir3)

        makedirs_ok_if_exists(dir3)

        assert os.path.isdir(dir1)
        assert os.path.isdir(dir2)
        assert os.path.isdir(dir3)

    with_directory_contents(dict(), do_test)


def test_makedirs_ok_if_exists_fails_for_another_reason(monkeypatch):
    def do_test(dirname):
        def mock_mkdir_fails(path, mode):
            raise IOError("not EEXIST")

        monkeypatch.setattr("os.mkdir", mock_mkdir_fails)

        with pytest.raises(IOError) as excinfo:
            makedirs_ok_if_exists("foo/bar/baz")
        assert 'not EEXIST' in repr(excinfo.value)

    with_directory_contents(dict(), do_test)
