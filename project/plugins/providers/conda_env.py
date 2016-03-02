"""Conda environment providers."""
from __future__ import absolute_import, print_function

import os

import project.internal.conda_api as conda_api
from project.plugins.provider import Provider


class ProjectScopedCondaEnvProvider(Provider):
    """Provides a project-scoped Conda environment."""

    def read_config(self, context):
        """Override superclass to return our config."""
        config = dict()
        section = self.config_section(context.requirement)
        config['autocreate'] = context.local_state_file.get_value(section + ['autocreate'], default=True)
        return config

    def set_config_values_as_strings(self, context, values):
        """Override superclass to set our config values."""
        section = self.config_section(context.requirement)
        autocreate_string = values.get('autocreate', "True")
        autocreate = autocreate_string == "True"
        context.local_state_file.set_value(section + ['autocreate'], autocreate)

    def config_html(self, context, status):
        """Override superclass to provide our config html."""
        if status.has_been_provided:
            return None
        else:
            return """
<form>
  <label><input name="autocreate" type="checkbox" value="True"/>Autocreate an environment
    in PROJECT_DIR/.envs/default  <input name="autocreate" type="hidden" value="False"/></label>
</form>
"""

    def provide(self, requirement, context):
        """Override superclass to activating a project-scoped environment (creating it if needed)."""
        if not context.status.analysis.config['autocreate']:
            context.append_log("Not trying to create a Conda environment.")
            return

        # TODO: we are ignoring any version or build specs for the package names.
        # the hard part about this is that the conda command line which we use
        # to create the environment has a different syntax from meta.yaml which we
        # use to create the required package specs, so we can't just pass the meta.yaml
        # syntax to the conda command line.
        command_line_packages = set(['python']).union(requirement.conda_package_names_set)

        # future: we could use environment.yml if present to create the default env
        prefix = os.path.join(context.environ['PROJECT_DIR'], ".envs", "default")
        try:
            conda_api.create(prefix=prefix, pkgs=list(command_line_packages))
        except conda_api.CondaEnvExistsError:
            pass
        except conda_api.CondaError as e:
            context.append_error(str(e))
            prefix = None

        if prefix is not None:
            # now install any missing packages (should only happen if env didn't exist,
            # otherwise we passed the needed packages to create)
            installed = conda_api.installed(prefix)
            missing = set()
            for name in command_line_packages:
                if name not in installed:
                    missing.add(name)
            if len(missing) > 0:
                try:
                    conda_api.install(prefix=prefix, pkgs=list(missing))
                except conda_api.CondaError as e:
                    context.append_error("Failed to install missing packages: " + ", ".join(missing))
                    context.append_error(str(e))
                    prefix = None

        if prefix is not None:
            context.environ[requirement.env_var] = prefix
            path = context.environ.get("PATH", "")
            context.environ["PATH"] = conda_api.set_conda_env_in_path(path, prefix)
            # Some stuff can only be done when a shell is launched:
            #  - we can't set PS1 because it shouldn't be exported.
            #  - we can't run conda activate scripts because they are sourced.
            # We can do these in the output of our activate command, but not here.
