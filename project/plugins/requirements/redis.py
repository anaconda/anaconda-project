"""Redis-related requirements."""

from project.plugins.requirement import EnvVarRequirement, RequirementStatus
# don't "import from" network_util or we can't monkeypatch it in tests
import project.plugins.network_util as network_util


class RedisRequirement(EnvVarRequirement):
    """A requirement for REDIS_URL (or another specified env var) to point to a running Redis."""

    def __init__(self, env_var="REDIS_URL", options=None):
        """Extend superclass to default to REDIS_URL."""
        super(RedisRequirement, self).__init__(env_var=env_var, options=options)

    def _find_providers(self, registry):
        return registry.find_by_service(self, 'redis')

    def _why_not_provided(self, environ):
        url = self._get_value_of_env_var(environ)
        if url is None:
            return self._unset_message()
        split = network_util.urlparse.urlsplit(url)
        if split.scheme != 'redis':
            return "{env_var} value '{url}' does not have 'redis:' scheme.".format(env_var=self.env_var, url=url)
        port = 6379
        if split.port is not None:
            port = split.port
        if network_util.can_connect_to_socket(split.hostname, port):
            return None
        else:
            return "Cannot connect to {url} (from {env_var} environment variable).".format(url=url,
                                                                                           env_var=self.env_var)

    def check_status(self, environ, registry):
        """Override superclass to get our status."""
        why_not_provided = self._why_not_provided(environ)
        providers = self._find_providers(registry)
        if why_not_provided is None:
            return RequirementStatus(
                self,
                registry,
                has_been_provided=True,
                status_description=("Using Redis server at %s" % self._get_value_of_env_var(environ)),
                possible_providers=providers)
        else:
            return RequirementStatus(self,
                                     registry,
                                     has_been_provided=False,
                                     status_description=why_not_provided,
                                     possible_providers=providers)
