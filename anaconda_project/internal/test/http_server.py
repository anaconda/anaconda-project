# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from tornado.httpserver import HTTPServer
from tornado.netutil import bind_sockets
from tornado.web import Application, RequestHandler
from tornado import gen
import uuid
import hashlib
import socket


class _DownloadView(RequestHandler):
    def __init__(self, application, *args, **kwargs):
        # Note: application is stored as self.application
        super(_DownloadView, self).__init__(application, *args, **kwargs)

    @gen.coroutine
    def get(self, *args, **kwargs):
        download_id = self.get_argument("id")
        hash_algorithm = self.get_argument("hash_algorithm", None)
        length = int(self.get_argument("length"))

        print("Planning to send %d bytes" % length)
        if hash_algorithm:
            hasher = getattr(hashlib, hash_algorithm)()

        self.set_status(200)
        self.set_header('Content-Length', str(length))
        data = ("abcdefghijklmnop" * 20).encode("utf-8")
        remaining = length
        while remaining > 0:
            to_write = data[:remaining]
            if hash_algorithm:
                hasher.update(to_write)
            remaining = remaining - len(to_write)
            self.write(to_write)
            try:
                yield self.flush()
            except Exception as e:
                raise e

        if hash_algorithm:
            self.application.hashes[download_id] = hasher.hexdigest()

        self.finish()


class _ErrorView(RequestHandler):
    def __init__(self, application, *args, **kwargs):
        # Note: application is stored as self.application
        super(_ErrorView, self).__init__(application, *args, **kwargs)

    def get(self, *args, **kwargs):
        self.set_status(404)
        self.finish()


class _TestServerApplication(Application):
    def __init__(self, **kwargs):
        self.hashes = dict()
        patterns = [(r'/download', _DownloadView), (r'/error', _ErrorView)]
        super(_TestServerApplication, self).__init__(patterns, **kwargs)


class _TestServer(object):
    def __init__(self):
        self._application = _TestServerApplication()
        self._http = HTTPServer(self._application)

        # these would throw OSError on failure
        sockets = bind_sockets(port=None, address='127.0.0.1')

        self._port = None
        for s in sockets:
            # we have to find the ipv4 one
            if s.family == socket.AF_INET:
                self._port = s.getsockname()[1]
        assert self._port is not None

        self._http.add_sockets(sockets)

    @property
    def port(self):
        return self._port

    @property
    def url(self):
        return "http://localhost:%d/" % self.port

    def start(self):
        self._http.start(1)

    @gen.coroutine
    def close_all(self):
        self._http.close_all_connections()

    def unlisten(self):
        self._http.close_all_connections()
        yield self.close_all()

    @property
    def error_url(self):
        return self.url + "error"

    def new_download_url(self, download_length, hash_algorithm):
        url = (self.url + "download?id=" + str(uuid.uuid4()) + "&length=" + str(download_length))
        if hash_algorithm:
            url += "&hash_algorithm=" + hash_algorithm
        return url

    def server_computed_hash_for_downloaded_url(self, download_url):
        i = download_url.index("id=")
        download_id = download_url[(i + 3):][:36]
        if download_id not in self._application.hashes:
            raise RuntimeError("It looks like the download from %s did not complete" % download_url)
        return self._application.hashes[download_id]


class HttpServerTestContext(object):
    def __init__(self):
        self._server = _TestServer()

    def __exit__(self, type, value, traceback):
        self._server.unlisten()

    def __enter__(self):
        self._server.start()
        return self._server
