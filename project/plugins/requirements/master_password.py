"""Requirement for a master password used to store encrypted credentials."""

from project.plugins.requirement import EnvVarRequirement, RequirementStatus


class MasterPasswordRequirement(EnvVarRequirement):
    """A requirement for ANACONDA_MASTER_PASSWORD."""

    def __init__(self, registry, options=None):
        """Extend superclass to always use ANACONDA_MASTER_PASSWORD."""
        super(MasterPasswordRequirement, self).__init__(registry=registry,
                                                        env_var='ANACONDA_MASTER_PASSWORD',
                                                        options=options)

    @property
    def title(self):
        """Override superclass title."""
        return "Anaconda master password (used to encrypt other passwords and credentials)"

    @property
    def encrypted(self):
        """Override superclass to never encrypt ANACONDA_MASTER_PASSWORD which would be circular."""
        return False

    def _find_providers(self):
        """Override superclass to list master password providers."""
        return [self.registry.find_provider_by_class_name('MasterPasswordProvider')]

    def check_status(self, environ):
        """Override superclass to get our status."""
        value = self._get_value_of_env_var(environ)
        providers = self._find_providers()
        unset_message = "Anaconda master password isn't set as the ANACONDA_MASTER_PASSWORD environment variable."
        set_message = "Using Anaconda master password from the environment variable."
        if value is None:
            return RequirementStatus(self,
                                     has_been_provided=False,
                                     status_description=unset_message,
                                     possible_providers=providers)
        else:
            return RequirementStatus(self,
                                     has_been_provided=True,
                                     status_description=set_message,
                                     possible_providers=providers)
