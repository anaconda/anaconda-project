# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from tornado import httpclient
from tornado import gen
from tqdm import tqdm

import anaconda_project.internal.makedirs as makedirs
import anaconda_project.internal.rename as rename

import os
import hashlib


class FileDownloader(object):
    def __init__(self, url, filename, hash_algorithm=None):
        """Downloader for the given url to the given filename, computing the given hash.

        hash_algorithm is the name of a hash function in hashlib
        """
        self._url = url
        self._filename = filename
        self._hash_algorithm = hash_algorithm
        self._hash = None
        self._client = None
        self._errors = []
        self._progress = None

    @gen.coroutine
    def run(self):
        """Run the download on the given io_loop."""
        assert self._client is None

        dirname = os.path.dirname(self._filename)
        try:
            makedirs.makedirs_ok_if_exists(dirname)
        except Exception as e:
            self._errors.append("Could not create directory '%s': %s" % (dirname, e))
            raise gen.Return(None)

        if self._hash_algorithm is not None:
            hasher = getattr(hashlib, self._hash_algorithm)()
        self._client = httpclient.AsyncHTTPClient(
            # No need for this, and removed in 5.0 anyway
            # io_loop=io_loop,
            max_clients=1,
            # without this we buffer a huge amount
            # of stuff and then call the streaming_callback
            # once.
            max_buffer_size=1024 * 1024,
            # without this we 599 on large downloads
            max_body_size=100 * 1024 * 1024 * 1024,
            force_instance=True)

        tmp_filename = self._filename + ".part"
        try:
            _file = open(tmp_filename, 'wb')
        except EnvironmentError as e:
            self._errors.append("Failed to open %s: %s" % (tmp_filename, e))
            raise gen.Return(None)

        def cleanup_tmp():
            try:
                _file.close()
                # future: we could save it in order to try
                # resuming a failed download midstream, but
                # pointless until the download code above
                # knows how to resume.
                os.remove(tmp_filename)
            except EnvironmentError:
                pass

        def writer(chunk):
            if len(self._errors) > 0:
                return

            if self._hash_algorithm is not None:
                hasher.update(chunk)

            try:
                _file.write(chunk)
                if self._progress is not None:
                    self._progress.update(len(chunk) / 1024 / 1024)
            except EnvironmentError as e:
                # we can't actually throw this error or Tornado freaks out, so instead
                # we ignore all future chunks once we have an error, which does mean
                # we continue to download bytes that we don't use. yuck.
                self._errors.append("Failed to write to %s: %s" % (tmp_filename, e))

        def read_header(line):
            if 'content-length' in line.lower():
                file_size = int(line.split(':')[1]) / 1024 / 1024
                self._progress = tqdm(unit='MiB',
                                      total=file_size,
                                      unit_scale=True,
                                      desc=os.path.basename(self._filename))

        try:
            timeout_in_seconds = 60 * 10  # pretty long because we could be dealing with huge files
            request = httpclient.HTTPRequest(url=self._url,
                                             header_callback=read_header,
                                             streaming_callback=writer,
                                             request_timeout=timeout_in_seconds)
            try:
                response = yield self._client.fetch(request)
            except Exception as e:
                self._errors.append("Failed download to %s: %s" % (self._filename, str(e)))
                raise gen.Return(None)
            finally:
                if self._progress is not None:
                    self._progress.close()

            # assert fetch() was supposed to throw the error, not leave it here unthrown
            assert response.error is None

            if len(self._errors) == 0:
                try:
                    _file.close()  # be sure tmp_filename is flushed
                    rename.rename_over_existing(tmp_filename, self._filename)
                except EnvironmentError as e:
                    self._errors.append("Failed to rename %s to %s: %s" % (tmp_filename, self._filename, str(e)))

            if len(self._errors) == 0 and self._hash_algorithm is not None:
                self._hash = hasher.hexdigest()

            raise gen.Return(response)
        finally:
            cleanup_tmp()

    @property
    def hash(self):
        """Hash of the downloaded file if we succeeded in downloading it, None if we failed."""
        return self._hash

    @property
    def errors(self):
        """List of errors if we failed to download, empty list if we succeeded."""
        return self._errors
