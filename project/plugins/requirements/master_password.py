"""Requirement for a master password used to store encrypted credentials."""

from project.plugins.requirement import EnvVarRequirement


class MasterPasswordRequirement(EnvVarRequirement):
    """A requirement for ANACONDA_MASTER_PASSWORD."""

    def __init__(self, options=None):
        """Extend superclass to always use ANACONDA_MASTER_PASSWORD."""
        super(MasterPasswordRequirement, self).__init__(env_var='ANACONDA_MASTER_PASSWORD', options=options)

    @property
    def title(self):
        """Override superclass title."""
        return "Anaconda master password"

    @property
    def encrypted(self):
        """Override superclass to never encrypt ANACONDA_MASTER_PASSWORD which would be circular."""
        return False

    def find_providers(self, registry):
        """Override superclass to list master password providers."""
        return [registry.find_by_class_name('MasterPasswordProvider')]
