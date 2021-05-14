# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Project class representing a project directory."""
from __future__ import absolute_import

import contextlib
from copy import deepcopy, copy
import os
from os.path import join

from anaconda_project.env_spec import (EnvSpec, _anaconda_default_env_spec, _find_importable_spec,
                                       _find_out_of_sync_importable_spec, _empty_default_env_spec)
from anaconda_project.requirements_registry.registry import RequirementsRegistry
from anaconda_project.requirements_registry.requirement import EnvVarRequirement
from anaconda_project.requirements_registry.requirements.conda_env import CondaEnvRequirement
from anaconda_project.requirements_registry.requirements.download import DownloadRequirement
from anaconda_project.requirements_registry.requirements.service import ServiceRequirement
from anaconda_project.project_commands import (ProjectCommand, all_known_command_attributes)
from anaconda_project.project_file import ProjectFile
from anaconda_project.project_lock_file import ProjectLockFile
from anaconda_project.archiver import _list_relative_paths_for_unignored_project_files
from anaconda_project import __version__ as version
from anaconda_project.conda_manager import CondaLockSet
from anaconda_project.frontend import _null_frontend, _new_error_recorder, Frontend
from anaconda_project.yaml_file import CommentedMap

from anaconda_project.internal.py2_compat import is_string, is_list, is_dict
from anaconda_project.internal.simple_status import SimpleStatus
from anaconda_project.internal.slugify import slugify
import anaconda_project.internal.notebook_analyzer as notebook_analyzer
import anaconda_project.internal.conda_api as conda_api
import anaconda_project.internal.pip_api as pip_api
from anaconda_project.internal import plugins as plugins_api
from anaconda_project.projectignore import add_projectignore_if_none

# These strings are used in the command line options to anaconda-project,
# so changing them has back-compat consequences.
COMMAND_TYPE_CONDA_APP_ENTRY = 'conda_app_entry'
COMMAND_TYPE_SHELL = 'unix'
COMMAND_TYPE_WINDOWS = 'windows'
COMMAND_TYPE_NOTEBOOK = 'notebook'
COMMAND_TYPE_BOKEH_APP = 'bokeh_app'

ALL_COMMAND_TYPES = (COMMAND_TYPE_CONDA_APP_ENTRY, COMMAND_TYPE_SHELL, COMMAND_TYPE_WINDOWS, COMMAND_TYPE_NOTEBOOK,
                     COMMAND_TYPE_BOKEH_APP)


class ProjectProblem(object):
    """A possibly-autofixable problem with a project."""
    def __init__(self,
                 text,
                 filename=None,
                 fix_prompt=None,
                 fix_function=None,
                 no_fix_function=None,
                 only_a_suggestion=False,
                 line_number=None,
                 column_number=None):
        """Create a project problem."""
        self.text_without_filename = text
        if filename is None:
            self.text = text
        else:
            self.text = "%s: %s" % (os.path.basename(filename), text)
        self.fix_prompt = fix_prompt
        self.fix_function = fix_function
        self.no_fix_function = no_fix_function
        self.only_a_suggestion = only_a_suggestion
        self.maybe_filename = filename
        self.maybe_line_number = line_number
        self.maybe_column_number = column_number

    @property
    def can_fix(self):
        """True if the problem can be auto-fixed."""
        return self.fix_function is not None

    def fix(self, project):
        """Perform the auto-fix."""
        if self.fix_function is not None:
            return self.fix_function(project)
        else:
            return None

    def no_fix(self, project):
        """Take an action on deciding not to fix."""
        if self.no_fix_function is not None:
            return self.no_fix_function(project)
        else:
            return None


# given a list of mixed strings and ProjectProblem, make
# them all into ProjectProblem
def _make_problems_into_objects(problems):
    new_problems = []
    for p in problems:
        if isinstance(p, ProjectProblem):
            new_problems.append(p)
        else:
            new_problems.append(ProjectProblem(text=p))
    return new_problems


def _file_problem(problems, yaml_file, text, fix_prompt=None, fix_function=None):
    problems.append(
        ProjectProblem(text=text, filename=yaml_file.filename, fix_prompt=fix_prompt, fix_function=fix_function))


def _unknown_field_suggestions(project_file, problems, yaml_dict, known_fields):
    if 'user_fields' in yaml_dict.keys():
        known_fields = _add_user_fields(yaml_dict, known_fields)
    for key in yaml_dict.keys():
        if key not in known_fields:
            problems.append(
                ProjectProblem(text="Unknown field name '%s'" % (key),
                               filename=project_file.filename,
                               only_a_suggestion=True))


def _add_user_fields(yaml_dict, known_fields):
    user_fields = deepcopy(yaml_dict['user_fields'])
    user_fields.append('user_fields')
    all = [known_fields, user_fields]
    return [i for sub in all for i in sub]


def _fatal_problem(problems):
    for p in problems:
        # strings are fatal problems
        if not isinstance(p, ProjectProblem):
            return True
        # ProjectProblem instances may be fatal problems
        if not p.only_a_suggestion:
            return True
    return False


