# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""All-in-one public API module.

It's OK to use anything in anaconda_project as well, but anything
with an underscore prefix or inside ``anaconda_project.internal``
is considered private.

In this file, we try to export the interesting high-level
operations in one place so they are easy to find and import.  It
is a redundant but hopefully convenient wrapper around the entire
API.

"""
from __future__ import absolute_import

# This file shouldn't import anaconda_project.internal, because it's
# supposed to wrap other public API, not be the only public API.
from anaconda_project import prepare, project, provide, project_ops


class AnacondaProject(object):
    """Class containing a consolidated public API for convenience."""

    def __init__(self):
        """Construct an API instance."""
        pass

    def load_project(self, directory_path):
        """Load a project from the given directory.

        If there's a problem, the returned Project instance will
        have a non-empty ``problems`` attribute. So check
        ``project.problems`` when you get the result.
        ``project.problems`` can change anytime changes are made
        to a project; code must always be ready for a project to
        have some problems.

        Args:
            directory_path (str): path to the project directory

        Returns:
            a Project instance

        """
        return project.Project(directory_path=directory_path)

    def create_project(self, directory_path, make_directory=False, name=None, icon=None):
        """Create a project skeleton in the given directory.

        Returns a Project instance even if creation fails or the directory
        doesn't exist, but in those cases the ``problems`` attribute
        of the Project will describe the problem.

        If the project.yml already exists, this simply loads it.

        This will not prepare the project (create environments, etc.),
        use the separate prepare calls if you want to do that.

        Args:
            directory_path (str): directory to contain project.yml
            make_directory (bool): True to create the directory if it doesn't exist
            name (str): Name of the new project or None to leave unset (uses directory name)
            icon (str): Icon for the new project or None to leave unset (uses no icon)

        Returns:
            a Project instance
        """
        return project_ops.create(directory_path=directory_path, make_directory=make_directory, name=name, icon=icon)

    def prepare_project_locally(self,
                                project,
                                environ,
                                conda_environment_name=None,
                                command_name=None,
                                extra_command_args=None):
        """Prepare a project to run one of its commands.

        "Locally" means a machine where development will go on,
        contrasted with say a production deployment.

        This method takes any needed actions such as creating
        environments or starting services, without asking the user
        for permission.

        This method returns a result object. The result object has
        a ``failed`` property.  If the result is failed, the
        ``errors`` property has the errors.  If the result is not
        failed, the ``command_exec_info`` property has the stuff
        you need to run the project's default command, and the
        ``environ`` property has the updated environment. The
        passed-in ``environ`` is not modified in-place.

        You can update your original environment with
        ``result.update_environ()`` if you like, but it's probably
        a bad idea to modify ``os.environ`` in that way because
        the calling app won't want to have the project
        environment.

        The ``environ`` should usually be kept between
        preparations, starting out as ``os.environ`` but then
        being modified by the user.

        If the project has a non-empty ``problems`` attribute,
        this function returns the project problems inside a failed
        result. So ``project.problems`` does not need to be checked in
        advance.

        Args:
            project (Project): from the ``load_project`` method
            environ (dict): os.environ or the previously-prepared environ; not modified in-place
            conda_environment_name (str): the environment spec name to require, or None for default
            command_name (str): which named command to choose from the project, None for default
            extra_command_args (list): extra args to include in the returned command argv

        Returns:
            a ``PrepareResult`` instance, which has a ``failed`` flag

        """
        return prepare.prepare_without_interaction(project=project,
                                                   environ=environ,
                                                   mode=provide.PROVIDE_MODE_DEVELOPMENT,
                                                   conda_environment_name=conda_environment_name,
                                                   command_name=command_name,
                                                   extra_command_args=extra_command_args)

    def prepare_project_production(self,
                                   project,
                                   environ,
                                   conda_environment_name=None,
                                   command_name=None,
                                   extra_command_args=None):
        """Prepare a project to run one of its commands.

        "Production" means some sort of production deployment, so
        services have to be 'real' and not some kind of
        local/temporary throwaway. We won't just start things up
        willy-nilly.

        We still do some things automatically in production
        though, such as creating environments.

        This method does not interact with the user; it "does the
        right thing" without asking.

        See ``prepare_project_locally()`` for additional details
        that also apply to this method.

        Args:
            project (Project): from the ``load_project`` method
            environ (dict): os.environ or the previously-prepared environ; not modified in-place
            conda_environment_name (str): the environment spec name to require, or None for default
            command_name (str): which named command to choose from the project, None for default
            extra_command_args (list): extra args to include in the returned command argv

        Returns:
            a ``PrepareResult`` instance, which has a ``failed`` flag

        """
        return prepare.prepare_without_interaction(project=project,
                                                   environ=environ,
                                                   mode=provide.PROVIDE_MODE_PRODUCTION,
                                                   conda_environment_name=conda_environment_name,
                                                   command_name=command_name,
                                                   extra_command_args=extra_command_args)

    def prepare_project_check(self,
                              project,
                              environ,
                              conda_environment_name=None,
                              command_name=None,
                              extra_command_args=None):
        """Prepare a project to run one of its commands.

        This version only checks the status of the project's
        requirements, but doesn't take any actions; it won't
        create files or start processes or anything like that.  If
        it returns a successful result, the project can be
        prepared without taking any further action.

        See ``prepare_project_locally()`` for additional details
        that also apply to this method.

        Args:
            project (Project): from the ``load_project`` method
            environ (dict): os.environ or the previously-prepared environ; not modified in-place
            conda_environment_name (str): the environment spec name to require, or None for default
            command_name (str): which named command to choose from the project, None for default
            extra_command_args (list): extra args to include in the returned command argv

        Returns:
            a ``PrepareResult`` instance, which has a ``failed`` flag

        """
        return prepare.prepare_without_interaction(project=project,
                                                   environ=environ,
                                                   mode=provide.PROVIDE_MODE_CHECK,
                                                   conda_environment_name=conda_environment_name,
                                                   command_name=command_name,
                                                   extra_command_args=extra_command_args)

    def prepare_project_browser(self,
                                project,
                                environ,
                                conda_environment_name=None,
                                command_name=None,
                                extra_command_args=None,
                                io_loop=None,
                                show_url=None):
        """Prepare a project to run one of its commands.

        This version uses a browser-based UI to allow the user to
        see and choose how to meet project requirements.

        See ``prepare_project_locally()`` for additional details
        that also apply to this method.

        Args:
            project (Project): from the ``load_project`` method
            environ (dict): os.environ or the previously-prepared environ; not modified in-place
            conda_environment_name (str): the environment spec name to require, or None for default
            command_name (str): which named command to choose from the project, None for default
            extra_command_args (list): extra args to include in the returned command argv
            io_loop (IOLoop): tornado IOLoop to use, None for default
            show_url (function): function that's passed the URL to open it for the user

        Returns:
            a ``PrepareResult`` instance, which has a ``failed`` flag

        """
        return prepare.prepare_with_browser_ui(project=project,
                                               environ=environ,
                                               conda_environment_name=conda_environment_name,
                                               command_name=command_name,
                                               extra_command_args=extra_command_args,
                                               io_loop=io_loop,
                                               show_url=show_url)

    def set_properties(self, project, name=None, icon=None):
        """Set simple properties on a project.

        This doesn't support properties which require prepare()
        actions to check their effects; see other calls such as
        ``add_dependencies()`` for those.

        This will fail if project.problems is non-empty.

        Args:
            project (``Project``): the project instance
            name (str): Name of the new project or None to leave unmodified
            icon (str): Icon for the new project or None to leave unmodified

        Returns:
            a ``Status`` instance indicating success or failure
        """
        return project_ops.set_properties(project=project, name=name, icon=icon)

    def add_variables(self, project, vars_to_add):
        """Add variables in project.yml and set their values in local project state.

        Returns a ``Status`` instance which evaluates to True on
        success and has an ``errors`` property (with a list of error
        strings) on failure.

        Args:
            project (Project): the project
            vars_to_add (list of tuple): key-value pairs

        Returns:
            ``Status`` instance
        """
        return project_ops.add_variables(project=project, vars_to_add=vars_to_add)

    def remove_variables(self, project, vars_to_remove):
        """Remove variables from project.yml and unset their values in local project state.

        Returns a ``Status`` instance which evaluates to True on
        success and has an ``errors`` property (with a list of error
        strings) on failure.

        Args:
            project (Project): the project
            vars_to_remove (list of tuple): key-value pairs

        Returns:
            ``Status`` instance
        """
        return project_ops.remove_variables(project=project, vars_to_remove=vars_to_remove)

    def add_download(self, project, env_var, url, filename=None):
        """Attempt to download the URL; if successful, add it as a download to the project.

        The returned ``Status`` should be a ``RequirementStatus`` for
        the download requirement if it evaluates to True (on success),
        but may be another subtype of ``Status`` on failure. A False
        status will have an ``errors`` property with a list of error
        strings.

        Args:
            project (Project): the project
            env_var (str): env var to store the local filename
            url (str): url to download
            filename (optional, str): Name to give file or directory after downloading

        Returns:
            ``Status`` instance
        """
        return project_ops.add_download(project=project, env_var=env_var, url=url, filename=filename)

    def remove_download(self, project, env_var):
        """Remove file or directory referenced by ``env_var`` from file system and the project.

        The returned ``Status`` will be an instance of ``SimpleStatus``. A False
        status will have an ``errors`` property with a list of error
        strings.

        Args:
            project (Project): the project
            env_var (str): env var to store the local filename

        Returns:
            ``Status`` instance
        """
        return project_ops.remove_download(project=project, env_var=env_var)

    def add_environment(self, project, name, packages, channels):
        """Attempt to create the environment and add it to project.yml.

        The returned ``Status`` will be an instance of ``SimpleStatus``. A False
        status will have an ``errors`` property with a list of error
        strings.

        Args:
            project (Project): the project
            name (str): environment name
            packages (list of str): dependencies (with optional version info, as for conda install)
            channels (list of str): channels (as they should be passed to conda --channel)

        Returns:
            ``Status`` instance
        """
        return project_ops.add_environment(project=project, name=name, packages=packages, channels=channels)

    def remove_environment(self, project, name):
        """Remove the environment from project directory and remove from project.yml.

        Returns a ``Status`` subtype (it won't be a
        ``RequirementStatus`` as with some other functions, just a
        plain status).

        Args:
            project (Project): the project
            name (str): environment name

        Returns:
            ``Status`` instance
        """
        return project_ops.remove_environment(project=project, name=name)

    def add_dependencies(self, project, environment, packages, channels):
        """Attempt to install dependencies then add them to project.yml.

        If the environment is None rather than an env name,
        dependencies are added in the global dependencies section (to
        all environments).

        The returned ``Status`` should be a ``RequirementStatus`` for
        the environment requirement if it evaluates to True (on success),
        but may be another subtype of ``Status`` on failure. A False
        status will have an ``errors`` property with a list of error
        strings.

        Args:
            project (Project): the project
            environment (str): environment name or None for all environments
            packages (list of str): dependencies (with optional version info, as for conda install)
            channels (list of str): channels (as they should be passed to conda --channel)

        Returns:
            ``Status`` instance
        """
        return project_ops.add_dependencies(project=project,
                                            environment=environment,
                                            packages=packages,
                                            channels=channels)

    def remove_dependencies(self, project, environment, packages):
        """Attempt to remove dependencies from an environment in project.yml.

        If the environment is None rather than an env name,
        dependencies are removed from the global dependencies section
        (from all environments).

        The returned ``Status`` should be a ``RequirementStatus`` for
        the environment requirement if it evaluates to True (on success),
        but may be another subtype of ``Status`` on failure. A False
        status will have an ``errors`` property with a list of error
        strings.

        Args:
            project (Project): the project
            environment (str): environment name or None for all environments
            packages (list of str): dependencies

        Returns:
            ``Status`` instance
        """
        return project_ops.remove_dependencies(project=project, environment=environment, packages=packages)

    def add_command(self, project, name, command_type, command):
        """Add a command to project.yml.

        Returns a ``Status`` subtype (it won't be a
        ``RequirementStatus`` as with some other functions, just a
        plain status).

        Args:
           project (Project): the project
           name (str): name of the command
           command_type (str): choice of `bokeh_app`, `notebook`, `shell` or `windows` command
           command (str): the command line or filename itself

        Returns:
           a ``Status`` instance

        """
        return project_ops.add_command(project=project, name=name, command_type=command_type, command=command)

    def update_command(self, project, name, command_type=None, command=None, new_name=None):
        """Update attributes of a command in project.yml.

        Returns a ``Status`` subtype (it won't be a
        ``RequirementStatus`` as with some other functions, just a
        plain status).

        Args:
           project (Project): the project
           name (str): name of the command
           command_type (str or None): choice of `bokeh_app`, `notebook`, `shell` or `windows` command
           command (str or None): the command line or filename itself; command_type must also be specified
           new_name (str or None): a new name to reference the command

        Returns:
           a ``Status`` instance
        """
        return project_ops.update_command(project=project,
                                          name=name,
                                          command_type=command_type,
                                          command=command,
                                          new_name=new_name)

    def remove_command(self, project, name):
        """Remove a command from project.yml.

        Returns a ``Status`` subtype (it won't be a
        ``RequirementStatus`` as with some other functions, just a
        plain status).

        Args:
           project (Project): the project
           name (string): name of the command to be removed

        Returns:
           a ``Status`` instance
        """
        return project_ops.remove_command(project=project, name=name)

    def add_service(self, project, service_type, variable_name=None):
        """Add a service to project.yml.

        The returned ``Status`` should be a ``RequirementStatus`` for
        the service requirement if it evaluates to True (on success),
        but may be another subtype of ``Status`` on failure. A False
        status will have an ``errors`` property with a list of error
        strings.

        Args:
            project (Project): the project
            service_type (str): which kind of service
            variable_name (str): environment variable name (None for default)

        Returns:
            ``Status`` instance
        """
        return project_ops.add_service(project=project, service_type=service_type, variable_name=variable_name)

    def remove_service(self, project, variable_name=None):
        """Remove a service to project.yml.

        Returns a ``Status`` instance which evaluates to True on
        success and has an ``errors`` property (with a list of error
        strings) on failure.

        Args:
            project (Project): the project
            variable_name (str): environment variable name (None for default)

        Returns:
            ``Status`` instance
        """
        return project_ops.remove_service(project=project, variable_name=variable_name)
