from __future__ import absolute_import, print_function

from abc import ABCMeta, abstractmethod

from project.internal.metaclass import with_metaclass


class ConfigurePrepareContext(object):
    def __init__(self, environ, local_state_file, requirements_and_providers):
        self.environ = environ
        self.local_state_file = local_state_file
        self.requirements_and_providers = requirements_and_providers


class PrepareUI(with_metaclass(ABCMeta)):
    @abstractmethod
    def configure(self, context):
        pass  # pragma: no cover


class NotInteractivePrepareUI(PrepareUI):
    def configure(self, context):
        return True


class BrowserPrepareUI(PrepareUI):
    def __init__(self, io_loop, show_url):
        assert show_url is not None
        assert io_loop is not None
        self._server = None
        self._io_loop = io_loop
        self._show_url = show_url

    def configure(self, context):
        from project.internal.ui_server import UIServer, UIServerDoneEvent

        assert self._server is None

        def event_handler(event):
            if isinstance(event, UIServerDoneEvent):
                assert event.should_we_prepare
                self._io_loop.stop()

        self._server = UIServer(context, event_handler=event_handler, io_loop=self._io_loop)
        try:
            print("# Click the button at {url} to continue...".format(url=self._server.url))
            self._show_url(self._server.url)

            self._io_loop.start()
        finally:
            self._server.unlisten()
            self._server = None

        return True
