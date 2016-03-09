"""Environment class representing a conda environment."""
from __future__ import absolute_import

import os


class CondaEnvironment(object):
    """Represents an environment specification which we could potentially create."""

    def __init__(self, name, dependencies, channels):
        """Construct an Enviroment with the given name and dependencies.

        Args:
            name (str): name of the environment
            dependencies (list): list of package specs to pass to conda install
            channels (list): list of channel names
        """
        self._name = name
        self._dependencies = tuple(dependencies)
        self._channels = tuple(channels)

    @property
    def name(self):
        """Get name of the environment."""
        return self._name

    @property
    def dependencies(self):
        """Get the dependencies to install in the environment as an iterable."""
        return self._dependencies

    @property
    def channels(self):
        """Get the channels to install dependencies from."""
        return self._channels

    @property
    def conda_package_names_set(self):
        """Conda package names that the environment must contain, as a set."""
        names = set()
        for spec in self.dependencies:
            pieces = spec.split(' ', 2)
            name = pieces[0]
            names.add(name)
        return names

    def path(self, project_dir):
        """The filesystem path to this environment (or the path it would have if it existed)."""
        return os.path.join(project_dir, ".envs", self.name)
