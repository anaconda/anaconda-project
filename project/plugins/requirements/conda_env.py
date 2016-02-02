"""Conda-env-related requirements."""
from __future__ import absolute_import, print_function

from project.plugins.requirement import EnvVarRequirement
import project.internal.conda_api as conda_api
from project.internal.directory_contains import directory_contains_subdirectory


class CondaEnvRequirement(EnvVarRequirement):
    """A requirement for CONDA_DEFAULT_ENV (or another specified env var) to point to a conda env."""

    def __init__(self, env_var="CONDA_DEFAULT_ENV", options=None):
        """Extend superclass to default to CONDA_DEFAULT_ENV."""
        super(CondaEnvRequirement, self).__init__(env_var=env_var, options=options)

    def find_providers(self, registry):
        """Override superclass to find a provider of conda environments."""
        if self.must_be_project_scoped:
            provider = registry.find_by_class_name('ProjectScopedCondaEnvProvider')
            assert provider is not None
            return [provider]
        else:
            return registry.find_by_env_var(self, self.env_var)

    def why_not_provided(self, environ):
        """Extend superclass to check that the Conda env exists and looks plausible."""
        why_not = super(CondaEnvRequirement, self).why_not_provided(environ)
        if why_not is not None:
            return why_not
        name_or_prefix = environ[self.env_var]

        prefix = conda_api.resolve_env_to_prefix(name_or_prefix)
        if prefix is None:
            return "Conda environment %s='%s' does not seem to exist." % (self.env_var, name_or_prefix)

        if self.must_be_project_scoped:
            if 'PROJECT_DIR' not in environ:
                return "PROJECT_DIR not set, so cannot find a project-scoped Conda environment."
            # "inside the project directory" is a kind of rough
            # proxy for "environment dedicated to this project,"
            # we could define "project-scoped" in some more
            # elaborate way I suppose, but this seems like a fine
            # starting point.
            project_dir = environ['PROJECT_DIR']
            if not directory_contains_subdirectory(project_dir, prefix):
                return "Conda environment at '%s' is not inside project at '%s'" % (prefix, project_dir)

        return None

    @property
    def must_be_project_scoped(self):
        """Get whether environment must be dedicated to this project."""
        return self.options.get('project_scoped', True)
