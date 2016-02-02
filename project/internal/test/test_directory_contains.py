from __future__ import absolute_import, print_function

import os

from project.internal.directory_contains import directory_contains_subdirectory
from project.internal.test.tmpfile_utils import with_directory_contents


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