class _ConfigCache(object):
    def __init__(self, directory_path, registry, must_exist):
        self.directory_path = directory_path
        if registry is None:
            registry = RequirementsRegistry()
        self.registry = registry

        self.name = None
        self.description = ''
        self.icon = None
        self.commands = dict()
        self.default_command_name = None
        self.project_file_count = 0
        self.lock_file_count = 0
        self.env_specs = dict()
        self.lock_sets = dict()
        self.locking_globally_enabled = False
        self.default_env_spec_name = None
        self.global_base_env_spec = None
        self.must_exist = must_exist

    def update(self, project_file, lock_file):
        if project_file.change_count == self.project_file_count and \
                lock_file.change_count == self.lock_file_count:
            return

        self.project_file_count = project_file.change_count
        self.lock_file_count = lock_file.change_count

        requirements = dict()
        problems = []

        def accept_project_creation(project):
            self.must_exist = False

        project_exists = os.path.isdir(self.directory_path)
        if not project_exists:
            problems.append("Project directory '%s' does not exist." % self.directory_path)
        elif self.must_exist and not os.path.isfile(project_file.filename):
            problems.append(
                ProjectProblem(text="Project file '%s' does not exist." % os.path.basename(project_file.filename),
                               fix_prompt="Create file '%s'?" % project_file.filename,
                               fix_function=accept_project_creation))

        if project_file.corrupted:
            problems.append(
                ProjectProblem(text=("Syntax error: %s" % (project_file.corrupted_error_message)),
                               filename=project_file.filename,
                               line_number=project_file.corrupted_maybe_line,
                               column_number=project_file.corrupted_maybe_column))

        if lock_file.corrupted:
            problems.append(
                ProjectProblem(text=("Syntax error: %s" % (lock_file.corrupted_error_message)),
                               filename=lock_file.filename,
                               line_number=lock_file.corrupted_maybe_line,
                               column_number=lock_file.corrupted_maybe_column))

        if project_exists and not (project_file.corrupted or lock_file.corrupted):
            _unknown_field_suggestions(
                project_file, problems, project_file.root,
                ('name', 'description', 'icon', 'variables', 'downloads', 'services', 'env_specs', 'commands',
                 'packages', 'dependencies', 'channels', 'platforms', 'skip_imports'))

            _unknown_field_suggestions(lock_file, problems, lock_file.root, ('env_specs', 'locking_enabled'))

            self._update_name(problems, project_file)
            self._update_description(problems, project_file)
            self._update_icon(problems, project_file)
            self._update_lock_sets(problems, lock_file)
            self._update_env_specs(problems, project_file, lock_file)
            # future: we could un-hardcode this so plugins can add stuff here
            self._update_variables(requirements, problems, project_file)
            self._update_downloads(requirements, problems, project_file)
            self._update_services(requirements, problems, project_file)
            # this MUST be after we _update_variables since we may get CondaEnvRequirement
            # options in the variables section, and after _update_env_specs
            # since we use those
            self._update_conda_env_requirements(requirements, problems, project_file)

            # this MUST be after we update env reqs so we have the valid env spec names
            self._update_commands(problems, project_file, requirements)

            self._verify_command_dependencies(problems, project_file)

        self.requirements = requirements
        self.problems = _make_problems_into_objects(problems)
        self.problem_strings = list([p.text for p in self.problems if not p.only_a_suggestion])

    def _update_name(self, problems, project_file):
        # For back-compat reasons, name=null means auto-name at runtime,
        # while name field missing entirely is an error.
        default_name = os.path.basename(self.directory_path)

        if 'name' not in project_file.root:

            def set_name_field(project):
                project.project_file.set_value('name', default_name)

            problems.append(
                ProjectProblem(text="The 'name:' field is missing.",
                               filename=project_file.filename,
                               fix_prompt=("Name the project '%s'?" % default_name),
                               fix_function=set_name_field))
            # Note: we continue on here to set set the default name below,
            # just to avoid dealing with `project.name is None` elsewhere
            # in the code, but we don't save the name to the project_file.

        name = project_file.get_value('name', None)
        if name is not None:
            if not is_string(name):
                _file_problem(problems, project_file, "name: field should have a string value not %r" % name)
                name = None
            elif len(name.strip()) == 0:
                _file_problem(problems, project_file, "name: field is an empty or all-whitespace string.")
                name = None

        if name is None:
            name = default_name

        self.name = name

    def _update_description(self, problems, project_file):
        desc = project_file.get_value('description', None)
        if desc is not None and not is_string(desc):
            _file_problem(problems, project_file, "description: field should have a string value not %r" % desc)
            desc = None

        if desc is None:
            desc = ''

        self.description = desc

    def _update_icon(self, problems, project_file):
        icon = project_file.get_value('icon', None)
        if icon is not None and not is_string(icon):
            _file_problem(problems, project_file, "icon: field should have a string value not %r" % (icon))
            icon = None

        if icon is not None:
            icon = os.path.join(self.directory_path, icon)
            if not os.path.isfile(icon):
                problems.append("Icon file %s does not exist." % icon)
                icon = None

        self.icon = icon

    def _add_requirement(self, requirements, env_spec, requirement):
        # note that env_spec.name is None for the global_base_env_spec
        if env_spec.name not in requirements:
            requirements[env_spec.name] = []
        requirements[env_spec.name].append(requirement)

    def _update_requirements(self, requirements, problems, project_file, dict_name, updater):
        global_dict = project_file.get_value(dict_name)
        updater(requirements, problems, project_file, self.global_base_env_spec, global_dict)
        for env_spec in self.env_specs.values():
            env_dict = project_file.get_value(['env_specs', env_spec.name, dict_name], None)
            updater(requirements, problems, project_file, env_spec, env_dict)

    def _update_variables(self, requirements, problems, project_file):
        self._update_requirements(requirements, problems, project_file, 'variables',
                                  self._update_variables_for_env_spec)

    def _update_downloads(self, requirements, problems, project_file):
        self._update_requirements(requirements, problems, project_file, 'downloads',
                                  self._update_downloads_for_env_spec)

    def _update_services(self, requirements, problems, project_file):
        self._update_requirements(requirements, problems, project_file, 'services', self._update_services_for_env_spec)

    def _update_variables_for_env_spec(self, requirements, problems, project_file, env_spec, variables):
        def check_conda_reserved(key):
            if key in ('CONDA_DEFAULT_ENV', 'CONDA_ENV_PATH', 'CONDA_PREFIX'):
                _file_problem(problems, project_file, ("Environment variable %s is reserved for Conda's use, " +
                                                       "so it can't appear in the variables section.") % key)
                return True
            else:
                return False

        # variables: section can contain a list of var names or a dict from
        # var names to options OR default values. it can also be missing
        # entirely which is the same as empty.
        if variables is None:
            pass
        elif is_dict(variables):
            for key in variables.keys():
                if check_conda_reserved(key):
                    continue
                if key.strip() == '':
                    _file_problem(problems, project_file,
                                  "Variable name cannot be empty string, found: '{}' as name".format(key))
                    continue
                raw_options = variables[key]

                if raw_options is None:
                    options = {}
                elif is_dict(raw_options):
                    options = deepcopy(raw_options)  # so we can modify it below
                else:
                    options = dict(default=raw_options)

                assert (isinstance(options, dict))

                if EnvVarRequirement._parse_default(options, key, problems):
                    requirement = self.registry.find_requirement_by_env_var(key, options)
                    self._add_requirement(requirements, env_spec, requirement)

        elif is_list(variables):
            for item in variables:
                if is_string(item):
                    if item.strip() == '':
                        _file_problem(problems, project_file,
                                      "Variable name cannot be empty string, found: '{}' as name".format(item))
                        continue
                    if check_conda_reserved(item):
                        continue

                    requirement = self.registry.find_requirement_by_env_var(item, options=dict())
                    self._add_requirement(requirements, env_spec, requirement)
                else:
                    _file_problem(
                        problems, project_file,
                        ("variables section should contain environment variable names, {item} is not a string".format(
                            item=item)))
        else:
            _file_problem(
                problems, project_file,
                "variables section contains wrong value type {value}, should be dict or list of requirements".format(
                    value=variables))

    def _update_downloads_for_env_spec(self, requirements, problems, project_file, env_spec, downloads):
        if downloads is None:
            return

        if not is_dict(downloads):
            _file_problem(problems, project_file,
                          "'downloads:' section should be a dictionary, found {}".format(repr(downloads)))
            return

        for varname, item in downloads.items():
            if varname.strip() == '':
                _file_problem(problems, project_file,
                              "Download name cannot be empty string, found: '{}' as name".format(varname))
                continue
            download_kwargs = DownloadRequirement._parse(varname, item, problems)
            if download_kwargs is None:
                continue

            requirement = DownloadRequirement(self.registry, **download_kwargs)
            self._add_requirement(requirements, env_spec, requirement)

    def _update_services_for_env_spec(self, requirements, problems, project_file, env_spec, services):
        if services is None:
            return

        if not is_dict(services):
            _file_problem(problems, project_file,
                          ("'services:' section should be a dictionary from environment variable to " +
                           "service type, found {}").format(repr(services)))
            return

        for varname, item in services.items():
            if varname.strip() == '':
                _file_problem(problems, project_file,
                              "Service name cannot be empty string, found: '{}' as name".format(varname))
                continue

            service_kwargs = ServiceRequirement._parse(varname, item, problems)
            if service_kwargs is None:
                continue
            service_type = service_kwargs['service_type']

            if not self.registry.can_find_requirement_by_service_type(**service_kwargs):
                problems.append("Service {} has an unknown type '{}'.".format(varname, service_type))
                continue

            requirement = self.registry.find_requirement_by_service_type(**service_kwargs)
            assert isinstance(requirement, ServiceRequirement)
            assert 'type' in requirement.options
            self._add_requirement(requirements, env_spec, requirement)

    def _parse_string_list_with_special(self, problems, yaml_file, parent_dict, key, what, special_filter):
        items = parent_dict.get(key, [])
        if not is_list(items):
            _file_problem(problems, yaml_file, "%s: value should be a list of %ss, not '%r'" % (key, what, items))
            return ([], [])
        cleaned = []
        special = []
        for item in items:
            if is_string(item):
                cleaned.append(item.strip())
            elif special_filter(item):
                special.append(item)
            else:
                _file_problem(problems, yaml_file,
                              ("%s: value should be a %s (as a string) not '%r'" % (key, what, item)))
        return (cleaned, special)

    def _parse_string_list(self, problems, yaml_file, parent_dict, key, what):
        return self._parse_string_list_with_special(problems,
                                                    yaml_file,
                                                    parent_dict,
                                                    key,
                                                    what,
                                                    special_filter=lambda x: False)[0]

    def _parse_platforms(self, problems, yaml_file, parent_dict):
        platforms = self._parse_string_list(problems, yaml_file, parent_dict, 'platforms', 'platform name')
        (platforms, unknown, invalid) = conda_api.validate_platform_list(platforms)
        for u in unknown:
            problems.append(
                ProjectProblem(
                    text=("Unusual platform name '%s' may be a typo (more usual examples: linux-64, osx-64, win-64)" %
                          u),
                    filename=yaml_file.filename,
                    only_a_suggestion=True))
        for i in invalid:
            _file_problem(problems, yaml_file,
                          "Platform name '%s' is invalid (valid examples: linux-64, osx-64, win-64)" % i)
        return platforms

    def _parse_packages(self, problems, yaml_file, key, parent_dict):
        (deps, pip_dicts) = self._parse_string_list_with_special(problems, yaml_file, parent_dict, key, 'package name',
                                                                 lambda x: is_dict(x) and ('pip' in x))
        for dep in deps:
            parsed = conda_api.parse_spec(dep)
            if parsed is None:
                _file_problem(problems, yaml_file, "invalid package specification: %s" % (dep))

        # note that multiple "pip:" dicts are allowed
        pip_deps = []
        for pip_dict in pip_dicts:
            pip_list = self._parse_string_list(problems, yaml_file, pip_dict, 'pip', 'pip package name')
            pip_deps.extend(pip_list)

        for dep in pip_deps:
            parsed = pip_api.parse_spec(dep)
            if parsed is None:
                _file_problem(problems, yaml_file, "invalid pip package specifier: %s" % (dep))

        return (deps, pip_deps)

    def _update_lock_sets(self, problems, lock_file):
        self.lock_sets = dict()
        self.locking_globally_enabled = False

        enabled = lock_file.get_value(['locking_enabled'], True)
        if not isinstance(enabled, bool):
            _file_problem(problems, lock_file, "Value for locking_enabled should be true or false, found %r" % enabled)
        else:
            self.locking_globally_enabled = enabled

        lock_sets = lock_file.get_value(['env_specs'], {})
        if not is_dict(lock_sets):
            _file_problem(problems, lock_file, ("'env_specs:' section in lock file should be a dictionary from " +
                                                "env spec names to lock information, found {}").format(repr(lock_sets)))
            return

        for (name, lock_set) in lock_sets.items():
            if not is_dict(lock_set):
                _file_problem(
                    problems, lock_file,
                    "Field '%s' in env_specs in lock file should be a dictionary, found %r" % (name, lock_set))
                continue

            _unknown_field_suggestions(lock_file, problems, lock_set,
                                       ('packages', 'dependencies', 'platforms', 'locked', 'env_spec_hash'))

            enabled = lock_set.get('locked', self.locking_globally_enabled)
            if not isinstance(enabled, bool):
                _file_problem(problems, lock_file,
                              "Value for locked for env spec '%s' should be true or false, found %r" % (name, enabled))
                continue

            env_spec_hash = lock_set.get('env_spec_hash', None)
            # we deliberately don't check the hash length or format, because we might
            # want to evolve those someday, and if someone sets the hash by hand to
            # "foobar" that's fine, won't hurt anything.
            if env_spec_hash is not None and not is_string(env_spec_hash):
                _file_problem(
                    problems, lock_file,
                    "Value for env_spec_hash for env spec '%s' should be a string, found %r" % (name, env_spec_hash))
                continue

            platforms = self._parse_platforms(problems, lock_file, lock_set)

            conda_packages_by_platform = dict()
            packages_by_platform = lock_set.get('packages', {})
            if not is_dict(packages_by_platform):
                _file_problem(
                    problems, lock_file,
                    "'packages:' section in env spec '%s' in lock file should be a dictionary, found %r" %
                    (name, packages_by_platform))
                continue

            for platform in packages_by_platform.keys():
                previous_problem_count = len(problems)
                # this may set problems due to invalid package specs
                (deps, pip_deps) = self._parse_packages(problems, lock_file, platform, packages_by_platform)

                if len(problems) > previous_problem_count:
                    continue

                if len(pip_deps) > 0:
                    # we warn but don't fail on this, so if we add pip support in the future
                    # older versions of anaconda-project won't puke on it.
                    problems.append(
                        ProjectProblem(text="env spec '%s': pip dependencies are currently ignored in the lock file" %
                                       name,
                                       filename=lock_file.filename,
                                       only_a_suggestion=True))

                conda_packages_by_platform[platform] = deps

            lock_set_object = CondaLockSet(package_specs_by_platform=conda_packages_by_platform,
                                           platforms=platforms,
                                           enabled=enabled)
            lock_set_object.env_spec_hash = env_spec_hash

            self.lock_sets[name] = lock_set_object

    def _update_env_specs(self, problems, project_file, lock_file):
        def _parse_string_list(parent_dict, key, what):
            return self._parse_string_list(problems, project_file, parent_dict, key, what)

        def _parse_channels(parent_dict):
            return _parse_string_list(parent_dict, 'channels', 'channel name')

        def _parse_platforms(parent_dict):
            return self._parse_platforms(problems, project_file, parent_dict)

        def _parse_packages(parent_dict):
            # dependencies allows environment.yml-like project files. It is not
            # expected to have both dependencies and packages
            pkg_key = 'dependencies' if project_file.get_value('dependencies') else 'packages'
            return self._parse_packages(problems, project_file, pkg_key, parent_dict)

        (shared_deps, shared_pip_deps) = _parse_packages(project_file.root)
        shared_channels = _parse_channels(project_file.root)
        shared_platforms = _parse_platforms(project_file.root)

        _default_env_spec = CommentedMap([('default', CommentedMap([('packages', []), ('channels', [])]))])
        env_specs = project_file.get_value('env_specs', default=_default_env_spec)

        first_env_spec_name = None
        env_specs_is_empty = False
        env_specs_is_missing = False

        # this one isn't in the env_specs dict
        self.global_base_env_spec = EnvSpec(name=None,
                                            conda_packages=shared_deps,
                                            pip_packages=shared_pip_deps,
                                            channels=shared_channels,
                                            platforms=shared_platforms,
                                            description="Global packages and channels",
                                            inherit_from_names=(),
                                            inherit_from=())

        env_spec_attrs = dict()
        if env_specs is None:
            env_specs_is_missing = True
        elif is_dict(env_specs):
            if len(env_specs) == 0:
                env_specs_is_empty = True
            for (name, attrs) in env_specs.items():
                if name.strip() == '':
                    _file_problem(problems, project_file,
                                  "Environment spec name cannot be empty string, found: '{}' as name".format(name))
                    continue
                description = attrs.get('description', None)
                if description is not None and not is_string(description):
                    _file_problem(problems, project_file,
                                  ("'description' field of environment {} must be a string".format(name)))
                    continue

                problem_count = len(problems)
                inherit_from_names = attrs.get('inherit_from', None)
                if inherit_from_names is None:
                    inherit_from_names = []
                elif is_string(inherit_from_names):
                    inherit_from_names = [inherit_from_names.strip()]
                else:
                    inherit_from_names = _parse_string_list(attrs, 'inherit_from', 'env spec name')

                if len(problems) > problem_count:
                    # we got a new problem from the bad inherit_from
                    continue

                (deps, pip_deps) = _parse_packages(attrs)
                channels = _parse_channels(attrs)
                platforms = _parse_platforms(attrs)

                lock_set = self.lock_sets.get(name, None)
                if lock_set is None:
                    lock_set = CondaLockSet(package_specs_by_platform=dict(),
                                            platforms=[],
                                            enabled=self.locking_globally_enabled,
                                            missing=True)

                env_spec_attrs[name] = dict(name=name,
                                            conda_packages=deps,
                                            pip_packages=pip_deps,
                                            channels=channels,
                                            platforms=platforms,
                                            description=description,
                                            inherit_from_names=tuple(inherit_from_names),
                                            inherit_from=(),
                                            lock_set=lock_set)

                if first_env_spec_name is None:
                    first_env_spec_name = name

                _unknown_field_suggestions(project_file, problems, attrs,
                                           ('packages', 'dependencies', 'channels', 'platforms', 'description',
                                            'inherit_from', 'variables', 'services', 'downloads'))
        else:
            _file_problem(
                problems, project_file,
                "env_specs should be a dictionary from environment name to environment attributes, not %r" %
                (env_specs))

        self.env_specs = dict()

        def make_env_spec(name, trail):
            assert name in env_spec_attrs

            if name not in self.env_specs:
                was_cycle = False
                if name in trail:
                    _file_problem(problems, project_file,
                                  ("'inherit_from' fields create circular inheritance among these env specs: {}".format(
                                      ", ".join(sorted(trail)))))
                    was_cycle = True
                trail.append(name)

                attrs = env_spec_attrs[name]

                if not was_cycle:
                    inherit_from_names = attrs['inherit_from_names']
                    for parent in inherit_from_names:
                        if parent not in env_spec_attrs:
                            _file_problem(problems, project_file,
                                          ("name '{}' in 'inherit_from' field of env spec {} does not match " +
                                           "the name of another env spec").format(parent, attrs['name']))
                        else:
                            inherit_from = make_env_spec(parent, trail)
                            attrs['inherit_from'] = attrs['inherit_from'] + (inherit_from, )

                # All parent-less env specs get the global base spec as parent,
                # which means the global base spec is in everyone's ancestry
                if attrs['inherit_from'] == ():
                    attrs['inherit_from'] = (self.global_base_env_spec, )

                self.env_specs[name] = EnvSpec(**attrs)

            return self.env_specs[name]

        # it's important to create all the env specs when possible
        # even if they are broken (e.g. bad inherit_from), so they
        # can be edited in order to fix them

        for name in env_spec_attrs.keys():
            make_env_spec(name, [])
            assert name in self.env_specs

        # Find issues with missing platforms: lists in the project file

        missing_platforms = []
        locked_specs_count = 0
        for env_spec in self.env_specs.values():
            if env_spec.lock_set.enabled:
                locked_specs_count += 1
            if env_spec.lock_set.enabled and len(env_spec.platforms) == 0:
                missing_platforms.append(env_spec.name)

        if locked_specs_count > 0:
            default_platforms = conda_api.default_platforms_with_current()

            # If none of the env specs have platforms, assume we want to
            # add platforms: to the toplevel (spanning entire file).
            # Otherwise, suggest fixing them one-by-one.
            missing_platform_count = len(missing_platforms)
            if missing_platform_count == locked_specs_count:

                def set_global_default_platforms(project):
                    project.project_file.set_value(['platforms'], default_platforms)

                _file_problem(problems,
                              project_file,
                              "The 'platforms:' field should list platforms the project supports.",
                              fix_prompt=("Set platforms to '%s'?" % ", ".join(default_platforms)),
                              fix_function=set_global_default_platforms)
            else:
                for missing in sorted(missing_platforms):

                    def make_fix(missing):
                        def set_env_spec_platforms(project):
                            project.project_file.set_value(['env_specs', missing, 'platforms'], default_platforms)

                        return set_env_spec_platforms

                    _file_problem(problems,
                                  project_file,
                                  "Env spec %s does not have anything in its 'platforms:' field." % missing,
                                  fix_prompt=("Set platforms to '%s'?" % ", ".join(default_platforms)),
                                  fix_function=make_fix(missing))

        # Find lock-set-out-of-sync-with-env-spec issues

        for env_spec in self.env_specs.values():
            if env_spec.lock_set.disabled:
                continue

            locked_hash = env_spec.lock_set.env_spec_hash
            if locked_hash is not None and locked_hash != env_spec.logical_hash:
                text = ("Env spec '%s' has changed since the lock file was last updated "
                        "(env spec hash has changed from %s to %s)") % (env_spec.name, locked_hash,
                                                                        env_spec.logical_hash)
                problems.append(ProjectProblem(text=text, filename=lock_file.filename, only_a_suggestion=True))

            if env_spec.platforms != env_spec.lock_set.platforms:
                if len(env_spec.lock_set.platforms) == 0:
                    text = "Env spec '%s' specifies platforms '%s' but the lock file lists no platforms for it" % (
                        env_spec.name, ",".join(env_spec.platforms))
                else:
                    text = ("Env spec '%s' specifies platforms '%s' but the lock file has " +
                            "locked versions for platforms '%s'") % (env_spec.name, ",".join(
                                env_spec.platforms), ",".join(env_spec.lock_set.platforms))
                problems.append(ProjectProblem(text=text, filename=lock_file.filename, only_a_suggestion=True))

            if len(env_spec.conda_packages) > 0:
                for platform in env_spec.lock_set.platforms:
                    conda_packages = env_spec.lock_set.package_specs_for_platform(platform)
                    if len(conda_packages) == 0:
                        text = ("Lock file lists no packages for env spec '%s' on platform %s") % (env_spec.name,
                                                                                                   platform)
                        problems.append(ProjectProblem(text=text, filename=lock_file.filename, only_a_suggestion=True))
                    else:
                        # If conda ever had RPM-like "Obsoletes" then this situation _may_ happen
                        # in correct scenarios.
                        lock_set_names = set()
                        for package in conda_packages:
                            parsed = conda_api.parse_spec(package)
                            if parsed is not None:
                                lock_set_names.add(parsed.name)
                        unlocked_names = env_spec.conda_package_names_set - lock_set_names
                        if len(unlocked_names) > 0:
                            text = "Lock file is missing %s packages for env spec %s on %s (%s)" % (
                                len(unlocked_names), env_spec.name, platform, ",".join(sorted(list(unlocked_names))))
                            problems.append(
                                ProjectProblem(text=text, filename=lock_file.filename, only_a_suggestion=True))

        # Look for lock sets that don't go with an env spec
        for name in self.lock_sets.keys():
            if name not in self.env_specs:
                text = ("Lock file lists env spec '%s' which is not in %s") % (name, project_file.basename)
                problems.append(ProjectProblem(text=text, filename=lock_file.filename, only_a_suggestion=True))

        # Look for environment.yml, requirements.txt that are out of sync

        (importable_spec, importable_filename) = _find_out_of_sync_importable_spec(self.env_specs.values(),
                                                                                   self.directory_path)
        if importable_spec is not None:
            skip_spec_import = project_file.get_value(['skip_imports', 'environment'])
            if skip_spec_import == importable_spec.logical_hash:
                importable_spec = None

        if importable_spec is not None:
            old = self.env_specs.get(importable_spec.name)

        # this is a pretty bad hack, but if we injected "notebook"
        # or "bokeh" deps to make a notebook/bokeh command work,
        # we will end up out-of-sync for that reason
        # alone. environment.yml seems to typically not have
        # "notebook" in it because the environment.yml is used for
        # the kernel but not Jupyter itself.
        # We then end up in a problem loop where we complain about
        # missing notebook dep, add it, then complain about environment.yml
        # out of sync, and `anaconda-project init` in a directory with a .ipynb
        # and an environment.yml doesn't result in a valid project.
        if importable_spec is not None and old is not None and \
                importable_spec.diff_only_removes_notebook_or_bokeh(old):
            importable_spec = None

        if importable_spec is not None:
            if old is None:
                text = "Environment spec '%s' from %s is not in %s." % (importable_spec.name, importable_filename,
                                                                        os.path.basename(project_file.filename))
                prompt = "Add env spec %s to %s?" % (importable_spec.name, os.path.basename(project_file.filename))
            else:
                text = "Environment spec '%s' from %s is out of sync with %s. Diff:\n%s" % (
                    importable_spec.name, importable_filename, os.path.basename(
                        project_file.filename), importable_spec.diff_from(old))
                prompt = "Overwrite env spec %s with the changes from %s?" % (importable_spec.name, importable_filename)

            def overwrite_env_spec_from_importable(project):
                project.project_file.set_value(['env_specs', importable_spec.name], importable_spec.to_json())

            def remember_no_import_importable(project):
                project.project_file.set_value(['skip_imports', 'environment'], importable_spec.logical_hash)

            # we don't set the filename here because it isn't really an error in the
            # file, it ends up reading strangely.
            problems.append(
                ProjectProblem(text=text,
                               fix_prompt=prompt,
                               fix_function=overwrite_env_spec_from_importable,
                               no_fix_function=remember_no_import_importable))
        elif env_specs_is_empty or env_specs_is_missing:
            # we do NOT want to add this problem if we merely
            # failed to parse individual env specs; it must be
            # safe to overwrite the env_specs key, so it has to
            # be empty or missing entirely. Also, we do NOT want
            # to add this if we are going to ask about environment.yml
            # import, above.
            def add_default_env_spec(project):
                default_spec = _anaconda_default_env_spec(self.global_base_env_spec)
                project.project_file.set_value(['env_specs', default_spec.name], default_spec.to_json())

            # This section should now be inaccessible
            # since env_spec will be added at runtime if missing


