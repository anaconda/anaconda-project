"""Project class representing a project directory."""
from __future__ import absolute_import

import os

from project.project_file import ProjectFile
from project.conda_meta_file import CondaMetaFile
from project.plugins.requirement import RequirementRegistry


class _ConfigCache(object):
    def __init__(self, requirement_registry):
        if requirement_registry is None:
            requirement_registry = RequirementRegistry()
        self.requirement_registry = requirement_registry

        self.project_file_count = 0
        self.conda_meta_file_count = 0

    def update(self, project_file, conda_meta_file):
        if project_file.change_count == self.project_file_count and \
           conda_meta_file.change_count == self.conda_meta_file_count:
            return

        self.project_file_count = project_file.change_count
        self.conda_meta_file_count = conda_meta_file.change_count

        requirements = []
        problems = []

        if project_file.corrupted:
            problems.append("%s has a syntax error that needs to be fixed by hand: %s" %
                            (project_file.filename, project_file.corrupted_error_message))
        if conda_meta_file.corrupted:
            problems.append("%s has a syntax error that needs to be fixed by hand: %s" %
                            (conda_meta_file.filename, conda_meta_file.corrupted_error_message))

        if not (project_file.corrupted or conda_meta_file.corrupted):
            self._update_runtime(requirements, problems, project_file)
            self._validate_package_requirements(problems, project_file, conda_meta_file)

        self.requirements = requirements
        self.problems = problems

    def _update_runtime(self, requirements, problems, project_file):
        runtime = project_file.get_value("runtime")
        # runtime: section can contain a list of var names
        # or a dict from var names to options. it can also
        # be missing
        if runtime is None:
            pass
        elif isinstance(runtime, dict):
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

    def _validate_package_requirements(self, problems, project_file, conda_meta_file):
        def validate(yaml_file):
            found = yaml_file.requirements_run
            if not isinstance(found, (list, tuple)):
                problems.append("%s: requirements: run: value should be a list of strings, not '%r'" %
                                (yaml_file.filename, found))
            else:
                for item in found:
                    if not isinstance(item, str):
                        problems.append("%s: requirements: run: value should be a string not '%r'" %
                                        (yaml_file.filename, item))
                        # future: validate MatchSpec

        validate(project_file)
        validate(conda_meta_file)


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
        self._project_file = ProjectFile.load_for_directory(directory_path)
        self._conda_meta_file = CondaMetaFile.load_for_directory(directory_path)
        self._directory_basename = os.path.basename(self._directory_path)
        self._config_cache = _ConfigCache(requirement_registry)

    def _updated_cache(self):
        self._config_cache.update(self._project_file, self._conda_meta_file)
        return self._config_cache

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
        return self._updated_cache().requirements

    @property
    def problems(self):
        """List of strings describing problems with the project configuration.

        This list contains problems which keep the project from loading, such as corrupt
        config files; it does not contain missing requirements and other "expected"
        problems.
        """
        return self._updated_cache().problems

    def _search_project_then_meta(self, attr, fallback):
        project_value = getattr(self.project_file, attr)
        if project_value is not None:
            return project_value

        meta_value = getattr(self.conda_meta_file, attr)
        if meta_value is not None:
            return meta_value

        return fallback

    def _combine_project_then_meta_lists(self, attr):
        project_value = getattr(self.project_file, attr, [])
        meta_value = getattr(self.conda_meta_file, attr, [])
        return project_value + meta_value

    @property
    def name(self):
        """Get the "package: name" field from either project.yml or meta.yaml."""
        return self._search_project_then_meta('name', fallback=self._directory_basename)

    @property
    def version(self):
        """Get the "package: version" field from either project.yml or meta.yaml."""
        return self._search_project_then_meta('version', fallback="unknown")

    @property
    def requirements_run(self):
        """Get the combined "requirements: run" lists from both project.yml and meta.yaml.

        The returned list is a list of strings in conda "match
        specification" format (see
        http://conda.pydata.org/docs/spec.html#build-version-spec
        and the ``conda.resolve.MatchSpec`` class).
        """
        return self._combine_project_then_meta_lists('requirements_run')
