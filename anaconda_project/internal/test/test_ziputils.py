# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import codecs
import os

from anaconda_project.internal.ziputils import unpack_zip
from anaconda_project.internal.test.tmpfile_utils import (with_directory_contents, with_tmp_zipfile)


def test_unzip_single_file_different_name():
    def do_test(zipname, workingdir):
        target_path = os.path.join(workingdir, 'boo')  # different name from what's in the zip
        errors = []
        unpack_zip(zipname, target_path, errors)
        assert [] == errors
        assert os.path.isdir(target_path)
        assert codecs.open(os.path.join(target_path, 'foo'), 'r', 'utf-8').read() == "hello world\n"

    with_tmp_zipfile(dict(foo="hello world\n"), do_test)


def test_unzip_single_file_same_name():
    def do_test(zipname, workingdir):
        target_path = os.path.join(workingdir, 'foo')  # same name as what's in the zip
        errors = []
        unpack_zip(zipname, target_path, errors)
        assert [] == errors
        assert os.path.isfile(target_path)
        assert codecs.open(target_path, 'r', 'utf-8').read() == "hello world\n"

    with_tmp_zipfile(dict(foo="hello world\n"), do_test)


def test_unzip_two_files():
    def do_test(zipname, workingdir):
        target_path = os.path.join(workingdir, 'boo')
        errors = []
        unpack_zip(zipname, target_path, errors)
        assert [] == errors
        assert os.path.isdir(target_path)
        assert codecs.open(os.path.join(target_path, 'foo'), 'r', 'utf-8').read() == "hello world\n"
        assert codecs.open(os.path.join(target_path, 'bar'), 'r', 'utf-8').read() == "goodbye world\n"

    with_tmp_zipfile(dict(foo="hello world\n", bar="goodbye world\n"), do_test)


def test_unzip_one_directory_different_name():
    def do_test(zipname, workingdir):
        target_path = os.path.join(workingdir, 'boo')  # different name from what's in the zip
        errors = []
        unpack_zip(zipname, target_path, errors)
        assert [] == errors
        assert os.path.isdir(target_path)
        assert os.path.isdir(os.path.join(target_path, 'foo'))
        assert codecs.open(os.path.join(target_path, 'foo', 'bar'), 'r', 'utf-8').read() == "hello world\n"

    with_tmp_zipfile({'foo/bar': "hello world\n"}, do_test)


def test_unzip_one_directory_same_name():
    def do_test(zipname, workingdir):
        target_path = os.path.join(workingdir, 'foo')  # same name as what's in the zip
        errors = []
        unpack_zip(zipname, target_path, errors)
        assert [] == errors
        assert os.path.isdir(target_path)
        assert codecs.open(os.path.join(target_path, 'bar'), 'r', 'utf-8').read() == "hello world\n"

    with_tmp_zipfile({'foo/bar': "hello world\n"}, do_test)


def test_unzip_empty_zip():
    def do_test(zipname, workingdir):
        target_path = os.path.join(workingdir, 'boo')
        errors = []
        unpack_zip(zipname, target_path, errors)
        assert ['Zip archive was empty.'] == errors
        assert not os.path.isdir(target_path)

    with_tmp_zipfile(dict(), do_test)


# we do rename directories over directories
def test_unzip_target_already_exists_and_is_directory():
    def do_test(zipname, workingdir):
        target_path = os.path.join(workingdir, 'boo')
        os.makedirs(target_path)
        errors = []
        unpack_zip(zipname, target_path, errors)
        assert [] == errors
        assert os.path.isdir(target_path)
        assert codecs.open(os.path.join(target_path, 'foo'), 'r', 'utf-8').read() == "hello world\n"
        assert codecs.open(os.path.join(target_path, 'bar'), 'r', 'utf-8').read() == "goodbye world\n"

    with_tmp_zipfile(dict(foo="hello world\n", bar="goodbye world\n"), do_test)


# we do rename directories over directories even if the dir is inside the zip
def test_unzip_target_already_exists_and_is_directory_and_single_dir_in_zip():
    def do_test(zipname, workingdir):
        target_path = os.path.join(workingdir, 'boo')  # different name from dir in zip
        os.makedirs(target_path)
        errors = []
        unpack_zip(zipname, target_path, errors)
        assert [] == errors
        assert os.path.isdir(target_path)
        assert os.path.isdir(os.path.join(target_path, 'foo'))
        assert codecs.open(os.path.join(target_path, 'foo', 'bar'), 'r', 'utf-8').read() == "hello world\n"

    with_tmp_zipfile({'foo/bar': "hello world\n"}, do_test)


