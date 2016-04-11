# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Requirement for a master password used to store encrypted credentials."""

from anaconda_project.plugins.requirement import EnvVarRequirement


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

    def check_status(self, environ, local_state_file):
        """Override superclass to get our status."""
        value = self._get_value_of_env_var(environ)
        has_been_provided = value is not None
        if has_been_provided:
            status_description = "Using Anaconda master password from the environment variable."
        else:
            status_description = (
                "Anaconda master password isn't set as the ANACONDA_MASTER_PASSWORD " + "environment variable.")

        return self._create_status(environ,
                                   local_state_file,
                                   has_been_provided=has_been_provided,
                                   status_description=status_description,
                                   provider_class_name='MasterPasswordProvider')
