# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Project "local state" file loading and manipulation."""
from __future__ import absolute_import

import os

from anaconda_project.yaml_file import YamlFile

# these are in the order we'll use them if multiple are present
possible_local_state_file_names = ("anaconda-project-local.yml", "anaconda-project-local.yaml")

DEFAULT_LOCAL_STATE_FILENAME = possible_local_state_file_names[0]

SERVICE_RUN_STATES_SECTION = "service_run_states"


class LocalStateFile(YamlFile):
    """Represents the locally-configured/user-specific state of the project directory.

    Project config that you might want in source control should be
    in ``ProjectFile`` instead.

    Be careful with creating your own instance of this class,
    because you have to think about when other code might load or
    save in a way that conflicts with your loads and saves.
    """

    @classmethod
    def load_for_directory(cls, directory):
        """Load the project local state file from the given directory, even if it doesn't exist.

        If the directory has no project file, the loaded
        ``LocalStateFile`` will be empty. It won't actually be
        created on disk unless you call ``save()``.

        If the local state file has syntax problems, the
        ``corrupted`` and ``corrupted_error_message`` properties
        will be set and attempts to modify or save the file will
        raise an exception.

        Args:
            directory (str): path to the project directory

        Returns:
            a new ``LocalStateFile``

        """
        for name in possible_local_state_file_names:
            path = os.path.join(directory, name)
            if os.path.isfile(path):
                return LocalStateFile(path)
        return LocalStateFile(os.path.join(directory, DEFAULT_LOCAL_STATE_FILENAME))

    def _default_comment(self):
        return "Anaconda local project state (specific to this user/machine)"

    def set_service_run_state(self, service_name, state):
        """Set a dict value in the ``service_run_states`` section.

        This is used to save the state of a running service, such as
        its port or process ID.

        Conventionally the state can also include a
        ``shutdown_commands`` property with a list of list of
        strings value. The lists of strings are args to pass to
        exec. In order to shut down a service, we run all
        ``shutdown_commands`` and then delete the entire service
        run state dict.

        This method does not save the file, call ``save()`` to do that.

        Args:
            service_name (str): environment variable identifying the service
            state (dict): state for the running service process
        """
        if not isinstance(state, dict):
            raise ValueError("service state should be a dict")
        self.set_value([SERVICE_RUN_STATES_SECTION, service_name], state)

    def get_service_run_state(self, service_name):
        """Get the running instance state for a service.

        Args:
            service_name (str): environment variable identifying the service

        Returns:
            The state dict (empty dict if no state was saved)
        """
        return self.get_value([SERVICE_RUN_STATES_SECTION, service_name], default=dict())

    def get_all_service_run_states(self):
        """Get all saved service run states.

        Returns the entire ``service_run_states`` section.

        Returns:
            a dict from service name to service state dict
        """
        return self.get_value(SERVICE_RUN_STATES_SECTION, default=dict())
