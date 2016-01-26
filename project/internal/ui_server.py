from __future__ import absolute_import, print_function

import socket

from tornado.httpserver import HTTPServer
from tornado.netutil import bind_sockets
from tornado.web import Application, RequestHandler


class UIServerEvent(object):
    pass


class UIServerDoneEvent(UIServerEvent):
    def __init__(self, should_we_prepare):
        super(UIServerDoneEvent, self).__init__()
        self.should_we_prepare = should_we_prepare


class PrepareViewHandler(RequestHandler):
    def __init__(self, application, *args, **kwargs):
        # Note: application is stored as self.application
        super(PrepareViewHandler, self).__init__(application, *args, **kwargs)

    def get(self, *args, **kwargs):
        # future: we will use some sort of template thing here
        page = """
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Project setup</title>
  </head>
  <body>
     <div>
         <form action="/" method="post">
            <input type="submit" value="Setup everything"></input>
         </form>
     </div>
  </body>
</html>
"""

        self.set_header("Content-Type", 'text/html')
        self.write(page)

    def post(self, *args, **kwargs):
        page = """
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Project setup</title>
  </head>
  <body>
     <div>
        Done! Close this window now if you like.
     </div>
  </body>
</html>
"""

        self.set_header("Content-Type", 'text/html')
        self.write(page)

        self.application.emit_event(UIServerDoneEvent(should_we_prepare=True))


class UIApplication(Application):
    def __init__(self, event_handler, io_loop, **kwargs):
        self._event_handler = event_handler
        self.io_loop = io_loop
        patterns = [(r'/?', PrepareViewHandler)]
        super(UIApplication, self).__init__(patterns, **kwargs)

    def emit_event(self, event):
        self.io_loop.add_callback(lambda: self._event_handler(event))


class UIServer(object):
    def __init__(self, event_handler, io_loop):
        assert event_handler is not None
        assert io_loop is not None

        self._application = UIApplication(event_handler, io_loop)
        self._http = HTTPServer(self._application, io_loop=io_loop)

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

    def unlisten(self):
        """Permanently close down the HTTP server, no longer listen on any sockets."""
        self._http.close_all_connections()
        self._http.stop()
