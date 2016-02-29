"""Conda-env-related requirements."""
from __future__ import absolute_import, print_function

from project.plugins.requirement import EnvVarRequirement, RequirementStatus
import project.internal.conda_api as conda_api
from project.internal.directory_contains import directory_contains_subdirectory


class CondaEnvRequirement(EnvVarRequirement):
    """A requirement for CONDA_DEFAULT_ENV (or another specified env var) to point to a conda env."""

    def __init__(self, registry, env_var="CONDA_DEFAULT_ENV", options=None, conda_package_specs=None):
        """Extend superclass to default to CONDA_DEFAULT_ENV and set conda_packages.

        Args:
            registry (PluginRegistry): plugin registry
            env_var (str): env var name
            options (dict): options from the config
            conda_package_specs (list of str): list of package spec strings (as in ``conda.resolve.MatchSpec``)
        """
        super(CondaEnvRequirement, self).__init__(registry=registry, env_var=env_var, options=options)
        if conda_package_specs is None:
            conda_package_specs = list()
        self.conda_package_specs = conda_package_specs

    @property
    def title(self):
        """Override superclass to provide our title."""
        if self.must_be_project_scoped:
            base = "A Conda environment inside the project directory"
        else:
            base = "A Conda environment"
        if len(self.conda_package_specs) > 0:
            return base + " containing packages: " + ", ".join(self.conda_package_specs)
        else:
            return base

    def _find_providers(self):
        if self.must_be_project_scoped:
            provider = self.registry.find_provider_by_class_name('ProjectScopedCondaEnvProvider')
            assert provider is not None
            return [provider]
        else:
            return self.registry.find_providers_by_env_var(self, self.env_var)

    def _why_not_provided(self, environ):
        name_or_prefix = self._get_value_of_env_var(environ)
        if name_or_prefix is None:
            return "A Conda environment hasn't been activated for this project (%s is unset)." % (self.env_var)

        try:
            prefix = conda_api.resolve_env_to_prefix(name_or_prefix)
        except conda_api.CondaError as e:
            return "Conda didn't understand environment name or prefix %s from %s: %s" % (name_or_prefix, self.env_var,
                                                                                          str(e))

        if prefix is None:
            return "Conda environment %s='%s' does not exist yet." % (self.env_var, name_or_prefix)

        if self.must_be_project_scoped:
            if 'PROJECT_DIR' not in environ:
                return "PROJECT_DIR isn't set, so cannot find or create a dedicated Conda environment."
            # "inside the project directory" is a kind of rough
            # proxy for "environment dedicated to this project,"
            # we could define "project-scoped" in some more
            # elaborate way I suppose, but this seems like a fine
            # starting point.
            project_dir = environ['PROJECT_DIR']
            if not directory_contains_subdirectory(project_dir, prefix):
                return ("The current environment (in %s) isn't inside the project directory (%s).") % (prefix,
                                                                                                       project_dir)

        if len(self.conda_package_specs) == 0:
            return None

        try:
            installed = conda_api.installed(prefix)
        except conda_api.CondaError as e:
            return "Conda failed while listing installed packages in %s: %s" % (prefix, str(e))

        missing = set()

        for name in self.conda_package_names_set:
            if name not in installed:
                missing.add(name)

        if len(missing) > 0:
            sorted = list(missing)
            sorted.sort()
            return "Conda environment is missing packages: %s" % (", ".join(sorted))

        return None

    def check_status(self, environ):
        """Override superclass to get our status."""
        why_not_provided = self._why_not_provided(environ)
        providers = self._find_providers()
        if why_not_provided is None:
            return RequirementStatus(
                self,
                has_been_provided=True,
                status_description=("Using Conda environment %s" % self._get_value_of_env_var(environ)),
                possible_providers=providers)
        else:
            return RequirementStatus(self,
                                     has_been_provided=False,
                                     status_description=why_not_provided,
                                     possible_providers=providers)

    @property
    def must_be_project_scoped(self):
        """Get whether environment must be dedicated to this project."""
        return self.options.get('project_scoped', True)

    @property
    def conda_package_names_set(self):
        """conda package names that the environment must contain, as a set."""
        names = set()
        for spec in self.conda_package_specs:
            pieces = spec.split(' ', 3)
            name = pieces[0]
            # vspecs = []
            # if len(pieces) > 1:
            #     vspecs = pieces[1].split('|')
            # build = None
            # if len(pieces) > 2:
            #     build = pieces[2]
            names.add(name)
        return names
