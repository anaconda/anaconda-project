"""Project class representing a project directory."""
from __future__ import absolute_import

import os

from distutils.spawn import find_executable

from project.project_file import ProjectFile
from project.conda_meta_file import CondaMetaFile
from project.plugins.registry import PluginRegistry
from project.plugins.requirements.conda_env import CondaEnvRequirement


class _ConfigCache(object):
    def __init__(self, registry):
        if registry is None:
            registry = PluginRegistry()
        self.registry = registry

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
            # future: we could un-hardcode this so plugins can add stuff here
            self._update_runtime(requirements, problems, project_file)
            # this MUST be after we _update_runtime since we may get CondaEnvRequirement
            # options in the runtime section
            self._update_conda_env_requirements(requirements, problems, project_file, conda_meta_file)
            self._update_launch_argv(problems, project_file, conda_meta_file)

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

    def _update_conda_env_requirements(self, requirements, problems, project_file, conda_meta_file):
        packages = []

        def load_from(yaml_file):
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
                    else:
                        packages.append(item)

        load_from(conda_meta_file)
        load_from(project_file)

        # for the getter on Project
        self.requirements_run = list(packages)

        if problems or not packages:
            return

        # use existing CondaEnvRequirement if it was created via env var
        env_requirement = None
        for r in requirements:
            if isinstance(r, CondaEnvRequirement):
                env_requirement = r

        if env_requirement is None:
            env_requirement = CondaEnvRequirement(registry=self.registry, conda_package_specs=packages)
            requirements.append(env_requirement)
        else:
            env_requirement.conda_package_specs.extend(packages)

    def _update_launch_argv(self, problems, project_file, conda_meta_file):
        def load_from(yaml_file):
            app_entry = yaml_file.app_entry
            if app_entry is not None and not isinstance(app_entry, str):
                problems.append("%s: app: entry: should be a string not '%r'" % (yaml_file.filename, app_entry))
                return None
            else:
                return app_entry

        app_entry = load_from(project_file)
        if app_entry is None:
            app_entry = load_from(conda_meta_file)

        if app_entry is None:
            self.launch_argv = None
        else:
            # conda.misc uses plain split and not shlex or
            # anything like that, we need to match its
            # interpretation
            parsed = app_entry.split()
            self.launch_argv = tuple(parsed)


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
    def requirements_run(self):
        """Get the combined "requirements: run" lists from both project.yml and meta.yaml.

        The returned list is a list of strings in conda "match
        specification" format (see
        http://conda.pydata.org/docs/spec.html#build-version-spec
        and the ``conda.resolve.MatchSpec`` class).
        """
        return self._updated_cache().requirements_run

    @property
    def launch_argv(self):
        """Get the argv to run the project or None.

        This argv is not "ready to use" because it has to be
        resolved against a set of environment variables and a
        conda environment. The ``prepare()`` API can do this for
        you.

        Returns:
            iterable of strings or None if no launch command configured
        """
        return self._updated_cache().launch_argv

    def launch_argv_for_environment(self, environ):
        """Get a usable argv with the executable path made absolute and prefix substituted.

        Args:
            environ (dict): the environment
        Returns:
            argv as list of strings
        """
        # see conda.misc::launch for what we're copying
        for name in ('CONDA_DEFAULT_ENV', 'PATH', 'PROJECT_DIR'):
            if name not in environ:
                raise ValueError("To get a runnable command for the app, %s must be set." % (name))

        prefix = None  # fetch this lazily only if needed
        args = []
        for arg in self.launch_argv:
            if '${PREFIX}' in arg:
                if prefix is None:
                    import project.internal.conda_api as conda_api
                    prefix = conda_api.resolve_env_to_prefix(environ['CONDA_DEFAULT_ENV'])
                    arg = arg.replace('${PREFIX}', prefix)
            args.append(arg)

        # always look in the project directory. This is a little
        # odd because we don't add PROJECT_DIR to PATH for child
        # processes - maybe we should?
        path = os.pathsep.join([environ['PROJECT_DIR'], environ['PATH']])
        executable = find_executable(args[0], path)
        if executable is not None:
            # if the executable is in cwd, for some reason find_executable does not
            # return the full path to it, just a relative path.
            args[0] = os.path.abspath(executable)
        # if we didn't find args[0] on the path, we leave it as-is
        # and wait for it to fail when we later try to run it.
        return args
