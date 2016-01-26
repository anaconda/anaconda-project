from __future__ import absolute_import, print_function

from tornado.ioloop import IOLoop

from project.internal.ui_server import UIServer, UIServerDoneEvent
from project.internal.test.http_utils import http_get, http_post


def test_ui_server():
    io_loop = IOLoop()
    io_loop.make_current()

    events = []

    def event_handler(event):
        events.append(event)

    server = UIServer(event_handler, io_loop)

    get_response = http_get(io_loop, server.url)
    print(repr(get_response))
    post_response = http_post(io_loop, server.url, body="")
    print(repr(post_response))

    server.unlisten()

    assert len(events) == 1
    assert isinstance(events[0], UIServerDoneEvent)
