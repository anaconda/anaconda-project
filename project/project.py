"""Project class representing a project directory."""
from __future__ import absolute_import

import os

from project.project_file import ProjectFile
from project.conda_meta_file import CondaMetaFile
from project.conda_environment import CondaEnvironment
from project.project_commands import ProjectCommand
from project.plugins.registry import PluginRegistry
from project.plugins.requirements.conda_env import CondaEnvRequirement


class _ConfigCache(object):
    def __init__(self, registry):
        if registry is None:
            registry = PluginRegistry()
        self.registry = registry

        self.commands = dict()
        self.default_command_name = None
        self.project_file_count = 0
        self.conda_meta_file_count = 0
        self.conda_environments = dict()
        self.default_conda_environment_name = 'default'

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
            # future: we could un-hardcode this so plugins can add stuff here
            self._update_runtime(requirements, problems, project_file)
            self._update_conda_environments(problems, project_file)
            # this MUST be after we _update_runtime since we may get CondaEnvRequirement
            # options in the runtime section, and after _update_conda_environments
            # since we use those
            self._update_conda_env_requirements(requirements, problems, project_file)

            self._update_commands(problems, project_file, conda_meta_file)

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
                    requirement = self.registry.find_requirement_by_env_var(key, options)
                    requirements.append(requirement)
                else:
                    problems.append(("runtime section has key {key} with value {options}; the value " +
                                     "must be a dict of options, instead.").format(key=key,
                                                                                   options=options))
        elif isinstance(runtime, list):
            for item in runtime:
                if isinstance(item, str):
                    requirement = self.registry.find_requirement_by_env_var(item, options=dict())
                    requirements.append(requirement)
                else:
                    problems.append(
                        "runtime section should contain environment variable names, {item} is not a string".format(
                            item=item))
        else:
            problems.append(
                "runtime section contains wrong value type {runtime}, should be dict or list of requirements".format(
                    runtime=runtime))

    def _update_conda_environments(self, problems, project_file):
        def _parse_dependencies(deps):
            if not isinstance(deps, (list, tuple)):
                problems.append("%s: dependencies: value should be a list of package names, not '%r'" %
                                (project_file.filename, deps))
                return []
            cleaned = []
            for dep in deps:
                if isinstance(dep, str):
                    cleaned.append(dep.strip())
                else:
                    problems.append("%s: dependencies: value should be a package name (as a string) not '%r'" %
                                    (project_file.filename, dep))
            return cleaned

        self.conda_environments = dict()
        shared_deps = _parse_dependencies(project_file.get_value('dependencies', default=[]))
        environments = project_file.get_value('environments', default={})
        first_listed_name = None
        if isinstance(environments, dict):
            for (name, attrs) in environments.items():
                if first_listed_name is None:
                    first_listed_name = name
                if 'dependencies' in attrs:
                    deps = _parse_dependencies(attrs.get('dependencies'))
                else:
                    deps = []
                # ideally we would merge same-name packages here, choosing the
                # highest of the two versions or something. maybe conda will
                # do that for us anyway?
                all_deps = shared_deps + deps
                self.conda_environments[name] = CondaEnvironment(name=name, dependencies=all_deps)
        else:
            problems.append(
                "%s: environments should be a dictionary from environment name to environment attributes, not %r" %
                (project_file.filename, environments))

        # invariant is that we always have at least one
        # environment; it doesn't have to be named 'default' but
        # we name it that if no named environment was created.
        if len(self.conda_environments) == 0:
            self.conda_environments['default'] = CondaEnvironment(name='default', dependencies=shared_deps)

        if 'default' in self.conda_environments:
            self.default_conda_environment_name = 'default'
        else:
            self.default_conda_environment_name = first_listed_name

    def _update_conda_env_requirements(self, requirements, problems, project_file):
        if problems:
            return

        # use existing CondaEnvRequirement if it was created via env var
        env_requirement = None
        for r in requirements:
            if isinstance(r, CondaEnvRequirement):
                env_requirement = r

        if env_requirement is None:
            env_requirement = CondaEnvRequirement(registry=self.registry,
                                                  environments=self.conda_environments,
                                                  default_environment_name=self.default_conda_environment_name)
            requirements.append(env_requirement)
        else:
            env_requirement.environments = self.conda_environments
            env_requirement.default_environment_name = self.default_conda_environment_name

    def _update_commands(self, problems, project_file, conda_meta_file):
        failed = False

        app_entry_from_meta_yaml = conda_meta_file.app_entry
        if app_entry_from_meta_yaml is not None:
            if not isinstance(app_entry_from_meta_yaml, str):
                problems.append("%s: app: entry: should be a string not '%r'" %
                                (conda_meta_file.filename, app_entry_from_meta_yaml))
                app_entry_from_meta_yaml = None
                failed = True

        first_command_name = None
        commands = dict()
        commands_section = project_file.get_value('commands', None)
        if commands_section is not None and not isinstance(commands_section, dict):
            problems.append("%s: 'commands:' section should be a dictionary from command names to attributes, not %r" %
                            (project_file.filename, commands_section))
            failed = True
        elif commands_section is not None:
            for (name, attrs) in commands_section.items():
                if first_command_name is None:
                    first_command_name = name

                if not isinstance(attrs, dict):
                    problems.append("%s: command name '%s' should be followed by a dictionary of attributes not %r" %
                                    (project_file.filename, name, attrs))
                    continue

                copy = attrs.copy()
                # default conda_app_entry to the one from meta.yaml
                if 'conda_app_entry' not in copy and app_entry_from_meta_yaml is not None:
                    copy['conda_app_entry'] = app_entry_from_meta_yaml

                if len(copy) == 0:
                    problems.append("%s: command '%s' does not have a command line in it" %
                                    (project_file.filename, name))
                    failed = True

                # for the moment, all possible attributes are command line strings, so
                # we can check them all in the same way
                for attr in attrs:
                    if not isinstance(attrs[attr], str):
                        problems.append("%s: command '%s' attribute '%s' should be a string not '%r'" %
                                        (project_file.filename, name, attr, attrs[attr]))
                        failed = True

                commands[name] = ProjectCommand(name=name, attributes=copy)

        if failed:
            self.commands = dict()
            self.default_command_name = None
        else:
            # if no commands and we have a meta.yaml app entry, use the meta.yaml
            if app_entry_from_meta_yaml is not None and len(commands) == 0:
                commands['default'] = ProjectCommand(name='default',
                                                     attributes=dict(conda_app_entry=app_entry_from_meta_yaml))

            self.commands = commands
            if 'default' in commands:
                self.default_command_name = 'default'
            else:
                # note: this may be None
                self.default_command_name = first_command_name


