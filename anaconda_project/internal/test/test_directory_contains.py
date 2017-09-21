# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import os

from anaconda_project.internal.directory_contains import (directory_contains_subdirectory,
                                                          subdirectory_relative_to_directory)
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents


def test_does_contain():
    def check_does_contain(dirname):
        subdir = os.path.join(dirname, "foo")
        # subdir doesn't have to actually exist, so don't create it
        assert directory_contains_subdirectory(dirname, subdir)
        subsubdir = os.path.join(subdir, "bar")
        assert directory_contains_subdirectory(dirname, subsubdir)
        assert directory_contains_subdirectory(subdir, subsubdir)

    with_directory_contents(dict(), check_does_contain)


def test_does_not_contain():
    def check_does_not_contain(dirname):
        assert not directory_contains_subdirectory(dirname, "/")
        assert not dirname.endswith("/")
        common_prefix_not_subdir = dirname + "foobar"
        assert not directory_contains_subdirectory(dirname, common_prefix_not_subdir)
        # we don't contain ourselves
        assert not directory_contains_subdirectory(dirname, dirname)

    with_directory_contents(dict(), check_does_not_contain)


def test_make_relative():
    def check(dirname):
        foo = os.path.join(dirname, 'foo')
        assert 'foo' == subdirectory_relative_to_directory(foo, dirname)

        foobar = os.path.join(dirname, os.path.join('foo', 'bar'))
        assert os.path.join('foo', 'bar') == subdirectory_relative_to_directory(foobar, dirname)

        # keep the path absolute if it isn't inside the parent
        parent_of_dirname = os.path.dirname(dirname)
        assert parent_of_dirname == subdirectory_relative_to_directory(parent_of_dirname, dirname)

    with_directory_contents(dict(), check)
