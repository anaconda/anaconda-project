# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from anaconda_project.internal.rename import rename_over_existing
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents

import errno
import os
import pytest


def _raise_file_exists(dst):
    try:
        raise FileExistsError(errno.EEXIST, "Cannot create a file when that file already exists", dst)
    except NameError:
        raise IOError(errno.EEXIST, "Cannot create a file when that file already exists")


def test_rename_target_does_not_exist():
    def do_test(dirname):
        name1 = os.path.join(dirname, "foo")
        name2 = os.path.join(dirname, "bar")
        assert os.path.exists(name1)
        assert not os.path.exists(name2)
        assert open(name1).read() == 'stuff-foo'

        rename_over_existing(name1, name2)

        assert not os.path.exists(name1)
        assert os.path.exists(name2)
        assert open(name2).read() == 'stuff-foo'

    with_directory_contents(dict(foo='stuff-foo'), do_test)


def test_rename_target_does_exist():
    def do_test(dirname):
        name1 = os.path.join(dirname, "foo")
        name2 = os.path.join(dirname, "bar")
        assert os.path.exists(name1)
        assert os.path.exists(name2)
        assert open(name1).read() == 'stuff-foo'
        assert open(name2).read() == 'stuff-bar'

        rename_over_existing(name1, name2)

        assert not os.path.exists(name1)
        assert os.path.exists(name2)
        assert open(name2).read() == 'stuff-foo'

    with_directory_contents(dict(foo='stuff-foo', bar='stuff-bar'), do_test)


def test_rename_target_does_exist_simulating_windows(monkeypatch):
    def do_test(dirname):
        name1 = os.path.join(dirname, "foo")
        name2 = os.path.join(dirname, "bar")
        assert os.path.exists(name1)
        assert os.path.exists(name2)
        assert open(name1).read() == 'stuff-foo'
        assert open(name2).read() == 'stuff-bar'

        saved_backup = {}

        from os import rename as real_rename

        def mock_rename(src, dst):
            if '.bak' in dst:
                saved_backup['path'] = dst
            if os.path.exists(dst):
                _raise_file_exists(dst)
            else:
                real_rename(src, dst)

        monkeypatch.setattr('os.rename', mock_rename)

        rename_over_existing(name1, name2)

        assert not os.path.exists(name1)
        assert os.path.exists(name2)
        assert open(name2).read() == 'stuff-foo'
        assert not os.path.exists(saved_backup['path'])

    with_directory_contents(dict(foo='stuff-foo', bar='stuff-bar'), do_test)


def test_rename_target_to_backup_fails(monkeypatch):
    def do_test(dirname):
        name1 = os.path.join(dirname, "foo")
        name2 = os.path.join(dirname, "bar")
        assert os.path.exists(name1)
        assert os.path.exists(name2)
        assert open(name1).read() == 'stuff-foo'
        assert open(name2).read() == 'stuff-bar'

        from os import rename as real_rename

        def mock_rename(src, dst):
            if os.path.exists(dst):
                _raise_file_exists(dst)
            elif '.bak' in dst:
                raise OSError("Failing rename to backup")
            else:
                real_rename(src, dst)

        monkeypatch.setattr('os.rename', mock_rename)

        with pytest.raises(OSError) as excinfo:
            rename_over_existing(name1, name2)
        assert 'Failing rename to backup' in repr(excinfo.value)

        assert os.path.exists(name1)
        assert os.path.exists(name2)
        assert open(name1).read() == 'stuff-foo'
        assert open(name2).read() == 'stuff-bar'

    with_directory_contents(dict(foo='stuff-foo', bar='stuff-bar'), do_test)


def test_rename_after_backup_fails(monkeypatch):
    def do_test(dirname):
        name1 = os.path.join(dirname, "foo")
        name2 = os.path.join(dirname, "bar")
        assert os.path.exists(name1)
        assert os.path.exists(name2)
        assert open(name1).read() == 'stuff-foo'
        assert open(name2).read() == 'stuff-bar'

        saved_backup = {}

        from os import rename as real_rename

        def mock_rename(src, dst):
            if '.bak' in dst:
                saved_backup['path'] = dst
            if os.path.exists(dst):
                _raise_file_exists(dst)
            elif 'path' in saved_backup and os.path.exists(saved_backup['path']) and src != saved_backup['path']:
                assert not os.path.exists(name2)
                assert os.path.exists(saved_backup['path'])
                raise OSError("Failed to copy after backup")
            else:
                real_rename(src, dst)

        monkeypatch.setattr('os.rename', mock_rename)

        with pytest.raises(OSError) as excinfo:
            rename_over_existing(name1, name2)
        assert 'Failed to copy after backup' in repr(excinfo.value)

        assert os.path.exists(name1)
        assert os.path.exists(name2)
        assert open(name1).read() == 'stuff-foo'
        assert open(name2).read() == 'stuff-bar'
        assert not os.path.exists(saved_backup['path'])

    with_directory_contents(dict(foo='stuff-foo', bar='stuff-bar'), do_test)


def test_rename_target_does_exist_simulating_windows_remove_backup_fails(monkeypatch):
    def do_test(dirname):
        name1 = os.path.join(dirname, "foo")
        name2 = os.path.join(dirname, "bar")
        assert os.path.exists(name1)
        assert os.path.exists(name2)
        assert open(name1).read() == 'stuff-foo'
        assert open(name2).read() == 'stuff-bar'

        saved_backup = {}

        from os import rename as real_rename

        def mock_rename(src, dst):
            if '.bak' in dst:
                saved_backup['path'] = dst
            if os.path.exists(dst):
                _raise_file_exists(dst)
            else:
                real_rename(src, dst)

        monkeypatch.setattr('os.rename', mock_rename)

        def mock_remove(filename):
            raise OSError("not removing")

        monkeypatch.setattr('os.remove', mock_remove)

        # we shouldn't throw if we can't remove the backup
        rename_over_existing(name1, name2)

        assert not os.path.exists(name1)
        assert os.path.exists(name2)
        assert open(name2).read() == 'stuff-foo'
        # backup file gets left around
        assert os.path.exists(saved_backup['path'])

        # otherwise the os.remove monkeypatch affects cleaning up the tmp
        # directory - but only on python 2.
        monkeypatch.undo()

    with_directory_contents(dict(foo='stuff-foo', bar='stuff-bar'), do_test)


def test_rename_other_error_besides_eexist(monkeypatch):
    def do_test(dirname):
        name1 = os.path.join(dirname, "foo")
        name2 = os.path.join(dirname, "bar")
        assert os.path.exists(name1)
        assert os.path.exists(name2)
        assert open(name1).read() == 'stuff-foo'
        assert open(name2).read() == 'stuff-bar'

        def mock_rename(src, dst):
            raise IOError("it all went wrong")

        monkeypatch.setattr('os.rename', mock_rename)

        with pytest.raises(IOError) as excinfo:
            rename_over_existing(name1, name2)
        assert 'it all went wrong' in str(excinfo.value)

    with_directory_contents(dict(foo='stuff-foo', bar='stuff-bar'), do_test)