# this is only used for commands that don't specify anything
# (when/if we require all commands to specify, then remove this.)

        if 'default' in self.env_specs:
            self.default_env_spec_name = 'default'
        else:
            self.default_env_spec_name = first_env_spec_name

    def _update_conda_env_requirements(self, requirements, problems, project_file):
        if _fatal_problem(problems):
            return

        if self.has_bootstrap_env_spec():
            requirement = CondaEnvRequirement(registry=self.registry,
                                              env_specs=self.env_specs,
                                              env_var='BOOTSTRAP_ENV_PREFIX')
            self._add_requirement(requirements, self.global_base_env_spec, requirement)

        requirement = CondaEnvRequirement(registry=self.registry, env_specs=self.env_specs)
        self._add_requirement(requirements, self.global_base_env_spec, requirement)

    def _update_commands(self, problems, project_file, requirements):
        failed = False

        first_command_name = None
        commands = dict()
        commands_section = project_file.get_value('commands', None)

        plugins = plugins_api.get_plugins('command_run')
        all_known_command_attributes_extended = (all_known_command_attributes + tuple(plugins.keys()))

        if commands_section is not None and not is_dict(commands_section):
            _file_problem(
                problems, project_file,
                "'commands:' section should be a dictionary from command names to attributes, not %r" %
                (commands_section))
            failed = True
        elif commands_section is not None:
            for (name, attrs) in commands_section.items():
                if name.strip() == '':
                    _file_problem(problems, project_file,
                                  "Command variable name cannot be empty string, found: '{}' as name".format(name))
                    failed = True
                    continue
                if first_command_name is None:
                    first_command_name = name

                if not is_dict(attrs):
                    _file_problem(
                        problems, project_file,
                        "command name '%s' should be followed by a dictionary of attributes not %r" % (name, attrs))
                    failed = True
                    continue

                _unknown_field_suggestions(project_file, problems, attrs, all_known_command_attributes_extended)

                if 'description' in attrs and not is_string(attrs['description']):
                    _file_problem(problems, project_file,
                                  "'description' field of command {} must be a string".format(name))
                    failed = True

                if 'supports_http_options' in attrs and not isinstance(attrs['supports_http_options'], bool):
                    _file_problem(problems, project_file,
                                  ("'supports_http_options' field of command {} must be a boolean".format(name)))
                    failed = True

                if 'env_spec' in attrs:
                    if not is_string(attrs['env_spec']):
                        _file_problem(
                            problems, project_file,
                            "'env_spec' field of command {} must be a string (an environment spec name)".format(name))
                        failed = True
                    elif attrs['env_spec'] not in self.env_specs:
                        _file_problem(
                            problems, project_file,
                            "env_spec '%s' for command '%s' does not appear in the env_specs section" %
                            (attrs['env_spec'], name))
                        failed = True

                if 'registers_fusion_function' in attrs and not isinstance(attrs['registers_fusion_function'], bool):
                    _file_problem(problems, project_file,
                                  ("'registers_fusion_function' field of command {} must be a boolean".format(name)))
                    failed = True

                copied_attrs = deepcopy(attrs)

                if 'env_spec' not in copied_attrs:
                    copied_attrs['env_spec'] = self.default_env_spec_name

                command_types = []
                ProjectCommandClass = ProjectCommand
                for attr in ALL_COMMAND_TYPES + tuple(plugins.keys()):
                    if attr not in copied_attrs:
                        continue
                    else:
                        if attr in plugins:
                            ProjectCommandClass = plugins[attr]

                    # be sure we add this even if the command is broken, since it's
                    # confusing to say "does not have a command line in it" below
                    # if the issue is that the command line is broken.
                    command_types.append(attr)

                    if not is_string(copied_attrs[attr]):
                        _file_problem(
                            problems, project_file, "command '%s' attribute '%s' should be a string not '%r'" %
                            (name, attr, copied_attrs[attr]))
                        failed = True

                if len(command_types) == 0:
                    _file_problem(problems, project_file, "command '%s' does not have a command line in it" % (name))
                    failed = True

                if ('notebook' in copied_attrs or 'bokeh_app' in copied_attrs) and (len(command_types) > 1):
                    label = 'bokeh_app' if 'bokeh_app' in copied_attrs else 'notebook'
                    others = copy(command_types)
                    others.remove(label)
                    others = [("'%s'" % other) for other in others]
                    _file_problem(
                        problems, project_file, "command '%s' has multiple commands in it, '%s' can't go with %s" %
                        (name, label, ", ".join(others)))
                    failed = True

                # note that once one command fails, we don't add any more
                if not failed:
                    commands[name] = ProjectCommandClass(name=name, attributes=copied_attrs)

        self._verify_notebook_commands(commands, problems, requirements, project_file)

        if failed:
            self.commands = dict()
            self.default_command_name = None
        else:
            self.commands = commands

        if 'default' in self.commands:
            self.default_command_name = 'default'
        else:
            # 'default' is always mapped to the first-listed if none is named 'default'
            # note: this may be None
            self.default_command_name = first_command_name

    def _verify_notebook_commands(self, commands, problems, requirements, project_file):
        skipped_notebooks = project_file.get_value(['skip_imports', 'notebooks'])
        if skipped_notebooks is not None:
            if skipped_notebooks is True:
                # skip ALL notebooks forever
                return
            elif not is_list(skipped_notebooks):
                _file_problem(
                    problems, project_file,
                    "'skip_imports: notebooks:' value should be a list, found {}".format(repr(skipped_notebooks)))
                return
        else:
            skipped_notebooks = []

        recorder = _new_error_recorder(_null_frontend())
        flat_requirements = []
        for reqs in requirements.values():
            flat_requirements.extend(reqs)
        files = _list_relative_paths_for_unignored_project_files(self.directory_path,
                                                                 frontend=recorder,
                                                                 requirements=flat_requirements)
        if files is None:
            problems.extend(recorder.pop_errors())
            assert problems != []
            return

        # chop out hidden directories. The
        # main reason to ignore dot directories is that they
        # might contain packages or git cache data or other
        # such gunk, not because we really care about
        # ".foo.ipynb" per se.
        files = [f for f in files if not f[0] == '.']

        # always use unix file separator
        files = [f.replace("\\", "/") for f in files]

        # use a deterministic order because the first command is the default
        files = sorted(files)

        def need_to_import_notebook(relative_name):
            for command in commands.values():
                if command.notebook == relative_name:
                    return False

            if relative_name in skipped_notebooks:
                return False

            return True

        def make_add_notebook_func(relative_name, env_spec_name):
            def add_notebook(project):
                errors = []
                extras = notebook_analyzer.extras(os.path.join(self.directory_path, relative_name), errors)
                # TODO this is broken, need to refactor so fix functions can return
                # errors and probably also log progress indication.
                assert [] == errors
                assert extras is not None

                command_dict = {'notebook': relative_name, 'env_spec': env_spec_name}
                command_dict.update(extras)
                project.project_file.set_value(['commands', relative_name], command_dict)

            return add_notebook

        def make_no_add_notebook_func(relative_name):
            def no_add_notebook(project):
                skipped_notebooks = project.project_file.get_value(['skip_imports', 'notebooks'], default=[])
                skipped_notebooks.append(relative_name)
                project.project_file.set_value(['skip_imports', 'notebooks'], skipped_notebooks)

            return no_add_notebook

        need_to_import = []
        for relative_name in files:
            if relative_name.endswith('.ipynb'):
                if need_to_import_notebook(relative_name):
                    need_to_import.append(relative_name)

        # make tests deterministic
        need_to_import.sort()

        if len(need_to_import) == 1:
            relative_name = need_to_import[0]
            problem = ProjectProblem(text="No command runs notebook %s" % (relative_name),
                                     filename=project_file.filename,
                                     fix_prompt="Create a command in %s for %s?" %
                                     (os.path.basename(project_file.filename), relative_name),
                                     fix_function=make_add_notebook_func(relative_name, self.default_env_spec_name),
                                     no_fix_function=make_no_add_notebook_func(relative_name),
                                     only_a_suggestion=True)
            problems.append(problem)
        elif len(need_to_import) > 1:
            add_funcs = [
                make_add_notebook_func(relative_name, self.default_env_spec_name) for relative_name in need_to_import
            ]
            no_add_funcs = [make_no_add_notebook_func(relative_name) for relative_name in need_to_import]

            def add_all(project):
                for f in add_funcs:
                    f(project)

            def no_add_all(project):
                for f in no_add_funcs:
                    f(project)

            problem = ProjectProblem(text="No commands run notebooks %s" % (", ".join(need_to_import)),
                                     filename=project_file.filename,
                                     fix_prompt="Create commands in %s for all missing notebooks?" %
                                     (os.path.basename(project_file.filename)),
                                     fix_function=add_all,
                                     no_fix_function=no_add_all,
                                     only_a_suggestion=True)
            problems.append(problem)

    def _verify_command_dependencies(self, problems, project_file):
        for command in self.commands.values():
            if command.default_env_spec_name not in self.env_specs:
                # The missing environment will already have been flagged as a problem
                # in _update_commands, so we can just return
                return
            env_spec = self.env_specs[command.default_env_spec_name]
            missing = command.missing_packages(env_spec)
            if len(missing) > 0:

                def add_packages_to_env_spec(project):
                    env_dict = project.project_file.get_value(['env_specs', env_spec.name])
                    assert env_dict is not None
                    packages = env_dict.get('packages', [])
                    for m in missing:
                        # m would already be in there if we fixed the same env spec
                        # twice because two commands used it, for example.
                        if m not in packages:
                            packages.append(m)
                    project.project_file.set_value(['env_specs', env_spec.name, 'packages'], packages)

                problem = ProjectProblem(
                    text=("Command %s uses env spec %s which does not have the packages: %s" %
                          (command.name, env_spec.name, ", ".join(missing))),
                    filename=project_file.filename,
                    fix_prompt=("Add %s to env spec %s in %s?" %
                                (", ".join(missing), env_spec.name, os.path.basename(project_file.filename))),
                    fix_function=add_packages_to_env_spec,
                    only_a_suggestion=True)
                problems.append(problem)

    def has_bootstrap_env_spec(self):
        """Return True if bootstrap-env is in env_specs, False otherwise."""
        return 'bootstrap-env' in self.env_specs


