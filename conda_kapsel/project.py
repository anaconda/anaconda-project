# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Project class representing a project directory."""
from __future__ import absolute_import

from copy import deepcopy, copy
import os

from conda_kapsel.env_spec import EnvSpec
from conda_kapsel.conda_meta_file import CondaMetaFile, META_DIRECTORY
from conda_kapsel.plugins.registry import PluginRegistry
from conda_kapsel.plugins.requirement import EnvVarRequirement
from conda_kapsel.plugins.requirements.conda_env import CondaEnvRequirement
from conda_kapsel.plugins.requirements.download import DownloadRequirement
from conda_kapsel.plugins.requirements.service import ServiceRequirement
from conda_kapsel.project_commands import ProjectCommand
from conda_kapsel.project_file import ProjectFile
from conda_kapsel.archiver import _list_relative_paths_for_unignored_project_files

from conda_kapsel.internal.py2_compat import is_string
from conda_kapsel.internal.simple_status import SimpleStatus
import conda_kapsel.internal.conda_api as conda_api
import conda_kapsel.internal.pip_api as pip_api

# These strings are used in the command line options to conda-kapsel,
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
        self.description = ''
        self.icon = None
        self.commands = dict()
        self.default_command_name = None
        self.project_file_count = 0
        self.conda_meta_file_count = 0
        self.env_specs = dict()
        self.default_env_spec_name = None

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
            self._update_description(problems, project_file)
            self._update_icon(problems, project_file, conda_meta_file)
            # future: we could un-hardcode this so plugins can add stuff here
            self._update_variables(requirements, problems, project_file)
            self._update_downloads(requirements, problems, project_file)
            self._update_services(requirements, problems, project_file)
            self._update_env_specs(problems, project_file)
            # this MUST be after we _update_variables since we may get CondaEnvRequirement
            # options in the variables section, and after _update_env_specs
            # since we use those
            self._update_conda_env_requirements(requirements, problems, project_file)

            # this MUST be after we update env reqs so we have the valid env spec names
            self._update_commands(problems, project_file, conda_meta_file, requirements)

        self.requirements = requirements
        self.problems = problems

    def _update_name(self, problems, project_file, conda_meta_file):
        name = project_file.get_value('name', None)
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

    def _update_description(self, problems, project_file):
        desc = project_file.get_value('description', None)
        if desc is not None and not is_string(desc):
            problems.append("%s: description: field should have a string value not %r" % (project_file.filename, desc))
            desc = None

        if desc is None:
            desc = ''

        self.description = desc

    def _update_icon(self, problems, project_file, conda_meta_file):
        icon = project_file.get_value('icon', None)
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
            if key in ('CONDA_DEFAULT_ENV', 'CONDA_ENV_PATH', 'CONDA_PREFIX'):
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

    def _update_env_specs(self, problems, project_file):
        def _parse_string_list_with_special(parent_dict, key, what, special_filter):
            items = parent_dict.get(key, [])
            if not isinstance(items, (list, tuple)):
                problems.append("%s: %s: value should be a list of %ss, not '%r'" %
                                (project_file.filename, key, what, items))
                return ([], [])
            cleaned = []
            special = []
            for item in items:
                if is_string(item):
                    cleaned.append(item.strip())
                elif special_filter(item):
                    special.append(item)
                else:
                    problems.append("%s: %s: value should be a %s (as a string) not '%r'" %
                                    (project_file.filename, key, what, item))
            return (cleaned, special)

        def _parse_string_list(parent_dict, key, what):
            return _parse_string_list_with_special(parent_dict, key, what, special_filter=lambda x: False)[0]

        def _parse_channels(parent_dict):
            return _parse_string_list(parent_dict, 'channels', 'channel name')

        def _parse_packages(parent_dict):
            (deps, pip_dicts) = _parse_string_list_with_special(parent_dict, 'packages', 'package name',
                                                                lambda x: isinstance(x, dict) and ('pip' in x))
            for dep in deps:
                parsed = conda_api.parse_spec(dep)
                if parsed is None:
                    problems.append("%s: invalid package specification: %s" % (project_file.filename, dep))

            # note that multiple "pip:" dicts are allowed
            pip_deps = []
            for pip_dict in pip_dicts:
                pip_list = _parse_string_list(pip_dict, 'pip', 'pip package name')
                pip_deps.extend(pip_list)

            for dep in pip_deps:
                parsed = pip_api.parse_spec(dep)
                if parsed is None:
                    problems.append("%s: invalid pip package specifier: %s" % (project_file.filename, dep))

            return (deps, pip_deps)

        self.env_specs = dict()
        (shared_deps, shared_pip_deps) = _parse_packages(project_file.root)
        shared_channels = _parse_channels(project_file.root)
        env_specs = project_file.get_value('env_specs', default={})
        if isinstance(env_specs, dict):
            for (name, attrs) in env_specs.items():
                if name.strip() == '':
                    problems.append("Environment spec name cannot be empty string, found: '{}' as name".format(name))
                    continue
                description = attrs.get('description', None)
                if description is not None and not is_string(description):
                    problems.append("{}: 'description' field of environment {} must be a string".format(
                        project_file.filename, name))
                    continue
                (deps, pip_deps) = _parse_packages(attrs)
                channels = _parse_channels(attrs)
                # ideally we would merge same-name packages here, choosing the
                # highest of the two versions or something. maybe conda will
                # do that for us anyway?
                all_deps = shared_deps + deps
                all_pip_deps = shared_pip_deps + pip_deps
                all_channels = shared_channels + channels

                self.env_specs[name] = EnvSpec(name=name,
                                               conda_packages=all_deps,
                                               pip_packages=all_pip_deps,
                                               channels=all_channels,
                                               description=description)
        else:
            problems.append(
                "%s: env_specs should be a dictionary from environment name to environment attributes, not %r" %
                (project_file.filename, env_specs))

        # We ALWAYS have an environment named 'default' which is the default,
        # even if not explicitly listed.
        if 'default' not in self.env_specs:
            self.env_specs['default'] = EnvSpec(name='default',
                                                conda_packages=shared_deps,
                                                pip_packages=shared_pip_deps,
                                                channels=shared_channels,
                                                description="Default")

        # this is only used for commands that don't specify anything
        self.default_env_spec_name = 'default'

    def _update_conda_env_requirements(self, requirements, problems, project_file):
        if problems:
            return

        env_requirement = CondaEnvRequirement(registry=self.registry, env_specs=self.env_specs)
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
                    failed = True
                    continue
                if first_command_name is None:
                    first_command_name = name

                if not isinstance(attrs, dict):
                    problems.append("%s: command name '%s' should be followed by a dictionary of attributes not %r" %
                                    (project_file.filename, name, attrs))
                    failed = True
                    continue

                if 'description' in attrs and not is_string(attrs['description']):
                    problems.append("{}: 'description' field of command {} must be a string".format(
                        project_file.filename, name))
                    failed = True

                if 'env_spec' in attrs:
                    if not is_string(attrs['env_spec']):
                        problems.append(
                            "{}: 'env_spec' field of command {} must be a string (an environment spec name)".format(
                                project_file.filename, name))
                        failed = True
                    elif attrs['env_spec'] not in self.env_specs:
                        problems.append("%s: env_spec '%s' for command '%s' does not appear in the env_specs section" %
                                        (project_file.filename, attrs['env_spec'], name))
                        failed = True

                copied_attrs = deepcopy(attrs)

                if 'env_spec' not in copied_attrs:
                    copied_attrs['env_spec'] = self.default_env_spec_name

                command_types = []
                for attr in ALL_COMMAND_TYPES:
                    if attr not in copied_attrs:
                        continue

                    # be sure we add this even if the command is broken, since it's
                    # confusing to say "does not have a command line in it" below
                    # if the issue is that the command line is broken.
                    command_types.append(attr)

                    if not is_string(copied_attrs[attr]):
                        problems.append("%s: command '%s' attribute '%s' should be a string not '%r'" %
                                        (project_file.filename, name, attr, copied_attrs[attr]))
                        failed = True

                if len(command_types) == 0:
                    problems.append("%s: command '%s' does not have a command line in it" %
                                    (project_file.filename, name))
                    failed = True

                if ('notebook' in copied_attrs or 'bokeh_app' in copied_attrs) and (len(command_types) > 1):
                    label = 'bokeh_app' if 'bokeh_app' in copied_attrs else 'notebook'
                    others = copy(command_types)
                    others.remove(label)
                    others = [("'%s'" % other) for other in others]
                    problems.append("%s: command '%s' has multiple commands in it, '%s' can't go with %s" %
                                    (project_file.filename, name, label, ", ".join(others)))
                    failed = True

                # note that once one command fails, we don't add any more
                if not failed:
                    commands[name] = ProjectCommand(name=name, attributes=copied_attrs)

        self._add_notebook_commands(commands, problems, requirements)

        if failed:
            self.commands = dict()
            self.default_command_name = None
        else:
            # if no commands and we have a meta.yaml app entry, use the meta.yaml
            if app_entry_from_meta_yaml is not None and len(commands) == 0:
                commands['default'] = ProjectCommand(name='default',
                                                     attributes=dict(conda_app_entry=app_entry_from_meta_yaml,
                                                                     auto_generated=True,
                                                                     env_spec=self.default_env_spec_name))

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
                                                                         'auto_generated': True,
                                                                         'env_spec': self.default_env_spec_name})


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

        Prefers in order: `name` field from kapsel.yml, `package:
        name:` from meta.yaml, then project directory name.
        """
        return self._updated_cache().name

    @property
    def description(self):
        """Get the project description."""
        return self._updated_cache().description

    @property
    def icon(self):
        """Get the project's icon as an absolute path or None if no icon.

        Prefers in order: `icon` field from kapsel.yml, `app:
        icon:` from meta.yaml.
        """
        return self._updated_cache().icon

    @property
    def env_specs(self):
        """Get a dictionary of environment names to CondaEnvironment instances."""
        return self._updated_cache().env_specs

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
    def default_env_spec_name(self):
        """Get the named environment to use by default.

        This will be the one named "default" if it exists, and
        otherwise the first-listed one.

        Note that each command may have its own default, so
        this should only be used in contexts with no known
        command.
        """
        return self._updated_cache().default_env_spec_name

    def default_env_spec_name_for_command(self, command):
        """Get the named environment to use by default for a given ProjectCommand.

        the command may be ``None``
        """
        if command is None:
            return self.default_env_spec_name
        else:
            assert isinstance(command, ProjectCommand)
            return command.default_env_spec_name

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

    def default_exec_info_for_environment(self, environ, extra_args=None):
        """Get the information needed to run the project's default command.

        Args:
            environ (dict): the environment
            extra_args (list of str): extra args to append to the command line
        Returns:
            a CommandExecInfo instance
        """
        command = self.default_command
        if command is None:
            return None
        else:
            return command.exec_info_for_environment(environ=environ, extra_args=extra_args)

    def command_for_name(self, command_name):
        """Get the ProjectCommand for the given command name, or None if no commands.

        Args:
           command_name (str): the command name
        Returns:
           a ProjectCommand instance or None
        """
        if command_name is None:
            command_name = self._updated_cache().default_command_name
        if command_name is None:
            return None
        assert command_name in self._updated_cache().commands
        return self._updated_cache().commands[command_name]

    def publication_info(self):
        """Get JSON-serializable information to be stored as metadata when publishing the project.

        This is a "baked" version of kapsel.yml which also
        includes any defaults or automatic configuration.

        Before calling this, check that Project.problems is empty.

        Returns:
            A dictionary containing JSON-compatible types.
        """
        json = dict()
        json['name'] = self.name
        json['description'] = self.description
        commands = dict()
        for key, command in self.commands.items():
            commands[key] = dict(description=command.description)
            if command.bokeh_app is not None:
                commands[key]['bokeh_app'] = command.bokeh_app
            if command.notebook is not None:
                commands[key]['notebook'] = command.notebook
            if command is self.default_command:
                commands[key]['default'] = True
            commands[key]['env_spec'] = command.default_env_spec_name
        json['commands'] = commands
        envs = dict()
        for key, env in self.env_specs.items():
            envs[key] = dict(packages=list(env.conda_packages),
                             channels=list(env.channels),
                             description=env.description)
        json['env_specs'] = envs
        variables = dict()
        downloads = dict()
        services = dict()
        for req in self.requirements:
            if isinstance(req, CondaEnvRequirement):
                continue
            elif isinstance(req, DownloadRequirement):
                downloads[req.env_var] = dict(title=req.title,
                                              description=req.description,
                                              encrypted=req.encrypted,
                                              url=req.url)
            elif isinstance(req, ServiceRequirement):
                services[req.env_var] = dict(title=req.title, description=req.description, type=req.service_type)
            elif isinstance(req, EnvVarRequirement):
                variables[req.env_var] = dict(title=req.title, description=req.description, encrypted=req.encrypted)
        json['downloads'] = downloads
        json['variables'] = variables
        json['services'] = services

        return json
