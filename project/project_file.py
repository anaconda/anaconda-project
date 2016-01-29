from __future__ import absolute_import

import os

from project.yaml_file import YamlFile

# use .yml not .yaml to make Windows happy
PROJECT_FILENAME = "project.yml"


class ProjectFile(YamlFile):
    """Represents the project.yml file.

    This class is internal because everyone needs to use a singleton instance,
    if code loads the file itself it doesn't know when to reload because
    some other code made changes.
    """

    @classmethod
    def ensure_for_directory(cls, directory, requirement_registry):
        path = os.path.join(directory, PROJECT_FILENAME)
        project_file = ProjectFile(path, requirement_registry)
        if not os.path.exists(path):
            project_file.save()
        return project_file

    @classmethod
    def load_for_directory(cls, directory, requirement_registry):
        path = os.path.join(directory, PROJECT_FILENAME)
        return ProjectFile(path, requirement_registry)

    def __init__(self, filename, requirement_registry):
        self.requirement_registry = requirement_registry
        super(ProjectFile, self).__init__(filename)

    def load(self):
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
        return self._requirements

    @property
    def problems(self):
        return self._problems
