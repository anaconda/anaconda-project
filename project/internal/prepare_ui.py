from __future__ import absolute_import, print_function

from abc import ABCMeta, abstractmethod

from project.internal.metaclass import with_metaclass


class PrepareUI(with_metaclass(ABCMeta)):
    @abstractmethod
    def should_we_prepare(self, io_loop):
        pass  # pragma: no cover


class NotInteractivePrepareUI(PrepareUI):
    def should_we_prepare(self, io_loop):
        return True


class BrowserPrepareUI(PrepareUI):
    def __init__(self):
        self._server = None

    def should_we_prepare(self, io_loop):
        from project.internal.ui_server import UIServer, UIServerDoneEvent
        import webbrowser

        assert self._server is None

        def event_handler(event):
            if isinstance(event, UIServerDoneEvent):
                assert event.should_we_prepare
                io_loop.stop()

        self._server = UIServer(event_handler=event_handler, io_loop=io_loop)
        try:
            print("# Click the button at {url} to continue...".format(url=self._server.url))
            webbrowser.open_new_tab(self._server.url)

            io_loop.start()

            print("# ...continuing to prepare the project")
        finally:
            self._server.unlisten()
            self._server = None

        return True
