"""Project class representing a project directory."""
from __future__ import absolute_import

import os

from project.project_file import ProjectFile
from project.conda_meta_file import CondaMetaFile


class Project(object):
    """Represents the information we've inferred about a project.

    The Project class encapsulates information from the project
    file, and also anything else we've guessed by snooping around in
    the project directory or global user configuration.
    """

    def __init__(self, directory_path, requirement_registry=None):
        """Construct a Project with the given directory and requirements registry.

        Args:
            directory_path (str): path to the project directory
            requirement_registry (RequirementRegistry): where to look up Requirement instances, None for default
        """
        self._directory_path = os.path.realpath(directory_path)
        self._project_file = ProjectFile.load_for_directory(directory_path, requirement_registry)
        self._conda_meta_file = CondaMetaFile.load_for_directory(directory_path)
        self._directory_basename = os.path.basename(self._directory_path)

    @property
    def directory_path(self):
        """Get path to the project directory."""
        return self._directory_path

    @property
    def project_file(self):
        """Get the ``ProjectFile`` for this project."""
        return self._project_file

    @property
    def conda_meta_file(self):
        """Get the ``CondaMetaFile`` for this project."""
        return self._conda_meta_file

    @property
    def requirements(self):
        """Required items in order to run this project (list of ``Requirement`` instances)."""
        return self.project_file.requirements

    @property
    def problems(self):
        """List of strings describing problems with the project configuration."""
        return self.project_file.problems

    @property
    def name(self):
        """Get the "package: name" field from either project.yml or meta.yaml."""
        if self.project_file.name is not None:
            return self.project_file.name
        elif self.conda_meta_file.name is not None:
            return self.conda_meta_file.name
        else:
            return self._directory_basename

    @property
    def version(self):
        """Get the "package: version" field from either project.yml or meta.yaml."""
        if self.project_file.version is not None:
            return self.project_file.version
        elif self.conda_meta_file.version is not None:
            return self.conda_meta_file.version
        else:
            return "unknown"
