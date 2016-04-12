# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Project class representing a project directory."""
from __future__ import absolute_import

import os

from anaconda_project.conda_environment import CondaEnvironment
from anaconda_project.conda_meta_file import CondaMetaFile, META_DIRECTORY
from anaconda_project.plugins.registry import PluginRegistry
from anaconda_project.plugins.requirement import EnvVarRequirement
from anaconda_project.plugins.requirements.conda_env import CondaEnvRequirement
from anaconda_project.plugins.requirements.download import DownloadRequirement
from anaconda_project.project_commands import ProjectCommand
from anaconda_project.project_file import ProjectFile

from anaconda_project.internal.directory_contains import subdirectory_relative_to_directory


class _ConfigCache(object):
    def __init__(self, directory_path, registry, default_default_conda_environment_name, default_default_command_name):
        self.directory_path = directory_path
        if registry is None:
            registry = PluginRegistry()
        self.registry = registry

        self.name = None
        self.icon = None
        self.commands = dict()
        if default_default_command_name is None:
            self.default_default_command_name = 'default'
        else:
            self.default_default_command_name = default_default_command_name
        self.default_command_name = None
        self.project_file_count = 0
        self.conda_meta_file_count = 0
        self.conda_environments = dict()
        if default_default_conda_environment_name is None:
            self.default_default_conda_environment_name = 'default'
        else:
            self.default_default_conda_environment_name = default_default_conda_environment_name
        self.default_conda_environment_name = None

    def update(self, project_file, conda_meta_file):
        if project_file.change_count == self.project_file_count and \
           conda_meta_file.change_count == self.conda_meta_file_count:
            return

        self.project_file_count = project_file.change_count
        self.conda_meta_file_count = conda_meta_file.change_count

        requirements = []
        problems = []

        project_exists = os.path.isdir(self.directory_path)
        if not project_exists:
            problems.append("Project directory '%s' does not exist." % self.directory_path)

        if project_file.corrupted:
            problems.append("%s has a syntax error that needs to be fixed by hand: %s" %
                            (project_file.filename, project_file.corrupted_error_message))
        if conda_meta_file.corrupted:
            problems.append("%s has a syntax error that needs to be fixed by hand: %s" %
                            (conda_meta_file.filename, conda_meta_file.corrupted_error_message))

        if project_exists and not (project_file.corrupted or conda_meta_file.corrupted):
            self._update_name(problems, project_file, conda_meta_file)
            self._update_icon(problems, project_file, conda_meta_file)
            # future: we could un-hardcode this so plugins can add stuff here
            self._update_runtime(requirements, problems, project_file)
            self._update_downloads(requirements, problems, project_file)
            self._update_conda_environments(problems, project_file)
            # this MUST be after we _update_runtime since we may get CondaEnvRequirement
            # options in the runtime section, and after _update_conda_environments
            # since we use those
            self._update_conda_env_requirements(requirements, problems, project_file)

            self._update_commands(problems, project_file, conda_meta_file)

        self.requirements = requirements
        self.problems = problems

    def _update_name(self, problems, project_file, conda_meta_file):
        name = project_file.name
        if name is not None and not isinstance(name, str):
            problems.append("%s: name: field should have a string value not %r" % (project_file.filename, name))
            name = None

        if name is None:
            name = conda_meta_file.name
            if name is not None and not isinstance(name, str):
                problems.append("%s: package: name: field should have a string value not %r" %
                                (conda_meta_file.filename, name))
                name = None

        if name is None:
            name = os.path.basename(self.directory_path)

        self.name = name

    def _update_icon(self, problems, project_file, conda_meta_file):
        icon = project_file.icon
        if icon is not None and not isinstance(icon, str):
            problems.append("%s: icon: field should have a string value not %r" % (project_file.filename, icon))
            icon = None

        if icon is None:
            icon = conda_meta_file.icon
            if icon is not None and not isinstance(icon, str):
                problems.append("%s: app: icon: field should have a string value not %r" %
                                (conda_meta_file.filename, icon))
                icon = None
            if icon is not None:
                # relative to conda.recipe
                icon = os.path.join(META_DIRECTORY, icon)

        if icon is not None:
            icon = os.path.join(self.directory_path, icon)
            if not os.path.isfile(icon):
                problems.append("Icon file %s does not exist." % icon)
                icon = None

        self.icon = icon

    def _update_runtime(self, requirements, problems, project_file):
        runtime = project_file.get_value("runtime")

        def check_conda_reserved(key):
            if key in ('CONDA_DEFAULT_ENV', 'CONDA_ENV_PATH'):
                problems.append(("Environment variable %s is reserved for Conda's use, " +
                                 "so it can't appear in the runtime section.") % key)
                return True
            else:
                return False

        # runtime: section can contain a list of var names
        # or a dict from var names to options. it can also
        # be missing
        if runtime is None:
            pass
        elif isinstance(runtime, dict):
            for key in runtime.keys():
                if check_conda_reserved(key):
                    continue
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
                    if check_conda_reserved(item):
                        continue
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

    def _update_downloads(self, requirements, problems, project_file):
        downloads = project_file.get_value('downloads')

        if downloads is None:
            return

        if not isinstance(downloads, dict):
            problems.append("'downloads:' section should be a dictionary, found {}".format(repr(downloads)))
            return

        for varname, item in downloads.items():
            DownloadRequirement.parse(self.registry, varname, item, problems, requirements)

    def _update_conda_environments(self, problems, project_file):
        def _parse_string_list(parent_dict, key, what):
            items = parent_dict.get(key, [])
            if not isinstance(items, (list, tuple)):
                problems.append("%s: %s: value should be a list of %ss, not '%r'" %
                                (project_file.filename, key, what, items))
                return []
            cleaned = []
            for item in items:
                if isinstance(item, str):
                    cleaned.append(item.strip())
                else:
                    problems.append("%s: %s: value should be a %s (as a string) not '%r'" %
                                    (project_file.filename, key, what, item))
            return cleaned

        def _parse_channels(parent_dict):
            return _parse_string_list(parent_dict, 'channels', 'channel name')

        def _parse_dependencies(parent_dict):
            return _parse_string_list(parent_dict, 'dependencies', 'package name')

        self.conda_environments = dict()
        shared_deps = _parse_dependencies(project_file.root)
        shared_channels = _parse_channels(project_file.root)
        environments = project_file.get_value('environments', default={})
        first_listed_name = None
        if isinstance(environments, dict):
            for (name, attrs) in environments.items():
                if first_listed_name is None:
                    first_listed_name = name
                deps = _parse_dependencies(attrs)
                channels = _parse_channels(attrs)
                # ideally we would merge same-name packages here, choosing the
                # highest of the two versions or something. maybe conda will
                # do that for us anyway?
                all_deps = shared_deps + deps
                all_channels = shared_channels + channels
                self.conda_environments[name] = CondaEnvironment(name=name,
                                                                 dependencies=all_deps,
                                                                 channels=all_channels)
        else:
            problems.append(
                "%s: environments should be a dictionary from environment name to environment attributes, not %r" %
                (project_file.filename, environments))

        # invariant is that we always have at least one
        # environment; it doesn't have to be named 'default' but
        # we name it that if no named environment was created.
        if len(self.conda_environments) == 0:
            self.conda_environments['default'] = CondaEnvironment(name='default',
                                                                  dependencies=shared_deps,
                                                                  channels=shared_channels)

        if self.default_default_conda_environment_name in self.conda_environments:
            self.default_conda_environment_name = self.default_default_conda_environment_name
        else:
            # 'default' is always mapped to the first-listed if none is named 'default'
            if self.default_default_conda_environment_name == 'default':
                self.default_conda_environment_name = first_listed_name
            else:
                self.default_conda_environment_name = None
                problems.append("Environment name '%s' is not in %s, these names were found: %s" %
                                (self.default_default_conda_environment_name, project_file.filename,
                                 ", ".join(sorted(self.conda_environments.keys()))))

    def _update_conda_env_requirements(self, requirements, problems, project_file):
        if problems:
            return

        env_requirement = CondaEnvRequirement(registry=self.registry,
                                              environments=self.conda_environments,
                                              default_environment_name=self.default_conda_environment_name)
        requirements.append(env_requirement)

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

                have_command = False
                for attr in ('conda_app_entry', 'shell', 'windows', 'notebook', 'bokeh_app'):
                    if attr not in copy:
                        continue

                    # this should be True even if we have problems
                    # with the command line, since "no command
                    # line" error is confusing if there is one and
                    # it's broken
                    have_command = True

                    if not isinstance(copy[attr], str):
                        problems.append("%s: command '%s' attribute '%s' should be a string not '%r'" %
                                        (project_file.filename, name, attr, copy[attr]))
                        failed = True

                if not have_command:
                    problems.append("%s: command '%s' does not have a command line in it" %
                                    (project_file.filename, name))
                    failed = True

                if ('notebook' in copy or 'bokeh_app' in copy) and len(copy.keys()) > 1:
                    label = 'bokeh_app' if 'bokeh_app' in copy else 'notebook'
                    problems.append("%s: command '%s' has conflicting statements, '%s' must stand alone" %
                                    (project_file.filename, name, label))
                    failed = True

                commands[name] = ProjectCommand(name=name, attributes=copy)

        self._add_notebook_commands(commands)

        if failed:
            self.commands = dict()
            self.default_command_name = None
        else:
            # if no commands and we have a meta.yaml app entry, use the meta.yaml
            if app_entry_from_meta_yaml is not None and len(commands) == 0:
                commands['default'] = ProjectCommand(name='default',
                                                     attributes=dict(conda_app_entry=app_entry_from_meta_yaml))

            self.commands = commands

        if self.default_default_command_name in self.commands:
            self.default_command_name = self.default_default_command_name
        else:
            # 'default' is always mapped to the first-listed if none is named 'default'
            if self.default_default_command_name == 'default':
                # note: this may be None
                self.default_command_name = first_command_name
            else:
                problems.append("Command name '%s' is not in %s, these names were found: %s" %
                                (self.default_default_command_name, project_file.filename,
                                 ", ".join(sorted(self.commands.keys()))))
                self.default_command_name = None

    def _add_notebook_commands(self, commands):
        for dirpath, dirnames, filenames in os.walk(self.directory_path):
            for fname in filenames:
                if fname.endswith('.ipynb'):
                    relative_name = subdirectory_relative_to_directory(
                        os.path.join(dirpath, fname), self.directory_path)

                    if relative_name not in commands:
                        commands[relative_name] = ProjectCommand(name=relative_name,
                                                                 attributes={'notebook': relative_name})


