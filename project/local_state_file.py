"""Project "local state" file loading and manipulation."""
from __future__ import absolute_import

import os

from project.yaml_file import YamlFile

LOCAL_STATE_DIRECTORY = ".anaconda"
LOCAL_STATE_FILENAME = "project-local.yml"

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

        If the local state file has syntax problems, this raises
        an exception from the YAML parser.

        Args:
            directory (str): path to the project directory

        Returns:
            a new ``LocalStateFile``

        """
        path = os.path.join(directory, LOCAL_STATE_DIRECTORY, LOCAL_STATE_FILENAME)
        return LocalStateFile(path)

    def _default_comment(self):
        return "Anaconda local project state"

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

        Args:
            service_name (str): some sort of unique name for the service
            state (dict): state for the running service process
        """
        if not isinstance(state, dict):
            raise ValueError("service state should be a dict")
        self.set_value(SERVICE_RUN_STATES_SECTION, service_name, state)

    def get_service_run_state(self, service_name):
        """Get the running instance state for a service.

        Args:
            service_name (str): some sort of unique name for the service

        Returns:
            The state dict (empty dict if no state was saved)
        """
        return self.get_value(SERVICE_RUN_STATES_SECTION, service_name, default=dict())

    def get_all_service_run_states(self):
        """Get all saved service run states.

        Returns the entire ``service_run_states`` section.

        Returns:
            a dict from service name to service state dict
        """
        return self.get_value(SERVICE_RUN_STATES_SECTION, default=dict())
