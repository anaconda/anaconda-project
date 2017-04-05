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

from anaconda_project.env_spec import (EnvSpec, _anaconda_default_env_spec, _find_importable_spec,
                                       _find_out_of_sync_importable_spec)
from anaconda_project.plugins.registry import PluginRegistry
from anaconda_project.plugins.requirement import EnvVarRequirement
from anaconda_project.plugins.requirements.conda_env import CondaEnvRequirement
from anaconda_project.plugins.requirements.download import DownloadRequirement
from anaconda_project.plugins.requirements.service import ServiceRequirement
from anaconda_project.project_commands import (ProjectCommand, all_known_command_attributes)
from anaconda_project.project_file import ProjectFile
from anaconda_project.archiver import _list_relative_paths_for_unignored_project_files
from anaconda_project.version import version

from anaconda_project.internal.py2_compat import is_string
from anaconda_project.internal.simple_status import SimpleStatus
from anaconda_project.internal.slugify import slugify
import anaconda_project.internal.notebook_analyzer as notebook_analyzer
import anaconda_project.internal.conda_api as conda_api
import anaconda_project.internal.pip_api as pip_api

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


def _file_problem(problems, yaml_file, text):
    problems.append(ProjectProblem(text=text, filename=yaml_file.filename))


def _unknown_field_suggestions(project_file, problems, yaml_dict, known_fields):
    for key in yaml_dict.keys():
        if key not in known_fields:
            problems.append(ProjectProblem(text="Unknown field name '%s'" % (key),
                                           filename=project_file.filename,
                                           only_a_suggestion=True))


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
        self.env_specs = dict()
        self.default_env_spec_name = None
        self.global_base_env_spec = None

    def update(self, project_file):
        if project_file.change_count == self.project_file_count:
            return

        self.project_file_count = project_file.change_count

        requirements = []
        problems = []

        project_exists = os.path.isdir(self.directory_path)
        if not project_exists:
            problems.append("Project directory '%s' does not exist." % self.directory_path)

        if project_file.corrupted:
            problems.append(ProjectProblem(text=("Syntax error: %s" % (project_file.corrupted_error_message)),
                                           filename=project_file.filename,
                                           line_number=project_file.corrupted_maybe_line,
                                           column_number=project_file.corrupted_maybe_column))

        if project_exists and not project_file.corrupted:
            _unknown_field_suggestions(project_file, problems, project_file.root,
                                       ('name', 'description', 'icon', 'variables', 'downloads', 'services',
                                        'env_specs', 'commands', 'packages', 'channels', 'skip_imports'))

            self._update_name(problems, project_file)
            self._update_description(problems, project_file)
            self._update_icon(problems, project_file)
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

            problems.append(ProjectProblem(text="The 'name:' field is missing.",
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

    def _update_variables(self, requirements, problems, project_file):
        variables = project_file.get_value("variables")

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
        elif isinstance(variables, dict):
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
                        _file_problem(problems, project_file,
                                      "Variable name cannot be empty string, found: '{}' as name".format(item))
                        continue
                    if check_conda_reserved(item):
                        continue
                    requirement = self.registry.find_requirement_by_env_var(item, options=dict())
                    requirements.append(requirement)
                else:
                    _file_problem(
                        problems,
                        project_file,
                        ("variables section should contain environment variable names, {item} is not a string".format(
                            item=item)))
        else:
            _file_problem(
                problems,
                project_file,
                "variables section contains wrong value type {value}, should be dict or list of requirements".format(
                    value=variables))

    def _update_downloads(self, requirements, problems, project_file):
        downloads = project_file.get_value('downloads')

        if downloads is None:
            return

        if not isinstance(downloads, dict):
            _file_problem(problems, project_file,
                          "'downloads:' section should be a dictionary, found {}".format(repr(downloads)))
            return

        for varname, item in downloads.items():
            if varname.strip() == '':
                _file_problem(problems, project_file,
                              "Download name cannot be empty string, found: '{}' as name".format(varname))
                continue
            DownloadRequirement._parse(self.registry, varname, item, problems, requirements)

    def _update_services(self, requirements, problems, project_file):
        services = project_file.get_value('services')

        if services is None:
            return

        if not isinstance(services, dict):
            _file_problem(problems, project_file,
                          ("'services:' section should be a dictionary from environment variable to " +
                           "service type, found {}").format(repr(services)))
            return

        for varname, item in services.items():
            if varname.strip() == '':
                _file_problem(problems, project_file,
                              "Service name cannot be empty string, found: '{}' as name".format(varname))
                continue
            ServiceRequirement._parse(self.registry, varname, item, problems, requirements)

    def _update_env_specs(self, problems, project_file):
        def _parse_string_list_with_special(parent_dict, key, what, special_filter):
            items = parent_dict.get(key, [])
            if not isinstance(items, (list, tuple)):
                _file_problem(problems, project_file,
                              "%s: value should be a list of %ss, not '%r'" % (key, what, items))
                return ([], [])
            cleaned = []
            special = []
            for item in items:
                if is_string(item):
                    cleaned.append(item.strip())
                elif special_filter(item):
                    special.append(item)
                else:
                    _file_problem(problems, project_file,
                                  ("%s: value should be a %s (as a string) not '%r'" % (key, what, item)))
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
                    _file_problem(problems, project_file, "invalid package specification: %s" % (dep))

            # note that multiple "pip:" dicts are allowed
            pip_deps = []
            for pip_dict in pip_dicts:
                pip_list = _parse_string_list(pip_dict, 'pip', 'pip package name')
                pip_deps.extend(pip_list)

            for dep in pip_deps:
                parsed = pip_api.parse_spec(dep)
                if parsed is None:
                    _file_problem(problems, project_file, "invalid pip package specifier: %s" % (dep))

            return (deps, pip_deps)

        (shared_deps, shared_pip_deps) = _parse_packages(project_file.root)
        shared_channels = _parse_channels(project_file.root)
        env_specs = project_file.get_value('env_specs', default={})
        first_env_spec_name = None
        env_specs_is_empty_or_missing = False  # this should be iff it's an empty dict or absent entirely

        # this one isn't in the env_specs dict
        self.global_base_env_spec = EnvSpec(name=None,
                                            conda_packages=shared_deps,
                                            pip_packages=shared_pip_deps,
                                            channels=shared_channels,
                                            description="Global packages and channels",
                                            inherit_from_names=(),
                                            inherit_from=())

        env_spec_attrs = dict()
        if isinstance(env_specs, dict):
            if len(env_specs) == 0:
                env_specs_is_empty_or_missing = True
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

                env_spec_attrs[name] = dict(name=name,
                                            conda_packages=deps,
                                            pip_packages=pip_deps,
                                            channels=channels,
                                            description=description,
                                            inherit_from_names=tuple(inherit_from_names),
                                            inherit_from=())

                if first_env_spec_name is None:
                    first_env_spec_name = name

                _unknown_field_suggestions(project_file, problems, attrs, ('packages', 'channels', 'description',
                                                                           'inherit_from'))
        else:
            _file_problem(problems, project_file,
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

        for name in env_spec_attrs.keys():
            make_env_spec(name, [])
            assert name in self.env_specs

        # it's important to create all the env specs when possible
        # even if they are broken (e.g. bad inherit_from), so they
        # can be edited in order to fix them

        (importable_spec, importable_filename) = _find_out_of_sync_importable_spec(self.env_specs.values(),
                                                                                   self.directory_path)

        if importable_spec is not None:
            skip_spec_import = project_file.get_value(['skip_imports', 'environment'])
            if skip_spec_import == importable_spec.channels_and_packages_hash:
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
                    importable_spec.name, importable_filename, os.path.basename(project_file.filename),
                    importable_spec.diff_from(old))
                prompt = "Overwrite env spec %s with the changes from %s?" % (importable_spec.name, importable_filename)

            def overwrite_env_spec_from_importable(project):
                project.project_file.set_value(['env_specs', importable_spec.name], importable_spec.to_json())

            def remember_no_import_importable(project):
                project.project_file.set_value(['skip_imports', 'environment'],
                                               importable_spec.channels_and_packages_hash)

            # we don't set the filename here because it isn't really an error in the
            # file, it ends up reading strangely.
            problems.append(ProjectProblem(text=text,
                                           fix_prompt=prompt,
                                           fix_function=overwrite_env_spec_from_importable,
                                           no_fix_function=remember_no_import_importable))
        elif env_specs_is_empty_or_missing:
            # we do NOT want to add this problem if we merely
            # failed to parse individual env specs; it must be
            # safe to overwrite the env_specs key, so it has to
            # be empty or missing entirely. Also, we do NOT want
            # to add this if we are going to ask about environment.yml
            # import, above.
            def add_default_env_spec(project):
                default_spec = _anaconda_default_env_spec(self.global_base_env_spec)
                project.project_file.set_value(['env_specs', default_spec.name], default_spec.to_json())

            problems.append(ProjectProblem(text="The env_specs section is empty.",
                                           filename=project_file.filename,
                                           fix_prompt=("Add an environment spec to %s?" % os.path.basename(
                                               project_file.filename)),
                                           fix_function=add_default_env_spec))

        # this is only used for commands that don't specify anything
        # (when/if we require all commands to specify, then remove this.)
        if 'default' in self.env_specs:
            self.default_env_spec_name = 'default'
        else:
            self.default_env_spec_name = first_env_spec_name

    def _update_conda_env_requirements(self, requirements, problems, project_file):
        if _fatal_problem(problems):
            return

        env_requirement = CondaEnvRequirement(registry=self.registry, env_specs=self.env_specs)
        requirements.append(env_requirement)

    def _update_commands(self, problems, project_file, requirements):
        failed = False

        first_command_name = None
        commands = dict()
        commands_section = project_file.get_value('commands', None)
        if commands_section is not None and not isinstance(commands_section, dict):
            _file_problem(problems, project_file,
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

                if not isinstance(attrs, dict):
                    _file_problem(problems, project_file,
                                  "command name '%s' should be followed by a dictionary of attributes not %r" %
                                  (name, attrs))
                    failed = True
                    continue

                _unknown_field_suggestions(project_file, problems, attrs, all_known_command_attributes)

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
                        _file_problem(problems, project_file,
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
                for attr in ALL_COMMAND_TYPES:
                    if attr not in copied_attrs:
                        continue

                    # be sure we add this even if the command is broken, since it's
                    # confusing to say "does not have a command line in it" below
                    # if the issue is that the command line is broken.
                    command_types.append(attr)

                    if not is_string(copied_attrs[attr]):
                        _file_problem(problems, project_file, "command '%s' attribute '%s' should be a string not '%r'"
                                      % (name, attr, copied_attrs[attr]))
                        failed = True

                if len(command_types) == 0:
                    _file_problem(problems, project_file, "command '%s' does not have a command line in it" % (name))
                    failed = True

                if ('notebook' in copied_attrs or 'bokeh_app' in copied_attrs) and (len(command_types) > 1):
                    label = 'bokeh_app' if 'bokeh_app' in copied_attrs else 'notebook'
                    others = copy(command_types)
                    others.remove(label)
                    others = [("'%s'" % other) for other in others]
                    _file_problem(problems, project_file,
                                  "command '%s' has multiple commands in it, '%s' can't go with %s" %
                                  (name, label, ", ".join(others)))
                    failed = True

                # note that once one command fails, we don't add any more
                if not failed:
                    commands[name] = ProjectCommand(name=name, attributes=copied_attrs)

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
            elif not isinstance(skipped_notebooks, list):
                _file_problem(
                    problems, project_file,
                    "'skip_imports: notebooks:' value should be a list, found {}".format(repr(skipped_notebooks)))
                return
        else:
            skipped_notebooks = []

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
            problem = ProjectProblem(
                text="No command runs notebook %s" % (relative_name),
                filename=project_file.filename,
                fix_prompt="Create a command in %s for %s?" % (os.path.basename(project_file.filename), relative_name),
                fix_function=make_add_notebook_func(relative_name, self.default_env_spec_name),
                no_fix_function=make_no_add_notebook_func(relative_name),
                only_a_suggestion=True)
            problems.append(problem)
        elif len(need_to_import) > 1:
            add_funcs = [make_add_notebook_func(relative_name, self.default_env_spec_name)
                         for relative_name in need_to_import]
            no_add_funcs = [make_no_add_notebook_func(relative_name) for relative_name in need_to_import]

            def add_all(project):
                for f in add_funcs:
                    f(project)

            def no_add_all(project):
                for f in no_add_funcs:
                    f(project)

            problem = ProjectProblem(text="No commands run notebooks %s" % (", ".join(need_to_import)),
                                     filename=project_file.filename,
                                     fix_prompt="Create commands in %s for all missing notebooks?" % (os.path.basename(
                                         project_file.filename)),
                                     fix_function=add_all,
                                     no_fix_function=no_add_all,
                                     only_a_suggestion=True)
            problems.append(problem)

    def _verify_command_dependencies(self, problems, project_file):
        for command in self.commands.values():
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

                problem = ProjectProblem(text=("Command %s uses env spec %s which does not have the packages: %s" % (
                    command.name, env_spec.name, ", ".join(missing))),
                                         filename=project_file.filename,
                                         fix_prompt=("Add %s to env spec %s in %s?" % (", ".join(
                                             missing), env_spec.name, os.path.basename(project_file.filename))),
                                         fix_function=add_packages_to_env_spec,
                                         only_a_suggestion=True)
                problems.append(problem)


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

        def load_default_specs():
            (importable_spec, importable_filename) = _find_importable_spec(directory_path)
            if importable_spec is not None:
                return [importable_spec]
            else:
                return [_anaconda_default_env_spec(shared_base_spec=None)]

        self._project_file = ProjectFile.load_for_directory(directory_path, default_env_specs_func=load_default_specs)
        self._directory_basename = os.path.basename(self._directory_path)
        self._config_cache = _ConfigCache(self._directory_path, plugin_registry)

    def _updated_cache(self):
        self._config_cache.update(self._project_file)
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
        return self._updated_cache().problem_strings

    @property
    def problem_objects(self):
        """List of ProjectProblem instances describing problems with the project configuration."""
        return [problem for problem in self._updated_cache().problems if not problem.only_a_suggestion]

    @property
    def fixable_problems(self):
        """List of ProjectProblem that have associated fix prompts."""
        return [p for p in self.problem_objects if p.can_fix and not p.only_a_suggestion]

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
                self.project_file.use_changes_without_saving()
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
    def global_base_env_spec(self):
        """Get the env spec representing global packages and channels sections.

        This env spec has no name (its name is None) and can't be used directly
        to create environments, but every other env spec inherits from it.
        """
        return self._updated_cache().global_base_env_spec

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
                             description=env.description)
        json['env_specs'] = envs
        variables = dict()
        downloads = dict()
        services = dict()
        for req in self.requirements:
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

        json['downloads'] = downloads
        json['variables'] = variables
        json['services'] = services

        return json
