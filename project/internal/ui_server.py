from __future__ import absolute_import, print_function

import collections
import socket
import sys
import uuid

from tornado.httpserver import HTTPServer
from tornado.netutil import bind_sockets
from tornado.web import Application, RequestHandler

from project.plugins.provider import ProviderConfigContext

from project.internal.plugin_html import cleanup_and_scope_form, html_tag


class UIServerEvent(object):
    pass


class UIServerDoneEvent(UIServerEvent):
    def __init__(self, result):
        super(UIServerDoneEvent, self).__init__()
        self.result = result

# future: use actual template system
_entity_table = {"&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"}


def _html_escape(text):
    for key, value in _entity_table.items():
        text = text.replace(key, value)
    return text


class PrepareViewHandler(RequestHandler):
    def __init__(self, application, *args, **kwargs):
        # Note: application is stored as self.application
        super(PrepareViewHandler, self).__init__(application, *args, **kwargs)

    def _outer_page(self, content):
        return """
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Project setup</title>
  </head>
  <body>
    %s
  </body>
</html>
""" % (content)

    def _result_page(self, result):
        if result.failed:
            error_html = """
<p>Something didn't work...</p>
<ul>
"""

            for error in result.errors:
                error_html = error_html + ("<li>%s</li>\n" % _html_escape(error))
            error_html = error_html + "</ul>\n"

            return self._outer_page(error_html)
        else:
            return self._outer_page("""
<div>Done! Close this window now if you like.</div>
""")

    def get(self, *args, **kwargs):
        if self.application.prepare_stage is None:
            self.application.emit_event(UIServerDoneEvent(result=self.application.last_stage_result))
            page = self._result_page(self.application.last_stage_result)
        else:
            prepare_context = self.application.prepare_stage.configure()

            config_html = ""

            if prepare_context is not None:

                self.application.refresh_form_ids(prepare_context)

                config_html = config_html + "<ul>"
                for (requirement, providers) in prepare_context.requirements_and_providers:
                    config_html = config_html + "<li>"
                    config_html = config_html + html_tag("h3", requirement.title)
                    for provider in providers:
                        config_context = ProviderConfigContext(prepare_context.environ,
                                                               prepare_context.local_state_file, requirement)
                        config = provider.read_config(config_context)
                        raw_html = provider.config_html(requirement)
                        if raw_html is not None:
                            prefix = self.application.form_prefix(requirement, provider)
                            cleaned_html = cleanup_and_scope_form(raw_html, prefix, config)
                            config_html = config_html + "\n" + cleaned_html

                    config_html = config_html + "</li>"
                config_html = config_html + "</ul>"

            page = self._outer_page("""
<div>
  <form action="/" method="post" enctype="multipart/form-data">
    <input type="submit" value="%s"></input>
    %s
  </form>
</div>
""" % (self.application.prepare_stage.description_of_action, config_html))

        self.set_header("Content-Type", 'text/html')
        self.write(page)

    def post(self, *args, **kwargs):
        prepare_context = self.application.prepare_stage.configure()

        if prepare_context is not None:
            configs = collections.defaultdict(lambda: dict())
            for name in self.request.body_arguments:
                parsed = self.application.parse_form_name(prepare_context, name)
                if parsed is not None:
                    (requirement, provider, unscoped_name) = parsed
                    value_string = self.get_body_argument(name)
                    values = configs[(requirement, provider)]
                    values[unscoped_name] = value_string
            for ((requirement, provider), values) in configs.items():
                config_context = ProviderConfigContext(prepare_context.environ, prepare_context.local_state_file,
                                                       requirement)
                provider.set_config_values_as_strings(config_context, values)

            prepare_context.local_state_file.save()

        next_stage = self.application.prepare_stage.execute()
        if next_stage is None:
            self.application.last_stage_result = self.application.prepare_stage.result
        self.application.prepare_stage = next_stage

        return self.get(*args, **kwargs)


class UIApplication(Application):
    def __init__(self, prepare_stage, event_handler, io_loop, **kwargs):
        self._event_handler = event_handler
        self.io_loop = io_loop
        self.prepare_stage = prepare_stage
        self.last_stage_result = None

        self._requirements_by_id = {}
        self._ids_by_requirement = {}

        patterns = [(r'/?', PrepareViewHandler)]
        super(UIApplication, self).__init__(patterns, **kwargs)

    def emit_event(self, event):
        self.io_loop.add_callback(lambda: self._event_handler(event))

    def refresh_form_ids(self, prepare_context):
        old_ids_by_requirement = self._ids_by_requirement
        self._requirements_by_id = {}
        self._ids_by_requirement = {}
        for (requirement, providers) in prepare_context.requirements_and_providers:
            req_id = old_ids_by_requirement.get(requirement, str(uuid.uuid4()))
            self._requirements_by_id[req_id] = requirement
            self._ids_by_requirement[requirement] = req_id

    def form_prefix(self, requirement, provider):
        return "%s.%s." % (self._ids_by_requirement[requirement], provider.config_key)

    def parse_form_name(self, prepare_context, name):
        pieces = name.split(".")
        if len(pieces) < 3:
            # this map on "pieces" is so py2 and py3 render it the same way,
            # so the unit tests can be the same on both
            print("not enough pieces in " + repr(list(map(lambda s: str(s), pieces))), file=sys.stderr)
            return None
        req_id = pieces[0]
        provider_key = pieces[1]
        unscoped_name = ".".join(pieces[2:])
        if req_id not in self._requirements_by_id:
            print(req_id + " not a known requirement id", file=sys.stderr)
            return None
        requirement = self._requirements_by_id[req_id]
        for (req, providers) in prepare_context.requirements_and_providers:
            if req is requirement:
                for provider in providers:
                    if provider_key == provider.config_key:
                        return (requirement, provider, unscoped_name)
        print("did not find provider " + provider_key, file=sys.stderr)
        return None


class UIServer(object):
    def __init__(self, prepare_stage, event_handler, io_loop):
        assert event_handler is not None
        assert io_loop is not None

        self._application = UIApplication(prepare_stage, event_handler, io_loop)
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
