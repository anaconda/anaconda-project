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
    def __init__(self, port, prefix, hosts):
        assert prefix is not None
        assert port is not None
        self.application = falcon.API(middleware=HostFilter(hosts))
        # add_route is pedantic about this
        if prefix != '' and not prefix.startswith("/"):
            prefix = "/" + prefix
        self.application.add_route(prefix + '/quote', QuoteResource())
        self.application.add_route(prefix + "/", IndexResource(prefix))
        self.port = port
        super(QuoteApplication, self).__init__()

        print("Only connections via these hosts are allowed: " + repr(hosts))
        print("Starting API server. Try http://localhost:%s%s" % (self.port, prefix + '/quote'))

    def load_config(self):
        # Note that --kapsel-host is NOT this address; it is NOT
        # the address to listen on. --kapsel-host specifies the
        # allowed values of the Host header in an http request,
        # which is totally different. Another way to put it is
        # that --kapsel-host is the public hostname:port browsers will
        # be connecting to.
        self.cfg.set('bind', '%s:%s' % ('0.0.0.0', self.port))
        self.cfg.set('workers', (multiprocessing.cpu_count() * 2) + 1)

    def load(self):
        return self.application

# arg parser for the standard kapsel options
parser = ArgumentParser(prog="quote-api", description="API server that returns a quote.")
parser.add_argument('--kapsel-host', action='append', help='Hostname to allow in requests')
parser.add_argument('--kapsel-no-browser', action='store_true', default=False, help='Disable opening in a browser')
parser.add_argument('--kapsel-url-prefix', action='store', default='', help='Prefix in front of urls')
parser.add_argument('--kapsel-port', action='store', default='8080', help='Port to listen on')
parser.add_argument('--kapsel-iframe-hosts',
                    action='append',
                    help='Space-separated hosts which can embed us in an iframe per our Content-Security-Policy')

if __name__ == '__main__':
    # This app accepts but ignores --kapsel-no-browser because we never bother to open a browser,
    # and accepts but ignores --kapsel-iframe-hosts since iframing an API makes no sense.
    args = parser.parse_args(sys.argv[1:])
    if not args.kapsel_host:
        args.kapsel_host = ['localhost:' + args.kapsel_port]
    QuoteApplication(port=args.kapsel_port, prefix=args.kapsel_url_prefix, hosts=args.kapsel_host).run()
