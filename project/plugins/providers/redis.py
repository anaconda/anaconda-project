"""Redis-related providers."""
from project.plugins.provider import Provider


class DefaultRedisProvider(Provider):
    """Provides the default Redis service on localhost port 6379."""

    @property
    def title(self):
        """Override superclass to provide our title."""
        return "Default Redis port on localhost"

    def provide(self, requirement, environ):
        """Override superclass to set the requirement's env var to the default Redis localhost URL."""
        environ[requirement.env_var] = "redis://localhost:6379"
