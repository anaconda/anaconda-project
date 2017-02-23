# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import collections
import socket
import sys
import uuid

from tornado.httpserver import HTTPServer
from tornado.netutil import bind_sockets
from tornado.web import Application, RequestHandler

from anaconda_project.internal.plugin_html import cleanup_and_scope_form, html_tag


class UIServerEvent(object):
    pass


class UIServerDoneEvent(UIServerEvent):
    def __init__(self, result):
        super(UIServerDoneEvent, self).__init__()
        self.result = result

# future: use actual template system
# it's important to replace & before the later ones
_entity_table = [("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ("'", "&#39;"), ('"', "&quot;")]


def _html_escape(text):
    for (key, value) in _entity_table:
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
    <title>Project setup for %s</title>
  </head>
  <body>
    %s
  </body>
</html>
""" % (self.application.project.name, content)

    def _html_for_status_list(self, statuses, with_config, prepare_context=None):
        html = "<ul>"
        for status in sorted(statuses, key=lambda status: status.requirement.title):
            html = html + "<li>"
            if status.has_been_provided:
                check = '<span style="color: green;">✓</span> '
            else:
                check = '<span style="color: red;">✗</span> '
            html = html + html_tag("h4", status.requirement.title)
            html = html + html_tag("p", "Status: " + status.status_description).replace("<p>Status: ", "<p>Status: " +
                                                                                        check + " ")
            if with_config:
                raw_html = status.provider.config_html(status.requirement, prepare_context.environ,
                                                       prepare_context.local_state_file, prepare_context.overrides,
                                                       status)
                if raw_html is not None:
                    prefix = self.application.form_prefix(status.requirement, status.provider)
                    cleaned_html = cleanup_and_scope_form(raw_html, prefix, status.analysis.config)
                    html = html + "\n" + cleaned_html

            html = html + "</li>"
        html = html + "</ul>"

        return html

    def _result_page(self, result, latest_statuses):
        # TODO: clean this up, we should show the usual status
        # list with errors embedded and possibly config html to
        # fix them, rather than showing just textual errors free
        # of context.
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
            status_list_html = self._html_for_status_list(latest_statuses, with_config=False)
            return self._outer_page("""
<div>Done! Close this window now if you like.</div>
""" + status_list_html)

    def get(self, *args, **kwargs):
        if self.application.prepare_stage is None:
            self.application.emit_event(UIServerDoneEvent(result=self.application.last_stage_result))
            page = self._result_page(self.application.last_stage_result, self.application.latest_statuses)
        else:
            prepare_context = self.application.prepare_stage.configure()

            config_html = ""

            if prepare_context is not None:

                self.application.refresh_form_ids(prepare_context)

                status_list_html = self._html_for_status_list(prepare_context.statuses,
                                                              with_config=True,
                                                              prepare_context=prepare_context)

                config_html = config_html + status_list_html

            page = self._outer_page("""
<div>
  <form action="/" method="post" enctype="multipart/form-data">
    <h2>Project "%s" has these requirements that may need setup:</h2>
    %s
    <input type="submit" value="%s"></input>
  </form>
</div>
""" % (self.application.project.name, config_html, self.application.prepare_stage.description_of_action))

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
                    value_strings = self.get_body_arguments(name)
                    value_string = value_strings[0]
                    values = configs[(requirement, provider)]
                    values[unscoped_name] = value_string
            for ((requirement, provider), values) in configs.items():
                provider.set_config_values_as_strings(
                    requirement, prepare_context.environ, prepare_context.local_state_file,
                    prepare_context.default_env_spec_name, prepare_context.overrides, values)

            prepare_context.local_state_file.save()

        next_stage = self.application.prepare_stage.execute()
        self.application.latest_statuses = self.application.prepare_stage.statuses_after_execute
        if next_stage is None:
            self.application.last_stage_result = self.application.prepare_stage.result
        else:
            self.application.latest_statuses = next_stage.statuses_before_execute
        self.application.prepare_stage = next_stage

        return self.get(*args, **kwargs)


class UIApplication(Application):
    def __init__(self, project, prepare_stage, event_handler, io_loop, **kwargs):
        self._event_handler = event_handler
        self.project = project
        self.io_loop = io_loop
        self.prepare_stage = prepare_stage
        self.last_stage_result = None
        self.latest_statuses = prepare_stage.statuses_before_execute

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
        for status in prepare_context.statuses:
            req_id = old_ids_by_requirement.get(status.requirement, str(uuid.uuid4()))
            self._requirements_by_id[req_id] = status.requirement
            self._ids_by_requirement[status.requirement] = req_id

    def form_prefix(self, requirement, provider):
        return "%s.%s." % (self._ids_by_requirement[requirement], provider.__class__.__name__)

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
        for status in prepare_context.statuses:
            if status.requirement is requirement:
                if provider_key == status.provider.__class__.__name__:
                    return (requirement, status.provider, unscoped_name)
        print("did not find provider " + provider_key, file=sys.stderr)
        return None


class UIServer(object):
    def __init__(self, project, prepare_stage, event_handler, io_loop):
        assert event_handler is not None
        assert io_loop is not None

        self._application = UIApplication(project, prepare_stage, event_handler, io_loop)
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
