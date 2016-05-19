# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import os

from anaconda_project import bundler
from anaconda_project import project_ops
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents


def test_parse_ignore_file():
    def check(dirname):
        errors = []
        patterns = bundler._parse_ignore_file(os.path.join(dirname, ".projectignore"), errors)
        assert [] == errors

        pattern_strings = [pattern.pattern for pattern in patterns]

        assert pattern_strings == ['bar', '/baz', 'whitespace_surrounding',
                                   'foo # this comment will be part of the pattern', '#patternwithhash', 'hello']

    with_directory_contents(
        {".projectignore": """
# this is a sample .projectignore
   # there can be whitespace before the comment
bar
/baz
   whitespace_surrounding%s
foo # this comment will be part of the pattern
\#patternwithhash

# blank line above me

hello

        """ % ("   ")}, check)


def test_parse_missing_ignore_file():
    def check(dirname):
        errors = []
        patterns = bundler._parse_ignore_file(os.path.join(dirname, ".projectignore"), errors)
        assert [] == errors

        pattern_strings = [pattern.pattern for pattern in patterns]

        assert pattern_strings == []

    with_directory_contents(dict(), check)


def test_parse_ignore_file_with_io_error():
    def check(dirname):
        errors = []
        ignorefile = os.path.join(dirname, ".projectignore")
        os.chmod(ignorefile, 0)
        patterns = bundler._parse_ignore_file(ignorefile, errors)
        assert patterns is None
        assert len(errors) == 1  # exact message varies by OS

        # enable cleaning it up
        os.chmod(ignorefile, 0o777)

    with_directory_contents({".projectignore": ""}, check)


def test_parse_default_ignore_file():
    def check(dirname):
        project_ops._add_projectignore_if_none(dirname)
        ignorefile = os.path.join(dirname, ".projectignore")
        assert os.path.isfile(ignorefile)

        errors = []
        patterns = bundler._parse_ignore_file(ignorefile, errors)
        assert [] == errors

        pattern_strings = [pattern.pattern for pattern in patterns]

        assert pattern_strings == ['/project-local.yml', '__pycache__/', '*.pyc', '*.pyo', '*.pyd',
                                   '/.ipynb_checkpoints', '/.spyderproject']

    with_directory_contents(dict(), check)


def _test_file_pattern_matcher(tests, is_directory):
    class FakeInfo(object):
        pass

    for pattern_string in tests.keys():
        pattern = bundler._FilePattern(pattern_string)
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