class Project(object):
    """Represents the information we've inferred about a project.

    The Project class encapsulates information from the project
    file, and also anything else we've guessed by snooping around in
    the project directory or global user configuration.
    """
    def __init__(self, directory_path, plugin_registry=None, frontend=None, must_exist=False, scan_parents=True):
        """Construct a Project with the given directory and plugin registry.

        Args:
            directory_path (str): path to the project directory
            plugin_registry (RequirementsRegistry): where to look up Requirement and Provider instances,
                                                    None for default
            frontend (Frontend): the UX using this Project instance
            must_exist (bool): if True, the absence of a project file is a problem
            scan_parents (bool): if True search for anaconda-project.yml file in parent directories
                                 If one is found change the directory_path to its location.
        """
        self._directory_path = os.path.realpath(directory_path).rstrip(os.sep)

        def load_default_specs():
            (importable_spec, importable_filename) = _find_importable_spec(directory_path)
            if importable_spec is not None:
                return [importable_spec]
            else:
                return [_empty_default_env_spec(shared_base_spec=None)]

        self._project_file = ProjectFile.load_for_directory(directory_path,
                                                            default_env_specs_func=load_default_specs,
                                                            scan_parents=scan_parents)
        self._directory_path = self._project_file.project_dir
        add_projectignore_if_none(self._directory_path)

        self._lock_file = ProjectLockFile.load_for_directory(self._directory_path)
        self._directory_basename = os.path.basename(self._directory_path)
        self._config_cache = _ConfigCache(self._directory_path, plugin_registry, must_exist)
        if frontend is None:
            frontend = _null_frontend()
        assert isinstance(frontend, Frontend)
        self._frontends = [frontend]

    def _updated_cache(self):
        self._config_cache.update(self._project_file, self._lock_file)
        return self._config_cache

    @property
    def directory_path(self):
        """Get path to the project directory."""
        return self._directory_path

    @property
    def frontend(self):
        """Return the current UX frontend."""
        return self._frontends[-1]

    @property
    def project_file(self):
        """Get the ``ProjectFile`` for this project."""
        return self._project_file

    @property
    def lock_file(self):
        """Get the ``ProjectLockFile`` for this project."""
        return self._lock_file

    @property
    def plugin_registry(self):
        """Get the ``RequirementsRegistry`` for this project."""
        return self._config_cache.registry

    @property
    def union_of_requirements_for_all_envs(self):
        """Required items for ALL envs (list of ``Requirement`` instances)."""
        combined = []
        for env_spec in self.env_specs.values():
            # This is obviously pointless for the time being since
            # all env specs have the same requirements, but we want
            # to change that in the future so simulating it here.
            combined.extend(self.requirements(env_spec.name))
        return combined

    def requirements(self, env_spec_name):
        """Required items in order to run this project (list of ``Requirement`` instances)."""
        if env_spec_name is None:
            env_spec_name = self.default_env_spec_name
        requirements = self._updated_cache().requirements

        def get_reqs(env_spec):
            return requirements.get(env_spec.name, [])

        def req_key(req):
            assert isinstance(req, EnvVarRequirement)
            return req.env_var

        env_spec = self.env_specs.get(env_spec_name)

        if env_spec is None:
            # this happens if there was a problem parsing the project
            return []
        else:
            # this should probably really return the tuple instead
            # of list, but we'd have to fix up tests accordingly
            return list(env_spec._get_inherited_with_getter(get_reqs, key_func=req_key))

    def service_requirements(self, env_spec_name):
        """All requirements that are ServiceRequirement instances."""
        return self.find_requirements(env_spec_name, klass=ServiceRequirement)

    def download_requirements(self, env_spec_name):
        """All requirements that are DownloadRequirement instances."""
        return self.find_requirements(env_spec_name, klass=DownloadRequirement)

    def all_variable_requirements(self, env_spec_name):
        """All requirements that have an associated environment variable.

        Note: this will include services, downloads, and even CondaEnvRequirement.
        """
        return self.find_requirements(env_spec_name, klass=EnvVarRequirement)

    def plain_variable_requirements(self, env_spec_name):
        """All 'plain' variables (that aren't services, downloads, or a Conda environment for example).

        Use the ``all_variable_requirements`` property to get every variable.
        """
        return [req for req in self.all_variable_requirements(env_spec_name) if req.__class__ is EnvVarRequirement]

    def push_null_frontend(self):
        """Push a no-op frontend overriding the currently-active one.

        This is used to disable output temporarily.
        """
        self._frontends.append(_null_frontend())

    def pop_null_frontend(self):
        """Pop the no-op frontend."""
        assert len(self._frontends) > 1
        self._frontends = self._frontends[:-1]

    @contextlib.contextmanager
    def null_frontend(self):
        """Create a context with the frontend disabled."""
        self.push_null_frontend()
        try:
            yield
        finally:
            self.pop_null_frontend()

    def find_requirements(self, env_spec_name, env_var=None, klass=None):
        """Find requirements that match the given env var and class.

        If env_var and klass are both provided, BOTH must match.

        Args:
           env_spec_name (str): name of env spec to find requirements of
           env_var (str): if not None, filter requirements that have this env_var
           klass (class): if not None, filter requirements that are an instance of this class

        Returns:
           list of matching requirements (may be empty)
        """
        found = []
        for req in self.requirements(env_spec_name):
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
        return self._updated_cache().problem_strings

    @property
    def problem_objects(self):
        """List of ProjectProblem instances describing problems with the project configuration."""
        return [problem for problem in self._updated_cache().problems if not problem.only_a_suggestion]

    @property
    def fixable_problems(self):
        """List of ProjectProblem that have associated fix prompts."""
        return [p for p in self.problem_objects if p.can_fix and not p.only_a_suggestion]

    @property
    def unfixable_problems(self):
        """List of ProjectProblem that cannot be fixed."""
        return [p for p in self.problem_objects if not p.can_fix and not p.only_a_suggestion]

    def problems_status(self, description=None):
        """Get a ``Status`` describing project problems, or ``None`` if no problems."""
        if len(self.problems) > 0:
            errors = []
            for problem in self.problems:
                errors.append(problem)
            if description is None:
                description = "Unable to load the project."
            return SimpleStatus(success=False, description=description, errors=errors)
        else:
            return None

    @property
    def suggestions(self):
        """List of strings describing suggested changes to the project configuration."""
        return [problem.text for problem in self.suggestion_objects]

    @property
    def suggestion_objects(self):
        """List of ProjectProblem instances describing suggested changes to the project configuration."""
        return [problem for problem in self._updated_cache().problems if problem.only_a_suggestion]

    def fix_problems_and_suggestions(self):
        """Fix fixable problems and suggestions."""
        # the idea of this loop is that by fixing a problem we may
        # create a new one, for example we add a notebook command
        # and then the env spec needs to depend on "notebook".
        # However, we have no real way to detect an infinite
        # ping-pong of mutually-causing problems, so we cap
        # the iterations at an arbitrary number.
        iterations = 5
        while iterations > 0:
            fixed_a_thing = False
            for problem in self._updated_cache().problems:
                if problem.can_fix:
                    problem.fix(self)
                    fixed_a_thing = True
            if fixed_a_thing:
                self.use_changes_without_saving()
            iterations -= 1

    @property
    def name(self):
        """Get the project's human-readable name.

        Prefers in order: `name` field from anaconda-project.yml, `package:
        name:` from meta.yaml, then project directory name.
        """
        return self._updated_cache().name

    @property
    def url_friendly_name(self):
        """Get the project's url-friendly name."""
        return slugify(self.name)

    @property
    def description(self):
        """Get the project description."""
        return self._updated_cache().description

    @property
    def icon(self):
        """Get the project's icon as an absolute path or None if no icon.

        Prefers in order: `icon` field from anaconda-project.yml, `app:
        icon:` from meta.yaml.
        """
        return self._updated_cache().icon

    @property
    def env_specs(self):
        """Get a dictionary of environment names to CondaEnvironment instances."""
        return self._updated_cache().env_specs

    @property
    def locking_globally_enabled(self):
        """Get whether locking is enabled by default for lock sets that don't specify."""
        return self._updated_cache().locking_globally_enabled

    @property
    def global_base_env_spec(self):
        """Get the env spec representing global packages, channels, and platforms sections.

        This env spec has no name (its name is None) and can't be used directly
        to create environments, but every other env spec inherits from it.
        """
        return self._updated_cache().global_base_env_spec

    def all_variables(self, env_spec_name):
        """Get a list of strings with the variables names from ``all_variable_requirements``."""
        return [r.env_var for r in self.all_variable_requirements(env_spec_name)]

    def plain_variables(self, env_spec_name):
        """Get a list of strings with the variables names from ``plain_variable_requirements``."""
        return [r.env_var for r in self.plain_variable_requirements(env_spec_name)]

    def services(self, env_spec_name):
        """Get a list of strings with the variable names for the project services requirements."""
        return [r.env_var for r in self.service_requirements(env_spec_name)]

    def downloads(self, env_spec_name):
        """Get a list of strings with the variable names for the project download requirements."""
        return [r.env_var for r in self.download_requirements(env_spec_name)]

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
        commands = self._updated_cache().commands
        has_default = 'default' in commands

        if (command_name == 'default') and (not has_default):
            command_name = self._updated_cache().default_command_name
        if command_name is None:
            command_name = self._updated_cache().default_command_name
        if command_name is None:
            return None
        if command_name in self._updated_cache().commands:
            return self._updated_cache().commands[command_name]
        else:
            return None

    def publication_info(self):
        """Get JSON-serializable information to be stored as metadata when publishing the project.

        This is a "baked" version of anaconda-project.yml which also
        includes any defaults or automatic configuration.

        Before calling this, check that Project.problems is empty.

        Returns:
            A dictionary containing JSON-compatible types.
        """
        json = dict()
        json['name'] = self.name
        # the recipient will have to validate this; including it here
        # mostly because we might eventually allow the anaconda-project.yml to
        # manually provide it.
        json['url_friendly_name'] = self.url_friendly_name
        json['description'] = self.description
        json['anaconda_project_version'] = version
        commands = dict()
        for key, command in self.commands.items():
            commands[key] = dict(description=command.description)
            if command.bokeh_app is not None:
                commands[key]['bokeh_app'] = command.bokeh_app
            if command.notebook is not None:
                commands[key]['notebook'] = command.notebook
            if command.windows_cmd_commandline is not None:
                commands[key]['windows'] = command.windows_cmd_commandline
            if command.unix_shell_commandline is not None:
                commands[key]['unix'] = command.unix_shell_commandline
            if command is self.default_command:
                commands[key]['default'] = True
            commands[key]['env_spec'] = command.default_env_spec_name
            commands[key]['supports_http_options'] = command.supports_http_options
            commands[key].update(command.extras)
        json['commands'] = commands
        envs = dict()
        for key, env in self.env_specs.items():
            envs[key] = dict(packages=list(env.conda_packages),
                             channels=list(env.channels),
                             description=env.description,
                             locked=env.lock_set.enabled,
                             platforms=list(env.platforms))

            variables = dict()
            downloads = dict()
            services = dict()
            for req in self.requirements(key):
                if isinstance(req, CondaEnvRequirement):
                    continue

                if isinstance(req, EnvVarRequirement):
                    data = dict(title=req.title, description=req.description, encrypted=req.encrypted)

                    default = req.default_as_string
                    if default is not None:
                        data['default'] = default

                    if isinstance(req, DownloadRequirement):
                        data['url'] = req.url
                        downloads[req.env_var] = data
                    elif isinstance(req, ServiceRequirement):
                        data['type'] = req.service_type
                        services[req.env_var] = data
                    elif isinstance(req, EnvVarRequirement):
                        variables[req.env_var] = data

            envs[key]['downloads'] = downloads
            envs[key]['variables'] = variables
            envs[key]['services'] = services

        json['env_specs'] = envs

        return json

    def load(self):
        """Revert the project configuration by reloading config from disk.

        Discards all unsaved changes.

        This isn't needed when creating a Project, just if you want to
        revert to disk. We automatically load on Project creation.
        """
        self.project_file.load()
        self.lock_file.load()

    def save(self):
        """Save any modified project configuration.

        Does nothing for config files that are not dirty.
        """
        self.project_file.save()
        self.lock_file.save()

    def use_changes_without_saving(self):
        """Rebuild project state from in-memory changes.

        This causes the Project instance to reload from
        the in-memory (but possibly unsaved) state of
        the project file and lock file.
        """
        self.project_file.use_changes_without_saving()
        self.lock_file.use_changes_without_saving()

    @property
    def bootstrap_env_prefix(self):
        """Fullpath to bootstrap environment prefix."""
        return join(self._directory_path, 'envs', 'bootstrap-env')

    def is_running_in_bootstrap_env(self):
        """Return True if anaconda-project is running inside a project bootstrap env False otherwise."""
        return os.environ['CONDA_PREFIX'] == self.bootstrap_env_prefix

    def has_bootstrap_env_spec(self):
        """Return True if bootstrap-env is in env_specs, False otherwise."""
        return self._config_cache.has_bootstrap_env_spec()
