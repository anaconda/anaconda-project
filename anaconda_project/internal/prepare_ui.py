# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function


def _default_show_url(url):
    import webbrowser
    webbrowser.open_new_tab(url)


def prepare_browser(project, stage, io_loop, show_url):
    from tornado.ioloop import IOLoop
    from anaconda_project.internal.ui_server import UIServer, UIServerDoneEvent

    result_holder = {}
    old_current_loop = None
    try:
        old_current_loop = IOLoop.current()
        if io_loop is None:
            io_loop = IOLoop()
        io_loop.make_current()

        if show_url is None:
            show_url = _default_show_url

        def event_handler(event):
            if isinstance(event, UIServerDoneEvent):
                result_holder['result'] = event.result
                io_loop.stop()

        server = UIServer(project, stage, event_handler=event_handler, io_loop=io_loop)
        try:
            print("# Configure the project at {url} to continue...".format(url=server.url))
            show_url(server.url)

            io_loop.start()
        finally:
            server.unlisten()
    finally:
        if old_current_loop is not None:
            old_current_loop.make_current()

    if 'result' in result_holder:
        return result_holder['result']
    else:
        from anaconda_project.prepare import PrepareFailure
        # this pretty much only happens in unit tests.
        return PrepareFailure(logs=[],
                              statuses=(),
                              errors=["Browser UI main loop was stopped."],
                              environ=stage.environ,
                              overrides=stage.overrides)
