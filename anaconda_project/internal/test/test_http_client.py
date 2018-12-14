# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from anaconda_project.internal.http_client import FileDownloader
from anaconda_project.internal.test.http_server import HttpServerTestContext
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents

from tornado.ioloop import IOLoop

import os
import sys
import platform
import stat


def _download_file(length, hash_algorithm):
    def inside_directory_download_file(dirname):
        filename = os.path.join(dirname, "downloaded-file")
        with HttpServerTestContext() as server:
            url = server.new_download_url(download_length=length, hash_algorithm=hash_algorithm)
            download = FileDownloader(url=url, filename=filename, hash_algorithm=hash_algorithm)
            response = IOLoop.current().run_sync(download.run)
            assert [] == download.errors
            assert response is not None
            assert response.code == 200
            if hash_algorithm:
                server_hash = server.server_computed_hash_for_downloaded_url(url)
                assert download.hash == server_hash
            statinfo = os.stat(filename)
            assert statinfo.st_size == length
            assert not os.path.isfile(filename + ".part")

    with_directory_contents(dict(), inside_directory_download_file)


def test_download_empty_file_md5():
    _download_file(0, 'md5')


def test_download_small_file_md5():
    _download_file(1024, 'md5')


def test_download_small_file_hashless():
    _download_file(1024, None)


def test_download_medium_file_md5():
    _download_file(1024 * 1024, 'md5')


def test_download_medium_file_sha1():
    _download_file(1024 * 1024, 'sha1')


# this takes too long so disabled via underscore-prefix by default.
# uncomment it for manual testing if desired.
def _test_download_huge_file_md5():
    kilo = 1024
    mega = kilo * 1024
    giga = mega * 1024
    _download_file(int(giga * 0.2), 'md5')


def test_download_has_http_error():
    def inside_directory_get_http_error(dirname):
        filename = os.path.join(dirname, "downloaded-file")
        with HttpServerTestContext() as server:
            url = server.error_url
            download = FileDownloader(url=url, filename=filename, hash_algorithm='md5')
            response = IOLoop.current().run_sync(download.run)
            assert ['Failed download to %s: HTTP 404: Not Found' % filename] == download.errors
            assert response is None
            assert not os.path.isfile(filename)
            assert not os.path.isfile(filename + ".part")

    with_directory_contents(dict(), inside_directory_get_http_error)


def test_download_fail_to_create_directory(monkeypatch):
    def inside_directory_fail_to_create_directory(dirname):
        def mock_makedirs(name):
            raise IOError("Cannot create %s" % name)

        monkeypatch.setattr('anaconda_project.internal.makedirs.makedirs_ok_if_exists', mock_makedirs)
        filename = os.path.join(dirname, "downloaded-file")
        with HttpServerTestContext() as server:
            url = server.error_url
            download = FileDownloader(url=url, filename=filename, hash_algorithm='md5')
            response = IOLoop.current().run_sync(download.run)
            assert ["Could not create directory '%s': Cannot create %s" % (dirname, dirname)] == download.errors
            assert response is None
            assert not os.path.isfile(filename)
            assert not os.path.isfile(filename + ".part")

    with_directory_contents(dict(), inside_directory_fail_to_create_directory)


def test_download_fail_to_open_file(monkeypatch):
    def inside_directory_fail_to_open_file(dirname):
        statinfo = os.stat(dirname)
        try:
            filename = os.path.join(dirname, "downloaded-file")
            # make the open fail
            if platform.system() == 'Windows':
                # windows does not have read-only directories so we have to
                # make the file read-only
                with open(filename + ".part", 'wb') as file:
                    file.write("".encode())
                os.chmod(filename + ".part", stat.S_IREAD)
            else:
                os.chmod(dirname, stat.S_IREAD)

            with HttpServerTestContext() as server:
                url = server.error_url
                download = FileDownloader(url=url, filename=filename, hash_algorithm='md5')
                response = IOLoop.current().run_sync(download.run)
                filename_with_weird_extra_slashes = filename
                if platform.system() == 'Windows':
                    # I dunno. that's what Windows gives us.
                    filename_with_weird_extra_slashes = filename.replace("\\", "\\\\")
                assert [
                    "Failed to open %s.part: [Errno 13] Permission denied: '%s.part'" %
                    (filename, filename_with_weird_extra_slashes)
                ] == download.errors
                assert response is None
                assert not os.path.isfile(filename)
                if platform.system() != 'Windows':
                    # on windows we created this ourselves to cause the open error above
                    assert not os.path.isfile(filename + ".part")
        finally:
            # put this back so we don't get an exception cleaning up the directory
            os.chmod(dirname, statinfo.st_mode)
            if platform.system() == 'Windows':
                os.chmod(filename + ".part", stat.S_IWRITE)

    with_directory_contents(dict(), inside_directory_fail_to_open_file)


class _FakeFileFailsToWrite(object):
    def write(self, chunk):
        raise IOError("FAIL")

    def close(self):
        pass


def test_download_fail_to_write_file(monkeypatch):
    def inside_directory_fail_to_write_file(dirname):
        filename = os.path.join(dirname, "downloaded-file")
        with HttpServerTestContext() as server:
            url = server.new_download_url(download_length=(1024 * 1025), hash_algorithm='md5')
            download = FileDownloader(url=url, filename=filename, hash_algorithm='md5')

            def mock_open(filename, mode):
                return _FakeFileFailsToWrite()

            if sys.version_info > (3, 0):
                monkeypatch.setattr('builtins.open', mock_open)
            else:
                monkeypatch.setattr('__builtin__.open', mock_open)

            response = IOLoop.current().run_sync(download.run)
            assert ["Failed to write to %s: FAIL" % (filename + ".part")] == download.errors
            assert response.code == 200
            assert not os.path.isfile(filename)
            assert not os.path.isfile(filename + ".part")

    with_directory_contents(dict(), inside_directory_fail_to_write_file)


def test_download_fail_to_rename_tmp_file(monkeypatch):
    def inside_directory_fail_to_rename_tmp_file(dirname):
        filename = os.path.join(dirname, "downloaded-file")
        with HttpServerTestContext() as server:
            url = server.new_download_url(download_length=56780, hash_algorithm='md5')
            download = FileDownloader(url=url, filename=filename, hash_algorithm='md5')

            def mock_rename(src, dest):
                raise OSError("FAIL")

            monkeypatch.setattr('anaconda_project.internal.rename.rename_over_existing', mock_rename)

            response = IOLoop.current().run_sync(download.run)
            assert ["Failed to rename %s to %s: FAIL" % (filename + ".part", filename)] == download.errors
            assert response.code == 200
            assert not os.path.isfile(filename)
            assert not os.path.isfile(filename + ".part")

    with_directory_contents(dict(), inside_directory_fail_to_rename_tmp_file)
