"""Requirement for a master password used to store encrypted credentials."""

from project.plugins.requirement import EnvVarRequirement


class MasterPasswordRequirement(EnvVarRequirement):
    """A requirement for ANACONDA_MASTER_PASSWORD."""

    def __init__(self, options=None):
        """Extend superclass to always use ANACONDA_MASTER_PASSWORD."""
        super(MasterPasswordRequirement, self).__init__(env_var='ANACONDA_MASTER_PASSWORD', options=options)

    def find_providers(self, registry):
        """Override superclass to list no providers."""
        # EnvVarProvider will let you put the master password in
        # the config file, which we want to disallow. By having no
        # providers, it has to be set in the environment up front.
        # future: add a provider that uses the keyring library
        return []