class Project(object):
    """Represents the information we've inferred about a project.

    The Project class encapsulates information from the project
    file, and also anything else we've guessed by snooping around in
    the project directory or global user configuration.
    """

    def __init__(self, directory_path, plugin_registry=None):
        """Construct a Project with the given directory and plugin registry.

        Args:
            directory_path (str): path to the project directory
            plugin_registry (PluginRegistry): where to look up Requirement and Provider instances, None for default
        """
        self._directory_path = os.path.realpath(directory_path)
        self._project_file = ProjectFile.load_for_directory(directory_path)
        self._conda_meta_file = CondaMetaFile.load_for_directory(directory_path)
        self._directory_basename = os.path.basename(self._directory_path)
        self._config_cache = _ConfigCache(plugin_registry)

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
    def plugin_registry(self):
        """Get the ``PluginRegistry`` for this project."""
        return self._config_cache.registry

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

    @property
    def name(self):
        """Get the "package: name" field from either project.yml or meta.yaml."""
        return self._search_project_then_meta('name', fallback=self._directory_basename)

    @property
    def version(self):
        """Get the "package: version" field from either project.yml or meta.yaml."""
        return self._search_project_then_meta('version', fallback="unknown")

    @property
    def conda_environments(self):
        """Get a dictionary of environment names to CondaEnvironment instances."""
        return self._updated_cache().conda_environments

    @property
    def default_conda_environment_name(self):
        """Get the named environment to use by default.

        This will be the one named "default" if it exists, and
        otherwise the first-listed one.
        """
        return self._updated_cache().default_conda_environment_name

    @property
    def commands(self):
        """Get the dictionary of commands to run the project.

        This dictionary can be empty.

        Returns:
            dictionary of command names to ``ProjectCommand``
        """
        return self._updated_cache().commands

    @property
    def default_command(self):
        """Get the default ``ProjectCommand`` or None if we don't have one.

        Returns:
            the default ``ProjectCommand``
        """
        cache = self._updated_cache()
        if cache.default_command_name is None:
            return None
        else:
            return cache.commands[cache.default_command_name]

    def launch_argv_for_environment(self, environ):
        """Get a usable argv with any processing and interpretation necessary to execute it.

        Args:
            environ (dict): the environment
        Returns:
            argv as list of strings, or None if no commands are configured
        """
        # we use ANACONDA_PROJECT_COMMAND if configured and otherwise
        # the default command
        command_name = environ.get('ANACONDA_PROJECT_COMMAND', self._updated_cache().default_command_name)
        if command_name is None:
            return None
        command = self._updated_cache().commands[command_name]

        return command.launch_argv_for_environment(environ)
