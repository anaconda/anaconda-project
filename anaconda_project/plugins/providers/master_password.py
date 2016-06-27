# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Master password provider."""
from __future__ import absolute_import, print_function

from anaconda_project.plugins.provider import Provider, ProvideResult
from anaconda_project.internal import keyring
from anaconda_project.internal.py2_compat import is_string
from anaconda_project.internal.simple_status import SimpleStatus


class MasterPasswordProvider(Provider):
    """Provides a master password, stored in the OS keyring if possible."""

    def read_config(self, requirement, environ, local_state_file, default_env_spec_name, overrides):
        """Override superclass to read from keyring."""
        config = dict()
        value = keyring.get(requirement.env_var)
        if value is not None:
            config['value'] = value
        return config

    def set_config_values_as_strings(self, requirement, environ, local_state_file, default_env_spec_name, overrides,
                                     values):
        """Override superclass to set in keyring."""
        if 'value' in values:
            value_string = values['value']
            keyring.set(requirement.env_var, value_string)

    def config_html(self, requirement, environ, local_state_file, overrides, status):
        """Override superclass to provide our config html."""
        return """
<form>
  <label>Value: <input type="password" name="value"/></label>
</form>
"""

    def provide(self, requirement, context):
        """Override superclass to use password from the keyring or the environment."""
        # We prefer the values in this order:
        #  - the value stored in the keyring (like project-local in a regular EnvVarProvider)
        #  - anything already set in the environment
        #  - default from project.yml
        value = keyring.get(requirement.env_var)

        if value is not None:
            context.environ[requirement.env_var] = value
        elif requirement.env_var in context.environ:
            # nothing to do here
            pass
        elif 'default' in requirement.options:
            # Note: not a good idea to put your master password
            # in project.yml, but...
            #
            # variables:
            #   ANACONDA_MASTER_PASSWORD:
            #     default: "foobar"
            value = requirement.options['default']
            assert is_string(value)  # should have been checked on project load
            context.environ[requirement.env_var] = value
        else:
            pass

        return ProvideResult.empty()

    def unprovide(self, requirement, environ, local_state_file, overrides, requirement_status=None):
        """Override superclass to return success always."""
        return SimpleStatus(success=True, description=("Nothing to clean up for master password."))
