# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import json
import os
import socket
import sys
import threading

from tornado.ioloop import IOLoop
from tornado.httpserver import HTTPServer
from tornado.netutil import bind_sockets
from tornado.web import Application, RequestHandler
from tornado import gen


class ProjectViewHandler(RequestHandler):
    def __init__(self, application, *args, **kwargs):
        # Note: application is stored as self.application
        super(ProjectViewHandler, self).__init__(application, *args, **kwargs)

    def get(self, *args, **kwargs):
        # print("Received GET %r %r" % (args, kwargs), file=sys.stderr)
        path = args[0]
        if path == 'user':
            if 'auth' in self.application.server.fail_these:
                self.set_status(401)
            else:
                if 'missing_login' in self.application.server.fail_these:
                    self.set_header('Content-Type', 'application/json')
                    self.write('{}')
                else:
                    self.set_header('Content-Type', 'application/json')
                    self.write('{"login":"fake_username"}\n')
        elif path == 'user/foobar':
            self.set_header('Content-Type', 'application/json')
            self.write('{"login":"foobar"}\n')
        elif path == 'apps/fake_username/projects/fake_project':
            self.write('{"name":"fake_project"}')
            self.set_header('Content-Type', 'application/json')
            self.set_status(200)
        elif path == 'apps/fake_username/projects/fake_project/download':
            dirname = os.path.dirname(__file__)
            with open(os.path.join(dirname, 'fake_project.zip'), 'rb') as f:
                self.write(f.read())

            self.set_header('Content-Type', 'application/zip')
            self.set_header('Content-Disposition',
                            '''attachment; filename="fake_project.zip"; filename*=UTF-8\'\'fake_project.zip''')
            self.set_status(200)
        else:
            self.set_status(status_code=404)

    def post(self, *args, **kwargs):
        # print("Received POST %r %r" % (args, kwargs), file=sys.stderr)
        path = args[0]
        if path == 'apps/fake_username/projects':
            if 'create' in self.application.server.fail_these:
                self.set_status(501)
            else:
                self.set_header('Content-Type', 'application/json')
                self.write('{}\n')
        elif path.startswith('apps/fake_username/projects/'):
            path = path[len('apps/fake_username/projects/'):]
            [project, operation] = path.split("/", 1)
            # print("project=" + project + " operation=" + operation, file=sys.stderr)
            if operation == 'stage':
                if 'stage' in self.application.server.fail_these:
                    self.set_status(501)
                else:
                    body = json.loads(self.request.body.decode('utf-8'))
                    assert 'basename' in body
                    assert body['basename'] == self.application.server.expected_basename
                    post_url = self.application.server.url + "fake_s3"
                    self.set_header('Content-Type', 'application/json')
                    self.write(('{"post_url":"%s", ' + '"form_data":{"x-should-be-passed-back-to-us":"12345"},' +
                                '"dist_id":"rev42"}\n') % (post_url))
            elif operation == 'commit/rev42':
                if 'commit' in self.application.server.fail_these:
                    self.set_status(501)
                else:
                    self.set_header('Content-Type', 'application/json')
                    self.write('{"url":"http://example.com/whatevs"}')
            else:
                self.set_status(status_code=404)
        elif path == 'fake_s3':
            if 's3' in self.application.server.fail_these:
                self.set_status(501)
            else:
                if self.get_body_argument('x-should-be-passed-back-to-us') != '12345':
                    print("form_data for s3 wasn't sent", file=sys.stderr)
                    self.set_status(status_code=500)
                else:
                    assert 'file' in self.request.files
                    assert len(self.request.files['file']) == 1
                    fileinfo = self.request.files['file'][0]
                    assert fileinfo['filename'] == self.application.server.expected_basename
                    assert len(fileinfo['body']) > 100  # shouldn't be some tiny or empty thing
        else:
            self.set_status(status_code=404)


class FakeAnacondaApplication(Application):
    def __init__(self, server, **kwargs):
        self.server = server

        patterns = [(r'/(.*)', ProjectViewHandler)]
        super(FakeAnacondaApplication, self).__init__(patterns, **kwargs)


class FakeAnacondaServer(object):
    def __init__(self, fail_these, expected_basename):
        self.fail_these = fail_these
        self.expected_basename = expected_basename
        self._application = FakeAnacondaApplication(server=self)
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
        self._http.start(1)

    @property
    def port(self):
        return self._port

    @property
    def url(self):
        return "http://localhost:%d/" % self.port

    @gen.coroutine
    def close_all(self):
        self._http.close_all_connections()

    def unlisten(self):
        """Permanently close down the HTTP server, no longer listen on any sockets."""
        self._http.stop()
        yield self.close_all()


def _monkeypatch_client_config(monkeypatch, url):
    def _mock_get_config(user=True, site=True, remote_site=None):
        return {'url': url}

    # get_config moved into a `config` submodule at some point in anaconda-client
    try:
        import binstar_client.utils.config  # noqa # (unused import)
        monkeypatch.setattr('binstar_client.utils.config.get_config', _mock_get_config)
    except Exception:
        monkeypatch.setattr('binstar_client.utils.get_config', _mock_get_config)


class FakeServerContext(object):
    def __init__(self, monkeypatch, fail_these, expected_basename):
        self._monkeypatch = monkeypatch
        self._fail_these = fail_these
        self._expected_basename = expected_basename
        self._url = None
        self._loop = None
        self._started = threading.Condition()
        self._thread = threading.Thread(target=self._run)

    def __exit__(self, type, value, traceback):
        if self._loop is not None:
            # we can ONLY use add_callback here, since the loop is
            # running in a different thread.
            self._loop.add_callback(self._stop)
        self._thread.join()

    def __enter__(self):
        self._started.acquire()
        self._thread.start()
        self._started.wait()
        self._started.release()
        _monkeypatch_client_config(self._monkeypatch, self._url)
        return self._url

    def _run(self):
        self._loop = IOLoop()
        self._server = FakeAnacondaServer(fail_these=self._fail_these, expected_basename=self._expected_basename)
        self._url = self._server.url

        def notify_started():
            self._started.acquire()
            self._started.notify()
            self._started.release()

        self._loop.add_callback(notify_started)
        self._loop.start()
        # done
        self._server.unlisten()

    def _stop(self):
        def really_stop():
            if self._loop is not None:
                self._loop.stop()
                self._loop = None

        # the delay allows pending next-tick things to go ahead
        # and happen, which may avoid some problems with trying to
        # output to stdout after pytest closes it
        if self._loop is not None:
            self._loop.call_later(delay=0.05, callback=really_stop)


def fake_server(monkeypatch, fail_these=(), expected_basename='nope'):
    return FakeServerContext(monkeypatch, fail_these, expected_basename)
