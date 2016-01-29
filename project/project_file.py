"""Project file loading and manipulation."""
from __future__ import absolute_import

import os

from project.yaml_file import YamlFile

# use .yml not .yaml to make Windows happy
PROJECT_FILENAME = "project.yml"


class ProjectFile(YamlFile):
    """Represents the ``project.yml`` file which describes the project across machines/users.

    State that's specific to a machine/user/checkout/deployment
    should instead be in ``LocalStateFile``.  ``ProjectFile``
    would normally be checked in to source control or otherwise
    act as a shared resource.

    Be careful with creating your own instance of this class,
    because you have to think about when other code might load or
    save in a way that conflicts with your loads and saves.

    """

    @classmethod
    def ensure_for_directory(cls, directory, requirement_registry):
        """Load the project file from the given directory, forcing it to exist.

        This function saves the file immediately.

        TODO: get rid of this function. also the .exists is not
        necessary below because save() is a no-op if not dirty.

        Args:
            directory (str): path to the project directory
            requirement_registry (RequirementRegistry): for looking up Requirement instances

        Returns:
            a new ``ProjectFile``
        """
        path = os.path.join(directory, PROJECT_FILENAME)
        project_file = ProjectFile(path, requirement_registry)
        if not os.path.exists(path):
            project_file.save()
        return project_file

    @classmethod
    def load_for_directory(cls, directory, requirement_registry):
        """Load the project file from the given directory, even if it doesn't exist.

        If the directory has no project file, the loaded
        ``ProjectFile`` will be empty. It won't actually be
        created on disk unless you call ``save()``.

        If the project file has syntax problems, this raises
        an exception from the YAML parser. If the project file
        has semantic problems, the ``problems`` property will be
        set describing them.

        Args:
            directory (str): path to the project directory
            requirement_registry (RequirementRegistry): for
                looking up Requirement instances based on the config
                in the file

        Returns:
            a new ``ProjectFile``

        """
        path = os.path.join(directory, PROJECT_FILENAME)
        return ProjectFile(path, requirement_registry)

    def __init__(self, filename, requirement_registry):
        """Construct a ``ProjectFile`` with the given filename and requirement registry.

        It's easier to use ``ProjectFile.load_for_directory()`` in most cases.

        If the project file has syntax problems, this raises
        an exception from the YAML parser. If the project file
        has semantic problems, the ``problems`` property will be
        set describing them.

        Args:
            filename (str): path to the project file
            requirement_registry (RequirementRegistry): for
                looking up Requirement instances based on the config in
                the project file
        """
        self.requirement_registry = requirement_registry
        super(ProjectFile, self).__init__(filename)

    def load(self):
        """Extend superclass to also initialize ``requirements`` and ``problems`` properties."""
        super(ProjectFile, self).load()
        requirements = []
        problems = []
        runtime = self.get_value("runtime")
        # runtime: section can contain a list of var names
        # or a dict from var names to options
        if isinstance(runtime, dict):
            for key in runtime.keys():
                options = runtime[key]
                if isinstance(options, dict):
                    requirement = self.requirement_registry.find_by_env_var(key, options)
                    requirements.append(requirement)
                else:
                    problems.append(("runtime section has key {key} with value {options}; the value " +
                                     "must be a dict of options, instead.").format(key=key,
                                                                                   options=options))
        elif isinstance(runtime, list):
            for item in runtime:
                if isinstance(item, str):
                    requirement = self.requirement_registry.find_by_env_var(item, options=dict())
                    requirements.append(requirement)
                else:
                    problems.append(
                        "runtime section should contain environment variable names, {item} is not a string".format(
                            item=item))
        else:
            problems.append(
                "runtime section contains wrong value type {runtime}, should be dict or list of requirements".format(
                    runtime=runtime))

        self._requirements = requirements
        self._problems = problems

    def _default_comment(self):
        return "Anaconda project file"

    @property
    def requirements(self):
        """``Requirement`` instances describing this project's configured requirements."""
        return self._requirements

    @property
    def problems(self):
        """List of error message strings describing problems with the project configuration."""
        return self._problems
