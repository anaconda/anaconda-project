from __future__ import absolute_import

import os

from .yaml_file import YamlFile

LOCAL_STATE_DIRECTORY = ".anaconda"
LOCAL_STATE_FILENAME = "project-local.yml"

SERVICE_RUN_STATES_SECTION = "service_run_states"
PROVIDER_CONFIGS_SECTION = "providers"


class LocalStateFile(YamlFile):
    """Represents the locally-configured/user-specific state of the project directory.

    Project config that you might want in source control should be
    in ``ProjectFile`` instead.

    This class is internal because everyone needs to use a singleton instance,
    if code loads the file itself it doesn't know when to reload because
    some other code made changes.
    """

    @classmethod
    def load_for_directory(cls, directory):
        path = os.path.join(directory, LOCAL_STATE_DIRECTORY, LOCAL_STATE_FILENAME)
        return LocalStateFile(path)

    def __init__(self, filename):
        super(LocalStateFile, self).__init__(filename)

    def _default_comment(self):
        return "Anaconda local project state"

    def set_service_run_state(self, service_name, state):
        if not isinstance(state, dict):
            raise ValueError("service state should be a dict")
        self.set_value(SERVICE_RUN_STATES_SECTION, service_name, state)

    def get_service_run_state(self, service_name):
        return self.get_value(SERVICE_RUN_STATES_SECTION, service_name, default=dict())

    def get_all_service_run_states(self):
        return self.get_value(SERVICE_RUN_STATES_SECTION, default=dict())

    @classmethod
    def _provider_config_section(cls, requirement_key):
        return PROVIDER_CONFIGS_SECTION + "." + requirement_key

    def set_provider_config(self, requirement_key, provider_key, config):
        if not isinstance(config, dict):
            raise ValueError("provider config should be a dict")
        self.set_value(self._provider_config_section(requirement_key), provider_key, config)

    def get_provider_config(self, requirement_key, provider_key):
        return self.get_value(self._provider_config_section(requirement_key), provider_key, default=dict())