# we do rename directories over directories even if we strip the toplevel dir from the zip
def test_unzip_target_already_exists_and_is_directory_and_single_dir_in_zip_same_name():
    def do_test(zipname, workingdir):
        target_path = os.path.join(workingdir, 'foo')  # same name as dir in zip
        os.makedirs(target_path)
        errors = []
        unpack_zip(zipname, target_path, errors)
        assert [] == errors
        assert os.path.isdir(target_path)
        assert codecs.open(os.path.join(target_path, 'bar'), 'r', 'utf-8').read() == "hello world\n"

    with_tmp_zipfile({'foo/bar': "hello world\n"}, do_test)


# we don't rename a file over a directory when we discard the zip's dir due to same name
def test_unzip_target_already_exists_and_is_directory_and_single_file_in_zip_same_name():
    def do_test(zipname, workingdir):
        target_path = os.path.join(workingdir, 'foo')  # same name as file in zip
        os.makedirs(target_path)
        errors = []
        unpack_zip(zipname, target_path, errors)
        assert os.path.isdir(target_path)
        assert ["%s exists and is a directory, not unzipping a plain file over it." % target_path] == errors

    with_tmp_zipfile(dict(foo="hello world\n"), do_test)


# we do rename a directory over a directory if we keep the dir since the file has a different name
def test_unzip_target_already_exists_and_is_directory_and_single_file_in_zip_different_name():
    def do_test(zipname, workingdir):
        target_path = os.path.join(workingdir, 'boo')  # different name from file in zip
        os.makedirs(target_path)
        errors = []
        unpack_zip(zipname, target_path, errors)
        assert [] == errors
        assert os.path.isdir(target_path)
        assert codecs.open(os.path.join(target_path, 'foo'), 'r', 'utf-8').read() == "hello world\n"

    with_tmp_zipfile(dict(foo="hello world\n"), do_test)


# we don't rename directories over files even if the dirs are inside the zip
def test_unzip_target_already_exists_and_is_file_and_single_dir_in_zip():
    def do_test(zipname, workingdir):
        target_path = os.path.join(workingdir, 'boo')  # different name so we should keep "foo"
        with codecs.open(target_path, 'w', 'utf-8') as f:
            f.write("\n")
        errors = []
        unpack_zip(zipname, target_path, errors)
        assert os.path.isfile(target_path)
        assert [("%s exists and isn't a directory, not unzipping a directory over it." % target_path)] == errors

    with_tmp_zipfile({'foo/bar': "hello world\n"}, do_test)


# we don't rename directories over files if the zip has no root dir
def test_unzip_target_already_exists_and_is_file():
    def do_test(zipname, workingdir):
        target_path = os.path.join(workingdir, 'boo')
        with codecs.open(target_path, 'w', 'utf-8') as f:
            f.write("\n")
        errors = []
        unpack_zip(zipname, target_path, errors)
        assert [("%s exists and isn't a directory, not unzipping a directory over it." % target_path)] == errors

    with_tmp_zipfile(dict(foo="hello world\n", bar="goodbye world\n"), do_test)


# we do rename files over files if they have the same name
def test_unzip_target_already_exists_and_is_file_and_single_file_in_zip_same_name():
    def do_test(zipname, workingdir):
        target_path = os.path.join(workingdir, 'foo')  # same name
        with codecs.open(target_path, 'w', 'utf-8') as f:
            f.write("\n")
        errors = []
        unpack_zip(zipname, target_path, errors)
        assert [] == errors
        assert os.path.isfile(target_path)
        assert codecs.open(target_path, 'r', 'utf-8').read() == "hello world\n"

    with_tmp_zipfile(dict(foo="hello world\n"), do_test)


# we don't rename files over files if the name is different
def test_unzip_target_already_exists_and_is_file_and_single_file_in_zip_different_name():
    def do_test(zipname, workingdir):
        target_path = os.path.join(workingdir, 'boo')  # different from the file in the zip
        with codecs.open(target_path, 'w', 'utf-8') as f:
            f.write("original\n")
        errors = []
        unpack_zip(zipname, target_path, errors)
        assert [("%s exists and isn't a directory, not unzipping a directory over it." % target_path)] == errors
        assert os.path.isfile(target_path)
        assert codecs.open(target_path, 'r', 'utf-8').read() == "original\n"

    with_tmp_zipfile(dict(foo="hello world\n"), do_test)


def test_unzip_bad_zipfile():
    def do_test(workingdir):
        zipname = os.path.join(workingdir, 'foo')
        target_path = os.path.join(workingdir, 'boo')
        errors = []
        unpack_zip(zipname, target_path, errors)
        assert [('Failed to unzip %s: File is not a zip file' % zipname)] == errors

    with_directory_contents(dict(foo="not a zip file\n"), do_test)
