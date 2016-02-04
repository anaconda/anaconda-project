"""Redis-related requirements."""

from project.plugins.requirement import EnvVarRequirement
# don't "import from" network_util or we can't monkeypatch it in tests
import project.plugins.network_util as network_util


class RedisRequirement(EnvVarRequirement):
    """A requirement for REDIS_URL (or another specified env var) to point to a running Redis."""

    def __init__(self, env_var="REDIS_URL", options=None):
        """Extend superclass to default to REDIS_URL."""
        super(RedisRequirement, self).__init__(env_var=env_var, options=options)

    def find_providers(self, registry):
        """Override superclass to find by service name 'redis'."""
        return registry.find_by_service(self, 'redis')

    def why_not_provided(self, environ):
        """Extend superclass to check the URL syntax and that we can connect to it."""
        why_not = super(RedisRequirement, self).why_not_provided(environ)
        if why_not is not None:
            return why_not
        url = environ[self.env_var]
        split = network_util.urlparse.urlsplit(url)
        if split.scheme != 'redis':
            return "{env_var} value '{url}' does not have 'redis:' scheme".format(env_var=self.env_var, url=url)
        port = 6379
        if split.port is not None:
            port = split.port
        if network_util.can_connect_to_socket(split.hostname, port):
            return None
        else:
            return "Cannot connect to {url} (from {env_var})".format(url=url, env_var=self.env_var)
