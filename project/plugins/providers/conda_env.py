"""Conda environment providers."""
from __future__ import print_function

import os

import project.internal.conda_api as conda_api
from project.plugins.provider import Provider


class ProjectScopedCondaEnvProvider(Provider):
    """Provides a project-scoped Conda environment."""

    @property
    def title(self):
        """Override superclass to provide our title."""
        return "Conda environment inside the project directory"

    def read_config(self, local_state, requirement):
        """Override superclass to return empty config."""
        return dict()

    def provide(self, requirement, context):
        """Override superclass to activating a project-scoped environment (creating it if needed)."""
        # future: we could use environment.yml if present to create the default env
        prefix = os.path.join(context.environ['PROJECT_DIR'], ".envs", "default")
        try:
            conda_api.create(prefix=prefix, pkgs=['python'])
        except conda_api.CondaEnvExistsError:
            pass
        except conda_api.CondaError as e:
            context.append_error(str(e))
            prefix = None

        if prefix is not None:
            # future: we need to "activate" the environment by setting
            # PATH and all the things the regular conda env activate sets,
            # not only the CONDA_DEFAULT_ENV var.
            context.environ[requirement.env_var] = prefix
