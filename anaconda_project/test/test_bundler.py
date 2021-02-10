# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import os

from anaconda_project import archiver
from anaconda_project import projectignore
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.internal.test.fake_frontend import FakeFrontend


def test_parse_ignore_file():
    def check(dirname):
        frontend = FakeFrontend()
        patterns = archiver._parse_ignore_file(os.path.join(dirname, ".projectignore"), frontend)
        assert [] == frontend.errors

        pattern_strings = [pattern.pattern for pattern in patterns]

        assert set(pattern_strings) == {
            'bar', '/baz', 'whitespace_surrounding', 'foo # this comment will be part of the pattern',
            '#patternwithhash', 'hello'
        }

    with_directory_contents(
        {
            ".projectignore":
            """
# this is a sample .projectignore
   # there can be whitespace before the comment
bar
/baz
   whitespace_surrounding%s
foo # this comment will be part of the pattern
\\#patternwithhash

# blank line above me

hello

        """ % ("   ")
        }, check)


def test_parse_missing_ignore_file():
    def check(dirname):
        frontend = FakeFrontend()
        patterns = archiver._parse_ignore_file(os.path.join(dirname, ".projectignore"), frontend)
        assert [] == frontend.errors

        pattern_strings = [pattern.pattern for pattern in patterns]

        assert pattern_strings == []

    with_directory_contents(dict(), check)


def test_parse_ignore_file_with_io_error(monkeypatch):
    def check(dirname):
        frontend = FakeFrontend()
        ignorefile = os.path.join(dirname, ".projectignore")

        from codecs import open as real_open

        def mock_codecs_open(*args, **kwargs):
            if args[0].endswith(".projectignore"):
                raise IOError("NOPE")
            else:
                return real_open(*args, **kwargs)

        monkeypatch.setattr('codecs.open', mock_codecs_open)

        patterns = archiver._parse_ignore_file(ignorefile, frontend)
        assert patterns is None
        assert ["Failed to read %s: NOPE" % ignorefile] == frontend.errors

        # enable cleaning it up
        os.chmod(ignorefile, 0o777)

    with_directory_contents({".projectignore": ""}, check)


def test_parse_default_ignore_file():
    def check(dirname):
        projectignore.add_projectignore_if_none(dirname)
        ignorefile = os.path.join(dirname, ".projectignore")
        assert os.path.isfile(ignorefile)

        frontend = FakeFrontend()
        patterns = archiver._parse_ignore_file(ignorefile, frontend)
        assert [] == frontend.errors

        pattern_strings = [pattern.pattern for pattern in patterns]

        assert pattern_strings == [
            '*.pyc', '*.pyd', '*.pyo', '__pycache__/', '.ipynb_checkpoints/', '.Trash-*/', '/.spyderproject'
        ]

    with_directory_contents(dict(), check)


def _test_file_pattern_matcher(tests, is_directory):
    class FakeInfo(object):
        pass

    for pattern_string in tests.keys():
        pattern = archiver._FilePattern(pattern_string)
        should_match = tests[pattern_string]['yes']
        should_not_match = tests[pattern_string]['no']
        matched = []
        did_not_match = []
        for filename in (should_match + should_not_match):
            info = FakeInfo()
            setattr(info, 'unixified_relative_path', filename)
            setattr(info, 'is_directory', is_directory)
            if pattern.matches(info):
                matched.append(filename)
            else:
                did_not_match.append(filename)
        assert should_match == matched
        assert should_not_match == did_not_match


def test_file_pattern_matcher_non_directories():
    tests = {
        'foo': {
            'yes': ['foo', 'bar/foo', 'foo/bar'],
            'no': ['bar', 'foobar', 'barfoo']
        },
        '/foo': {
            'yes': ['foo', 'foo/bar'],
            'no': ['barfoo', 'bar/foo', 'bar', 'foobar']
        },
        'foo/': {
            'yes': [],
            'no': ['foo', 'barfoo', 'bar/foo', 'foo/bar', 'bar', 'foobar']
        },
        '/foo/': {
            'yes': [],
            'no': ['foo', 'barfoo', 'bar/foo', 'foo/bar', 'bar', 'foobar']
        },
    }

    _test_file_pattern_matcher(tests, is_directory=False)


def test_file_pattern_matcher_with_directories():
    tests = {
        'foo': {
            'yes': ['foo', 'bar/foo', 'foo/bar'],
            'no': ['bar', 'foobar', 'barfoo']
        },
        '/foo': {
            'yes': ['foo', 'foo/bar'],
            'no': ['barfoo', 'bar/foo', 'bar', 'foobar']
        }
    }

    # we'll say these are all dirs, so trailing / shouldn't matter
    tests['foo/'] = tests['foo']
    tests['/foo/'] = tests['/foo']

    _test_file_pattern_matcher(tests, is_directory=True)
