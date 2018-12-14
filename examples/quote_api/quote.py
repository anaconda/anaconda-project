from __future__ import absolute_import, print_function

from argparse import ArgumentParser
import falcon
import gunicorn.app.base
import json
import multiprocessing
import sys


# A Falcon resource that returns the same quote every time
class QuoteResource(object):
    def on_get(self, req, resp):
        """Handles GET requests"""
        quote = {'quote': 'I\'ve always been more interested in the future than in the past.', 'author': 'Grace Hopper'}

        resp.body = json.dumps(quote)


# A Falcon resource that explains what this server is
class IndexResource(object):
    def __init__(self, prefix):
        self.prefix = prefix

    def on_get(self, req, resp):
        """Handles GET requests"""
        resp.body = """
<html>
  <head>
    <title>Quote API Server</title>
  </head>
  <body>
    <p>This is a toy JSON API server example.</p>
    <p>Make a GET request to <a href="%s/quote">%s/quote</a></p>
  </body>
</html>
""" % (self.prefix, self.prefix)
        resp.content_type = "text/html"
        resp.status = falcon.HTTP_200


# A Falcon middleware to implement validation of the Host header in requests
class HostFilter(object):
    def __init__(self, hosts):
        # falcon strips the port out of req.host, even if it isn't 80.
        # This is probably a bug in Falcon, so we work around it here.
        self.hosts = [falcon.util.uri.parse_host(host)[0] for host in hosts]

    def process_request(self, req, resp):
        # req.host has the port stripped from what the browser
        # sent us, even when it isn't 80, which is probably a bug
        # in Falcon. We deal with that in __init__ by removing
        # ports from self.hosts.
        if req.host not in self.hosts:
            print("Attempted request with Host header '%s' denied" % req.host)
            raise falcon.HTTPForbidden("Bad Host header", "Cannot connect via the provided hostname")


# the gunicorn application
class QuoteApplication(gunicorn.app.base.BaseApplication):
    def __init__(self, port, address, prefix, hosts):
        assert prefix is not None
        assert port is not None
        assert address is not None
        self.application = falcon.API(middleware=HostFilter(hosts))
        # add_route is pedantic about this
        if prefix != '' and not prefix.startswith("/"):
            prefix = "/" + prefix
        self.application.add_route(prefix + '/quote', QuoteResource())
        self.application.add_route(prefix + "/", IndexResource(prefix))
        self.port = port
        self.address = address
        self.prefix = prefix
        super(QuoteApplication, self).__init__()

        print("Only connections via these hosts are allowed: " + repr(hosts))

    def load_config(self):
        # Note: the bind address here is --anaconda-project-address
        # plus --anaconda-project-port, NOT --anaconda-project-host.
        self.cfg.set('bind', '%s:%s' % (self.address, self.port))
        self.cfg.set('workers', (multiprocessing.cpu_count() * 2) + 1)

    def load(self):
        return self.application


# arg parser for the standard project options
parser = ArgumentParser(prog="quote-api", description="API server that returns a quote.")
parser.add_argument('--anaconda-project-host', action='append', help='Hostname to allow in requests')
parser.add_argument(
    '--anaconda-project-no-browser', action='store_true', default=False, help='Disable opening in a browser')
parser.add_argument(
    '--anaconda-project-use-xheaders', action='store_true', default=False, help='Trust X-headers from reverse proxy')
parser.add_argument('--anaconda-project-url-prefix', action='store', default='', help='Prefix in front of urls')
parser.add_argument('--anaconda-project-port', action='store', default='8080', help='Port to listen on')
parser.add_argument('--anaconda-project-address', action='store', default='0.0.0.0', help='IP to listen on')
parser.add_argument(
    '--anaconda-project-iframe-hosts',
    action='append',
    help='Space-separated hosts which can embed us in an iframe per our Content-Security-Policy')

if __name__ == '__main__':
    # This app accepts but ignores --anaconda-project-no-browser because we never bother to open a browser,
    # and accepts but ignores --anaconda-project-iframe-hosts since iframing an API makes no sense.
    args = parser.parse_args(sys.argv[1:])
    if not args.anaconda_project_host:
        args.anaconda_project_host = ['localhost:' + args.anaconda_project_port]
    app = QuoteApplication(
        port=args.anaconda_project_port,
        address=args.anaconda_project_address,
        prefix=args.anaconda_project_url_prefix,
        hosts=args.anaconda_project_host)
    print("Starting API server. Try http://localhost:%s%s" % (app.port, app.prefix + '/quote'))
    try:
        app.run()
    finally:
        print("Exiting.")
