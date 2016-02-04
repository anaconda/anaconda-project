from __future__ import absolute_import, print_function

from abc import ABCMeta, abstractmethod

from project.internal.metaclass import with_metaclass


class ConfigurePrepareContext(object):
    def __init__(self, io_loop, environ, local_state_file, requirements_and_providers):
        self.io_loop = io_loop
        self.environ = environ
        self.local_state_file = local_state_file
        self.requirements_and_providers = requirements_and_providers


class PrepareUI(with_metaclass(ABCMeta)):
    @abstractmethod
    def configure_prepare(self, context):
        pass  # pragma: no cover


class NotInteractivePrepareUI(PrepareUI):
    def configure_prepare(self, context):
        return True


class BrowserPrepareUI(PrepareUI):
    def __init__(self):
        self._server = None

    def configure_prepare(self, context):
        from project.internal.ui_server import UIServer, UIServerDoneEvent
        import webbrowser

        assert self._server is None

        def event_handler(event):
            if isinstance(event, UIServerDoneEvent):
                assert event.should_we_prepare
                context.io_loop.stop()

        self._server = UIServer(context, event_handler=event_handler)
        try:
            print("# Click the button at {url} to continue...".format(url=self._server.url))
            webbrowser.open_new_tab(self._server.url)

            context.io_loop.start()
        finally:
            self._server.unlisten()
            self._server = None

        return True