class Project(object):
    """Represents the information we've inferred about a project.

    The Project class encapsulates information from the project
    file, and also anything else we've guessed by snooping around in
    the project directory or global user configuration.
    """

    def __init__(self, directory_path, plugin_registry=None, default_conda_environment=None, default_command=None):
        """Construct a Project with the given directory and plugin registry.

        Args:
            directory_path (str): path to the project directory
            plugin_registry (PluginRegistry): where to look up Requirement and Provider instances, None for default
            default_conda_environment (str): name of conda environment spec to use by default
            default_command (str): name of command from commands section to use by default
        """
        self._directory_path = os.path.realpath(directory_path)
        self._project_file = ProjectFile.load_for_directory(directory_path)
        self._conda_meta_file = CondaMetaFile.load_for_directory(directory_path)
        self._directory_basename = os.path.basename(self._directory_path)
        self._config_cache = _ConfigCache(self._directory_path, plugin_registry, default_conda_environment,
                                          default_command)

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

    @property
    def name(self):
        """Get the project name.

        Prefers in order: `name` field from project.yml, `package:
        name:` from meta.yaml, then project directory name.
        """
        return self._updated_cache().name

    @property
    def icon(self):
        """Get the project's icon as an absolute path or None if no icon.

        Prefers in order: `icon` field from project.yml, `app:
        icon:` from meta.yaml.
        """
        return self._updated_cache().icon

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

    def exec_info_for_environment(self, environ, extra_args=None):
        """Get the information needed to run the project.

        Args:
            environ (dict): the environment
            extra_args (list of str): extra args to append to the command line
        Returns:
            argv as list of strings, or None if no commands are configured that work on our platform
        """
        # we use ANACONDA_PROJECT_COMMAND if configured and otherwise
        # the default command
        command_name = environ.get('ANACONDA_PROJECT_COMMAND', self._updated_cache().default_command_name)
        if command_name is None:
            return None
        command = self._updated_cache().commands[command_name]

        return command.exec_info_for_environment(environ, extra_args)

    def publication_info(self):
        """Get JSON-serializable information to be stored as metadata when publishing the project.

        This is a "baked" version of project.yml which also
        includes any defaults or automatic configuration.

        Before calling this, check that Project.problems is empty.

        Returns:
            A dictionary containing JSON-compatible types.
        """
        json = dict()
        json['name'] = self.name
        commands = dict()
        for key, command in self.commands.items():
            commands[key] = dict(description=command.description)
            if command.bokeh_app is not None:
                commands[key]['bokeh_app'] = command.bokeh_app
            if command.notebook is not None:
                commands[key]['notebook'] = command.notebook
        json['commands'] = commands
        envs = dict()
        for key, env in self.conda_environments.items():
            envs[key] = dict(dependencies=list(env.dependencies), channels=list(env.channels))
        json['environments'] = envs
        variables = dict()
        downloads = dict()
        for req in self.requirements:
            if isinstance(req, CondaEnvRequirement):
                continue
            elif isinstance(req, DownloadRequirement):
                downloads[req.env_var] = dict(title=req.title, encrypted=req.encrypted, url=req.url)
            elif isinstance(req, EnvVarRequirement):
                variables[req.env_var] = dict(title=req.title, encrypted=req.encrypted)
        json['downloads'] = downloads
        json['variables'] = variables

        return json
