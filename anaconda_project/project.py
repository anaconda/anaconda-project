# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Project class representing a project directory."""
from __future__ import absolute_import

from copy import deepcopy
import os

from anaconda_project.conda_environment import CondaEnvironment
from anaconda_project.conda_meta_file import CondaMetaFile, META_DIRECTORY
from anaconda_project.plugins.registry import PluginRegistry
from anaconda_project.plugins.requirement import EnvVarRequirement
from anaconda_project.plugins.requirements.conda_env import CondaEnvRequirement
from anaconda_project.plugins.requirements.download import DownloadRequirement
from anaconda_project.plugins.requirements.service import ServiceRequirement
from anaconda_project.project_commands import ProjectCommand
from anaconda_project.project_file import ProjectFile
from anaconda_project.bundler import _list_relative_paths_for_unignored_project_files

from anaconda_project.internal.py2_compat import is_string
from anaconda_project.internal.simple_status import SimpleStatus

# These strings are used in the command line options to anaconda-project,
# so changing them has back-compat consequences.
COMMAND_TYPE_CONDA_APP_ENTRY = 'conda_app_entry'
COMMAND_TYPE_SHELL = 'unix'
COMMAND_TYPE_WINDOWS = 'windows'
COMMAND_TYPE_NOTEBOOK = 'notebook'
COMMAND_TYPE_BOKEH_APP = 'bokeh_app'

ALL_COMMAND_TYPES = (COMMAND_TYPE_CONDA_APP_ENTRY, COMMAND_TYPE_SHELL, COMMAND_TYPE_WINDOWS, COMMAND_TYPE_NOTEBOOK,
                     COMMAND_TYPE_BOKEH_APP)


