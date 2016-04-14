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

    def load_project(self, directory_path, default_conda_environment=None, default_command=None):
        """Load a project from the given directory.

        If there's a problem, the returned Project instance will
        have a non-empty ``problems`` attribute. So check
        ``project.problems`` when you get the result.
        ``project.problems`` can change anytime changes are made
        to a project; code must always be ready for a project to
        have some problems.

        Args:
            directory_path (str): path to the project directory
            default_conda_environment (str): name of conda environment spec to use by default
            default_command (str): name of command from commands section to use by default

        Returns:
            a Project instance

        """
        return project.Project(directory_path=directory_path,
                               default_conda_environment=default_conda_environment,
                               default_command=default_command)

    def create_project(self, directory_path, make_directory=False):
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

        Returns:
            a Project instance
        """
        return project_ops.create(directory_path=directory_path, make_directory=make_directory)

    def prepare_project_locally(self, project, environ, extra_command_args=None):
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
            extra_command_args (list): extra args to include in the returned command argv

        Returns:
            a ``PrepareResult`` instance, which has a ``failed`` flag

        """
        return prepare.prepare_without_interaction(project=project,
                                                   environ=environ,
                                                   mode=provide.PROVIDE_MODE_DEVELOPMENT,
                                                   extra_command_args=extra_command_args)

    def prepare_project_production(self, project, environ, extra_command_args=None):
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
            extra_command_args (list): extra args to include in the returned command argv

        Returns:
            a ``PrepareResult`` instance, which has a ``failed`` flag

        """
        return prepare.prepare_without_interaction(project=project,
                                                   environ=environ,
                                                   mode=provide.PROVIDE_MODE_PRODUCTION,
                                                   extra_command_args=extra_command_args)

    def prepare_project_check(self, project, environ, extra_command_args=None):
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
            extra_command_args (list): extra args to include in the returned command argv

        Returns:
            a ``PrepareResult`` instance, which has a ``failed`` flag

        """
        return prepare.prepare_without_interaction(project=project,
                                                   environ=environ,
                                                   mode=provide.PROVIDE_MODE_CHECK,
                                                   extra_command_args=extra_command_args)

    def prepare_project_browser(self, project, environ, extra_command_args=None, io_loop=None, show_url=None):
        """Prepare a project to run one of its commands.

        This version uses a browser-based UI to allow the user to
        see and choose how to meet project requirements.

        See ``prepare_project_locally()`` for additional details
        that also apply to this method.

        Args:
            project (Project): from the ``load_project`` method
            environ (dict): os.environ or the previously-prepared environ; not modified in-place
            extra_command_args (list): extra args to include in the returned command argv
            io_loop (IOLoop): tornado IOLoop to use, None for default
            show_url (function): function that's passed the URL to open it for the user

        Returns:
            a ``PrepareResult`` instance, which has a ``failed`` flag

        """
        return prepare.prepare_with_browser_ui(project=project,
                                               environ=environ,
                                               extra_command_args=extra_command_args,
                                               io_loop=io_loop,
                                               show_url=show_url)

    def add_variables(self, project, vars_to_add):
        """Add variables in project.yml and set their values in local project state.

        Args:
           project (Project): the project
           vars_to_add (list of tuple): key-value pairs

        Returns:
           None
        """
        return project_ops.add_variables(project=project, vars_to_add=vars_to_add)

    def remove_variables(self, project, vars_to_remove):
        """Remove variables in project.yml and remove them from local project state.

        Args:
           project (Project): the project
           vars_to_remove (list of strings): variables to remove

        Returns:
           None
        """
        return project_ops.remove_variables(project=project, vars_to_remove=vars_to_remove)

    def add_download(self, project, env_var, url):
        """Attempt to download the URL; if successful, add it as a download to the project.

        The returned status would be None if we failed to even check the status for
        some reason... currently this would happen if the project has non-empty
        ``project.problems``.

        If the returned status is not None, if it's True we were
        successful, and if it's false ``status.errors`` may
        (hopefully) contain a list of useful error strings.

        Args:
            project (Project): the project
            env_var (str): env var to store the local filename
            url (str): url to download

        Returns:
            RequirementStatus instance for the download requirement or None

        """
        return project_ops.add_download(project=project, env_var=env_var, url=url)
