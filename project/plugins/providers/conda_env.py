"""Conda environment providers."""
from __future__ import absolute_import, print_function

import os

import project.internal.conda_api as conda_api
from project.plugins.provider import EnvVarProvider


class CondaEnvProvider(EnvVarProvider):
    """Provides a Conda environment."""

    def read_config(self, context):
        """Override superclass to add a choice to create a project-scoped environment."""
        config = super(CondaEnvProvider, self).read_config(context)

        assert 'PROJECT_DIR' in context.environ
        project_dir = context.environ['PROJECT_DIR']

        assert 'source' in config

        if config['source'] == 'environ':
            # we have a setting (off by default) for whether to
            # use the conda env we were in prior to
            # preparation. By default we always use a
            # project-scoped one.
            if not context.local_state_file.get_value('inherit_environment', default=False):
                config['source'] = 'project'
        elif config['source'] == 'unset':
            # if nothing is selected, default to project mode
            # because we don't have a radio button in the UI for
            # "do nothing" right now
            config['source'] = 'project'
        elif config['source'] == 'default':
            # we don't support a default here for CONDA_ENV_PATH
            # because it would need a hardcoded path
            config['source'] = 'project'

        # be sure we don't get confused by alternate ways to spell the path
        if 'value' in config:
            config['value'] = os.path.normpath(config['value'])

        # set env_name
        config['env_name'] = context.requirement.default_environment_name

        if 'value' in config:
            for env in context.requirement.environments.values():
                if config['value'] == env.path(project_dir):
                    config['env_name'] = env.name
                    if config['source'] == 'variables':
                        config['source'] = 'project'
        elif config['source'] == 'project':
            env = context.requirement.environments.get(config['env_name'])
            config['value'] = env.path(project_dir)

        # print("read_config " + repr(config))

        return config

    def set_config_values_as_strings(self, context, values):
        """Override superclass to support 'project' source option."""
        super(CondaEnvProvider, self).set_config_values_as_strings(context, values)
        # print("Setting values: " + repr(values))
        if 'source' in values:
            if values['source'] == 'project':
                project_dir = context.environ['PROJECT_DIR']
                name = values['env_name']
                for env in context.requirement.environments.values():
                    if env.name == name:
                        prefix = env.path(project_dir)
                        context.local_state_file.set_value(['variables', context.requirement.env_var], prefix)
            elif values['source'] == 'environ':
                # if user chose 'environ' explicitly, we need to set the inherit_environment flag
                context.local_state_file.set_value('inherit_environment', True)

    def config_html(self, context, status):
        """Override superclass to provide the extra option to create one of our configured environments."""
        # print("config_html with config " + repr(status.analysis.config))
        environ_value = context.environ.get(context.requirement.env_var, None)
        project_dir = context.environ['PROJECT_DIR']
        options_html = ('<div><label><input type="radio" name="source" ' +
                        'value="project"/>Use project-specific environment: <select name="env_name">')
        environ_value_is_project_specific = False
        for env in context.requirement.environments.values():
            html = ('<option value="%s">%s</option>\n' % (env.name, env.name))
            if env.path(project_dir) == environ_value:
                environ_value_is_project_specific = True
            options_html = options_html + html

        options_html = options_html + "</select></div>\n"

        if environ_value is not None and not environ_value_is_project_specific:
            options_html = options_html + """
            <div>
              <label><input type="radio" name="source" value="environ"/>Keep value '{from_environ}'</label>
            </div>
            """.format(from_environ=environ_value)

        options_html = options_html + """
            <div>
              <label><input type="radio" name="source" value="variables"/>Use this %s instead:
                     <input type="text" name="value"/></label>
            </div>
            """ % (context.requirement.env_var)

        return """
<form>
  %s
</form>
""" % (options_html)

    def provide(self, requirement, context):
        """Override superclass to create or update our environment."""
        assert 'PATH' in context.environ

        # we want to ignore the existing env var unless inherit_environment=True
        # read_config should have already arranged this
        if not context.local_state_file.get_value('inherit_environment', default=False):
            assert context.status.analysis.config['source'] != 'environ'

        # set the env var (but not PATH, etc. to fully activate, that's done below)
        super(CondaEnvProvider, self).provide(requirement, context)

        project_dir = context.environ['PROJECT_DIR']

        if context.status.analysis.config['source'] == 'environ':
            prefix = context.environ.get(requirement.env_var, None)
        else:
            prefix = None

        if prefix is None:
            # use the default environment
            env_name = context.status.analysis.config.get('env_name', requirement.default_environment_name)
            env = requirement.environments.get(env_name)
            assert env is not None
            prefix = env.path(project_dir)

        assert prefix is not None

        env_spec = None
        for env in requirement.environments.values():
            if env.path(project_dir) == prefix:
                env_spec = env
                break

        # TODO if not creating a named env, we could use the
        # shared dependencies, but for now we leave it alone
        if env_spec is not None:
            command_line_packages = set(['python']).union(set(env_spec.dependencies))

            if os.path.isdir(os.path.join(prefix, 'conda-meta')):
                # Update the environment with possibly-missing packages
                installed = conda_api.installed(prefix)
                missing = set()
                for name in env_spec.conda_package_names_set:
                    if name not in installed:
                        missing.add(name)
                if len(missing) > 0:
                    try:
                        # TODO we are ignoring package versions here
                        # https://github.com/Anaconda-Server/anaconda-project/issues/77
                        conda_api.install(prefix=prefix, pkgs=list(missing), channels=env_spec.channels)
                    except conda_api.CondaError as e:
                        context.append_error("Failed to install missing packages: " + ", ".join(missing))
                        context.append_error(str(e))
                        return
            else:
                # Create environment from scratch
                try:
                    conda_api.create(prefix=prefix, pkgs=list(command_line_packages), channels=env_spec.channels)
                except conda_api.CondaError as e:
                    context.append_error(str(e))
                    return

        context.environ[requirement.env_var] = prefix
        # future: if the prefix is a (globally, not project-scoped) named environment
        # this should be set to the name
        context.environ["CONDA_DEFAULT_ENV"] = prefix
        path = context.environ.get("PATH", "")
        context.environ["PATH"] = conda_api.set_conda_env_in_path(path, prefix)
        # Some stuff can only be done when a shell is launched:
        #  - we can't set PS1 because it shouldn't be exported.
        #  - we can't run conda activate scripts because they are sourced.
        # We can do these in the output of our activate command, but not here.
