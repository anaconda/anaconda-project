"""Project class representing a project directory."""
from __future__ import absolute_import

from project.internal.project_file import ProjectFile


class Project(object):
    """Represents the information we've inferred about a project.

    The Project class encapsulates information from the project
    file, and also anything else we've guessed by snooping around in
    the project directory or global user configuration.
    """

    def __init__(self, directory_path, requirement_registry):
        """Construct a Project with the given directory and requirements registry.

        Args:
            directory_path (str): path to the project directory
            requirement_registry (RequirementRegistry): where to look up Requirement instances
        """
        self.project_file = ProjectFile.load_for_directory(directory_path, requirement_registry)

    @property
    def requirements(self):
        """Required items in order to run this project (list of ``Requirement`` instances)."""
        return self.project_file.requirements

    @property
    def problems(self):
        """List of strings describing problems with the project configuration."""
        return self.project_file.problems