class _ConfigCache(object):
    def __init__(self, directory_path, registry):
        self.directory_path = directory_path
        if registry is None:
            registry = PluginRegistry()
        self.registry = registry

        self.name = None
        self.icon = None
        self.commands = dict()
        self.default_command_name = None
        self.project_file_count = 0
        self.conda_meta_file_count = 0
        self.conda_environments = dict()
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
            self._update_variables(requirements, problems, project_file)
            self._update_downloads(requirements, problems, project_file)
            self._update_services(requirements, problems, project_file)
            self._update_conda_environments(problems, project_file)
            # this MUST be after we _update_variables since we may get CondaEnvRequirement
            # options in the variables section, and after _update_conda_environments
            # since we use those
            self._update_conda_env_requirements(requirements, problems, project_file)

            self._update_commands(problems, project_file, conda_meta_file, requirements)

        self.requirements = requirements
        self.problems = problems

    def _update_name(self, problems, project_file, conda_meta_file):
        name = project_file.name
        if name is not None:
            if not is_string(name):
                problems.append("%s: name: field should have a string value not %r" % (project_file.filename, name))
                name = None
            elif len(name.strip()) == 0:
                problems.append("%s: name: field is an empty or all-whitespace string." % (project_file.filename))
                name = None

        if name is None:
            name = conda_meta_file.name
            if name is not None and not is_string(name):
                problems.append("%s: package: name: field should have a string value not %r" %
                                (conda_meta_file.filename, name))
                name = None

        if name is None:
            name = os.path.basename(self.directory_path)

        self.name = name

    def _update_icon(self, problems, project_file, conda_meta_file):
        icon = project_file.icon
        if icon is not None and not is_string(icon):
            problems.append("%s: icon: field should have a string value not %r" % (project_file.filename, icon))
            icon = None

        if icon is None:
            icon = conda_meta_file.icon
            if icon is not None and not is_string(icon):
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

    def _update_variables(self, requirements, problems, project_file):
        variables = project_file.get_value("variables")

        def check_conda_reserved(key):
            if key in ('CONDA_DEFAULT_ENV', 'CONDA_ENV_PATH'):
                problems.append(("Environment variable %s is reserved for Conda's use, " +
                                 "so it can't appear in the variables section.") % key)
                return True
            else:
                return False

        # variables: section can contain a list of var names or a dict from
        # var names to options OR default values. it can also be missing
        # entirely which is the same as empty.
        if variables is None:
            pass
        elif isinstance(variables, dict):
            for key in variables.keys():
                if check_conda_reserved(key):
                    continue
                if key.strip() == '':
                    problems.append("Variable name cannot be empty string, found: '{}' as name".format(key))
                    continue
                raw_options = variables[key]

                if raw_options is None:
                    options = {}
                elif isinstance(raw_options, dict):
                    options = deepcopy(raw_options)  # so we can modify it below
                else:
                    options = dict(default=raw_options)

                assert (isinstance(options, dict))

                if EnvVarRequirement._parse_default(options, key, problems):
                    requirement = self.registry.find_requirement_by_env_var(key, options)
                    requirements.append(requirement)
        elif isinstance(variables, list):
            for item in variables:
                if is_string(item):
                    if item.strip() == '':
                        problems.append("Variable name cannot be empty string, found: '{}' as name".format(item))
                        continue
                    if check_conda_reserved(item):
                        continue
                    requirement = self.registry.find_requirement_by_env_var(item, options=dict())
                    requirements.append(requirement)
                else:
                    problems.append(
                        "variables section should contain environment variable names, {item} is not a string".format(
                            item=item))
        else:
            problems.append(
                "variables section contains wrong value type {value}, should be dict or list of requirements".format(
                    value=variables))

    def _update_downloads(self, requirements, problems, project_file):
        downloads = project_file.get_value('downloads')

        if downloads is None:
            return

        if not isinstance(downloads, dict):
            problems.append("{}: 'downloads:' section should be a dictionary, found {}".format(project_file.filename,
                                                                                               repr(downloads)))
            return

        for varname, item in downloads.items():
            if varname.strip() == '':
                problems.append("Download name cannot be empty string, found: '{}' as name".format(varname))
                continue
            DownloadRequirement._parse(self.registry, varname, item, problems, requirements)

    def _update_services(self, requirements, problems, project_file):
        services = project_file.get_value('services')

        if services is None:
            return

        if not isinstance(services, dict):
            problems.append(("{}: 'services:' section should be a dictionary from environment variable to " +
                             "service type, found {}").format(project_file.filename, repr(services)))
            return

        for varname, item in services.items():
            if varname.strip() == '':
                problems.append("Service name cannot be empty string, found: '{}' as name".format(varname))
                continue
            ServiceRequirement._parse(self.registry, varname, item, problems, requirements)

    def _update_conda_environments(self, problems, project_file):
        def _parse_string_list(parent_dict, key, what):
            items = parent_dict.get(key, [])
            if not isinstance(items, (list, tuple)):
                problems.append("%s: %s: value should be a list of %ss, not '%r'" %
                                (project_file.filename, key, what, items))
                return []
            cleaned = []
            for item in items:
                if is_string(item):
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
        if isinstance(environments, dict):
            for (name, attrs) in environments.items():
                if name.strip() == '':
                    problems.append("Environment variable name cannot be empty string, found: '{}' as name".format(
                        name))
                    continue
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

        # We ALWAYS have an environment named 'default' which is the default,
        # even if not explicitly listed.
        if 'default' not in self.conda_environments:
            self.conda_environments['default'] = CondaEnvironment(name='default',
                                                                  dependencies=shared_deps,
                                                                  channels=shared_channels)

        # since this never varies now, it's a little pointless, but we'll leave it here
        # as an abstraction in case we change our mind again.
        self.default_conda_environment_name = 'default'

    def _update_conda_env_requirements(self, requirements, problems, project_file):
        if problems:
            return

        env_requirement = CondaEnvRequirement(registry=self.registry,
                                              environments=self.conda_environments,
                                              default_environment_name=self.default_conda_environment_name)
        requirements.append(env_requirement)

    def _update_commands(self, problems, project_file, conda_meta_file, requirements):
        failed = False

        app_entry_from_meta_yaml = conda_meta_file.app_entry
        if app_entry_from_meta_yaml is not None:
            if not is_string(app_entry_from_meta_yaml):
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
                if name.strip() == '':
                    problems.append("Command variable name cannot be empty string, found: '{}' as name".format(name))
                    continue
                if first_command_name is None:
                    first_command_name = name

                if not isinstance(attrs, dict):
                    problems.append("%s: command name '%s' should be followed by a dictionary of attributes not %r" %
                                    (project_file.filename, name, attrs))
                    continue

                copy = deepcopy(attrs)

                have_command = False
                for attr in ALL_COMMAND_TYPES:
                    if attr not in copy:
                        continue

                    # this should be True even if we have problems
                    # with the command line, since "no command
                    # line" error is confusing if there is one and
                    # it's broken
                    have_command = True

                    if not is_string(copy[attr]):
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

        self._add_notebook_commands(commands, problems, requirements)

        if failed:
            self.commands = dict()
            self.default_command_name = None
        else:
            # if no commands and we have a meta.yaml app entry, use the meta.yaml
            if app_entry_from_meta_yaml is not None and len(commands) == 0:
                commands['default'] = ProjectCommand(name='default',
                                                     attributes=dict(conda_app_entry=app_entry_from_meta_yaml,
                                                                     auto_generated=True))

            self.commands = commands

        if first_command_name is None and len(commands) > 0:
            # this happens if we created a command automatically
            # from a notebook file or conda meta.yaml
            first_command_name = sorted(commands.keys())[0]

        if 'default' in self.commands:
            self.default_command_name = 'default'
        else:
            # 'default' is always mapped to the first-listed if none is named 'default'
            # note: this may be None
            self.default_command_name = first_command_name

    def _add_notebook_commands(self, commands, problems, requirements):
        files = _list_relative_paths_for_unignored_project_files(self.directory_path,
                                                                 problems,
                                                                 requirements=requirements)
        if files is None:
            assert problems != []
            return

        # chop out hidden directories. The
        # main reason to ignore dot directories is that they
        # might contain packages or git cache data or other
        # such gunk, not because we really care about
        # ".foo.ipynb" per se.
        files = [f for f in files if not f[0] == '.']

        for relative_name in files:
            if relative_name.endswith('.ipynb'):
                if relative_name not in commands:
                    commands[relative_name] = ProjectCommand(name=relative_name,
                                                             attributes={'notebook': relative_name,
                                                                         'auto_generated': True})


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
        self._config_cache = _ConfigCache(self._directory_path, plugin_registry)

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
    def service_requirements(self):
        """All requirements that are ServiceRequirement instances."""
        return self.find_requirements(klass=ServiceRequirement)

    @property
    def download_requirements(self):
        """All requirements that are DownloadRequirement instances."""
        return self.find_requirements(klass=DownloadRequirement)

    @property
    def all_variable_requirements(self):
        """All requirements that have an associated environment variable.

        Note: this will include services, downloads, and even CondaEnvRequirement.
        """
        return self.find_requirements(klass=EnvVarRequirement)

    @property
    def plain_variable_requirements(self):
        """All 'plain' variables (that aren't services, downloads, or a Conda environment for example).

        Use the ``all_variable_requirements`` property to get every variable.
        """
        return [req for req in self.all_variable_requirements if req.__class__ is EnvVarRequirement]

    def find_requirements(self, env_var=None, klass=None):
        """Find requirements that match the given env var and class.

        If env_var and klass are both provided, BOTH must match.

        Args:
           env_var (str): if not None, filter requirements that have this env_var
           klass (class): if not None, filter requirements that are an instance of this class

        Returns:
           list of matching requirements (may be empty)
        """
        found = []
        for req in self.requirements:
            if env_var is not None and not (isinstance(req, EnvVarRequirement) and req.env_var == env_var):
                continue
            if klass is not None and not isinstance(req, klass):
                continue
            found.append(req)
        return found

    @property
    def problems(self):
        """List of strings describing problems with the project configuration.

        This list contains problems which keep the project from loading, such as corrupt
        config files; it does not contain missing requirements and other "expected"
        problems.
        """
        return self._updated_cache().problems

    def problems_status(self, description=None):
        """Get a ``Status`` describing project problems, or ``None`` if no problems."""
        if len(self.problems) > 0:
            errors = []
            for problem in self.problems:
                errors.append(problem)
            if description is None:
                description = "Unable to load the project."
            return SimpleStatus(success=False, description=description, logs=[], errors=errors)
        else:
            return None

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
    def all_variables(self):
        """Get a list of strings with the variables names from ``all_variable_requirements``."""
        return [r.env_var for r in self.all_variable_requirements]

    @property
    def plain_variables(self):
        """Get a list of strings with the variables names from ``plain_variable_requirements``."""
        return [r.env_var for r in self.plain_variable_requirements]

    @property
    def services(self):
        """Get a list of strings with the variable names for the project services requirements."""
        return [r.env_var for r in self.service_requirements]

    @property
    def downloads(self):
        """Get a list of strings with the variable names for the project download requirements."""
        return [r.env_var for r in self.download_requirements]

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

    def exec_info_for_environment(self, environ, command_name=None, extra_args=None):
        """Get the information needed to run the project.

        Args:
            environ (dict): the environment
            command_name (str): the command to get info for, None for the default
            extra_args (list of str): extra args to append to the command line
        Returns:
            argv as list of strings, or None if no commands are configured that work on our platform
        """
        if command_name is None:
            command_name = self._updated_cache().default_command_name
        if command_name is None:
            return None
        assert command_name in self._updated_cache().commands
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
            if command is self.default_command:
                commands[key]['default'] = True
        json['commands'] = commands
        envs = dict()
        for key, env in self.conda_environments.items():
            envs[key] = dict(dependencies=list(env.dependencies), channels=list(env.channels))
        json['environments'] = envs
        variables = dict()
        downloads = dict()
        services = dict()
        for req in self.requirements:
            if isinstance(req, CondaEnvRequirement):
                continue
            elif isinstance(req, DownloadRequirement):
                downloads[req.env_var] = dict(title=req.title, encrypted=req.encrypted, url=req.url)
            elif isinstance(req, ServiceRequirement):
                services[req.env_var] = dict(title=req.title, type=req.service_type)
            elif isinstance(req, EnvVarRequirement):
                variables[req.env_var] = dict(title=req.title, encrypted=req.encrypted)
        json['downloads'] = downloads
        json['variables'] = variables
        json['services'] = services

        return json
