# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
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

    def load_project(self, directory_path, frontend):
        """Load a project from the given directory.

        If there's a problem, the returned Project instance will
        have a non-empty ``problems`` attribute. So check
        ``project.problems`` when you get the result.
        ``project.problems`` can change anytime changes are made
        to a project; code must always be ready for a project to
        have some problems.

        Args:
            directory_path (str): path to the project directory
            frontend (Frontend): UX abstraction

        Returns:
            a Project instance

        """
        return project.Project(directory_path=directory_path, frontend=frontend)

    def create_project(self, directory_path, make_directory=False, name=None, icon=None, description=None):
        """Create a project skeleton in the given directory.

        Returns a Project instance even if creation fails or the directory
        doesn't exist, but in those cases the ``problems`` attribute
        of the Project will describe the problem.

        If the anaconda-project.yml already exists, this simply loads it.

        This will not prepare the project (create environments, etc.),
        use the separate prepare calls if you want to do that.

        Args:
            directory_path (str): directory to contain anaconda-project.yml
            make_directory (bool): True to create the directory if it doesn't exist
            name (str): Name of the new project or None to leave unset (uses directory name)
            icon (str): Icon for the new project or None to leave unset (uses no icon)
            description (str): Description for the new project or None to leave unset

        Returns:
            a Project instance
        """
        return project_ops.create(directory_path=directory_path,
                                  make_directory=make_directory,
                                  name=name,
                                  icon=icon,
                                  description=description)

    def prepare_project_locally(self,
                                project,
                                environ,
                                env_spec_name=None,
                                command_name=None,
                                command=None,
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
            env_spec_name (str): the package set name to require, or None for default
            command_name (str): which named command to choose from the project, None for default
            command (ProjectCommand): a command object (alternative to command_name)
            extra_command_args (list): extra args to include in the returned command argv

        Returns:
            a ``PrepareResult`` instance, which has a ``failed`` flag

        """
        return prepare.prepare_without_interaction(project=project,
                                                   environ=environ,
                                                   mode=provide.PROVIDE_MODE_DEVELOPMENT,
                                                   env_spec_name=env_spec_name,
                                                   command_name=command_name,
                                                   command=command,
                                                   extra_command_args=extra_command_args)

    def prepare_project_production(self,
                                   project,
                                   environ,
                                   env_spec_name=None,
                                   command_name=None,
                                   command=None,
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
            env_spec_name (str): the package set name to require, or None for default
            command_name (str): which named command to choose from the project, None for default
            command (ProjectCommand): a command object (alternative to command_name)
            extra_command_args (list): extra args to include in the returned command argv

        Returns:
            a ``PrepareResult`` instance, which has a ``failed`` flag

        """
        return prepare.prepare_without_interaction(project=project,
                                                   environ=environ,
                                                   mode=provide.PROVIDE_MODE_PRODUCTION,
                                                   env_spec_name=env_spec_name,
                                                   command_name=command_name,
                                                   command=command,
                                                   extra_command_args=extra_command_args)

    def prepare_project_check(self,
                              project,
                              environ,
                              env_spec_name=None,
                              command_name=None,
                              command=None,
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
            env_spec_name (str): the package set name to require, or None for default
            command_name (str): which named command to choose from the project, None for default
            command (ProjectCommand): a command object (alternative to command_name)
            extra_command_args (list): extra args to include in the returned command argv

        Returns:
            a ``PrepareResult`` instance, which has a ``failed`` flag

        """
        return prepare.prepare_without_interaction(project=project,
                                                   environ=environ,
                                                   mode=provide.PROVIDE_MODE_CHECK,
                                                   env_spec_name=env_spec_name,
                                                   command_name=command_name,
                                                   command=command,
                                                   extra_command_args=extra_command_args)

    def unprepare(self, project, prepare_result, whitelist=None):
        """Attempt to clean up project-scoped resources allocated by prepare().

        This will retain any user configuration choices about how to
        provide requirements, but it stops project-scoped services.
        Global system services or other services potentially shared
        among projects will not be stopped.

        To stop a single service, use ``whitelist=["SERVICE_VARIABLE"]``.

        Args:
            project (Project): the project
            prepare_result (PrepareResult): result from the previous prepare
            whitelist (iterable of str or type): ONLY call shutdown commands for the listed env vars' requirements

        """
        return prepare.unprepare(project=project, prepare_result=prepare_result, whitelist=whitelist)

    def set_properties(self, project, name=None, icon=None, description=None):
        """Set simple properties on a project.

        This doesn't support properties which require prepare()
        actions to check their effects; see other calls such as
        ``add_packages()`` for those.

        This will fail if project.problems is non-empty.

        Args:
            project (``Project``): the project instance
            name (str): Name of the project or None to leave unmodified
            icon (str): Icon for the project or None to leave unmodified
            description (str): description for the project or None to leave unmodified

        Returns:
            a ``Status`` instance indicating success or failure
        """
        return project_ops.set_properties(project=project, name=name, icon=icon, description=description)

    def add_variables(self, project, env_spec_name, vars_to_add, defaults):
        """Add variables in anaconda-project.yml, optionally setting their defaults.

        Returns a ``Status`` instance which evaluates to True on
        success and has an ``errors`` property (with a list of error
        strings) on failure.

        Args:
            project (Project): the project
            env_spec_name (str): environment spec name or None for all environment specs
            vars_to_add (list of str): variable names
            defaults (dict): dictionary from keys to defaults, can be empty

        Returns:
            ``Status`` instance
        """
        return project_ops.add_variables(project=project,
                                         env_spec_name=env_spec_name,
                                         vars_to_add=vars_to_add,
                                         defaults=defaults)

    def remove_variables(self, project, env_spec_name, vars_to_remove, prepare_result=None):
        """Remove variables from anaconda-project.yml and unset their values in local project state.

        Returns a ``Status`` instance which evaluates to True on
        success and has an ``errors`` property (with a list of error
        strings) on failure.

        Args:
            project (Project): the project
            env_spec_name (str): environment spec name or None for all environment specs
            vars_to_remove (list of tuple): key-value pairs
            prepare_result (PrepareResult): result of a previous prepare or None

        Returns:
            ``Status`` instance
        """
        return project_ops.remove_variables(project=project,
                                            env_spec_name=env_spec_name,
                                            vars_to_remove=vars_to_remove,
                                            prepare_result=prepare_result)

    def set_variables(self, project, env_spec_name, vars_and_values, prepare_result=None):
        """Set variables' values in anaconda-project-local.yml.

        Returns a ``Status`` instance which evaluates to True on
        success and has an ``errors`` property (with a list of error
        strings) on failure.

        Args:
            project (Project): the project
            env_spec_name (str): environment spec name or None for all environment specs
            vars_and_values (list of tuple): key-value pairs
            prepare_result (PrepareResult): result of a previous prepare or None

        Returns:
            ``Status`` instance
        """
        return project_ops.set_variables(project=project,
                                         env_spec_name=env_spec_name,
                                         vars_and_values=vars_and_values,
                                         prepare_result=prepare_result)

    def unset_variables(self, project, env_spec_name, vars_to_unset, prepare_result=None):
        """Unset variables' values in anaconda-project-local.yml.

        Returns a ``Status`` instance which evaluates to True on
        success and has an ``errors`` property (with a list of error
        strings) on failure.

        Args:
            project (Project): the project
            env_spec_name (str): environment spec name or None for all environment specs
            vars_to_unset (list of str): variable names
            prepare_result (PrepareResult): result of a previous prepare or None

        Returns:
            ``Status`` instance
        """
        return project_ops.unset_variables(project=project,
                                           env_spec_name=env_spec_name,
                                           vars_to_unset=vars_to_unset,
                                           prepare_result=prepare_result)

    def add_download(self, project, env_spec_name, env_var, url, filename=None, hash_algorithm=None, hash_value=None):
        """Attempt to download the URL; if successful, add it as a download to the project.

        The returned ``Status`` should be a ``RequirementStatus`` for
        the download requirement if it evaluates to True (on success),
        but may be another subtype of ``Status`` on failure. A False
        status will have an ``errors`` property with a list of error
        strings.

        Args:
            project (Project): the project
            env_spec_name (str): environment spec name or None for all environment specs
            env_var (str): env var to store the local filename
            url (str): url to download
            filename (optional, str): Name to give file or directory after downloading
            hash_algorithm (optional, str): Name of the algorithm to use for checksum verification
                                       must be present if hash_value is entered
            hash_value (optional, str): Checksum value to use for verification
                                           must be present if hash_algorithm is entered
        Returns:
            ``Status`` instance
        """
        return project_ops.add_download(project=project,
                                        env_spec_name=env_spec_name,
                                        env_var=env_var,
                                        url=url,
                                        filename=filename,
                                        hash_algorithm=hash_algorithm,
                                        hash_value=hash_value)

    def remove_download(self, project, env_spec_name, env_var, prepare_result=None):
        """Remove file or directory referenced by ``env_var`` from file system and the project.

        The returned ``Status`` will be an instance of ``SimpleStatus``. A False
        status will have an ``errors`` property with a list of error
        strings.

        Args:
            project (Project): the project
            env_spec_name (str): environment spec name or None for all environment specs
            env_var (str): env var to store the local filename
            prepare_result (PrepareResult): result of a previous prepare

        Returns:
            ``Status`` instance
        """
        return project_ops.remove_download(project=project,
                                           env_spec_name=env_spec_name,
                                           env_var=env_var,
                                           prepare_result=prepare_result)

    def add_env_spec(self, project, name, packages, channels):
        """Attempt to create the environment spec and add it to anaconda-project.yml.

        The returned ``Status`` will be an instance of ``SimpleStatus``. A False
        status will have an ``errors`` property with a list of error
        strings.

        Args:
            project (Project): the project
            name (str): environment name
            packages (list of str): packages (with optional version info, as for conda install)
            channels (list of str): channels (as they should be passed to conda --channel)

        Returns:
            ``Status`` instance
        """
        return project_ops.add_env_spec(project=project, name=name, packages=packages, channels=channels)

    def remove_env_spec(self, project, name):
        """Remove the environment spec from project directory and remove from anaconda-project.yml.

        Returns a ``Status`` subtype (it won't be a
        ``RequirementStatus`` as with some other functions, just a
        plain status).

        Args:
            project (Project): the project
            name (str): environment name

        Returns:
            ``Status`` instance
        """
        return project_ops.remove_env_spec(project=project, name=name)

    def export_env_spec(self, project, name, filename):
        """Export the environment spec as an environment.yml-type file.

        Returns a ``Status`` subtype (it won't be a
        ``RequirementStatus`` as with some other functions, just a
        plain status).

        Args:
            project (Project): the project
            name (str): environment spec name
            filename (str): file to export to

        Returns:
            ``Status`` instance
        """
        return project_ops.export_env_spec(project=project, name=name, filename=filename)

    def add_packages(self, project, env_spec_name, packages, channels, pip=False):
        """Attempt to install packages then add them to anaconda-project.yml.

        If the environment spec name is None rather than an env
        name, packages are added in the global packages
        section (to all environments).

        The returned ``Status`` should be a ``RequirementStatus`` for
        the environment requirement if it evaluates to True (on success),
        but may be another subtype of ``Status`` on failure. A False
        status will have an ``errors`` property with a list of error
        strings.

        Args:
            project (Project): the project
            env_spec_name (str): environment spec name or None for all environment specs
            packages (list of str): packages (with optional version info, as for conda install)
            channels (list of str): channels (as they should be passed to conda --channel)
            pip (bool): Flag to request packages to be installed with pip if True else use Conda.

        Returns:
            ``Status`` instance

        """
        return project_ops.add_packages(project=project,
                                        env_spec_name=env_spec_name,
                                        packages=packages,
                                        channels=channels,
                                        pip=pip)

    def remove_packages(self, project, env_spec_name, packages, pip):
        """Attempt to remove packages from an environment spec in anaconda-project.yml.

        If the environment spec name is None rather than an env
        name, packages are removed from the global
        packages section (from all environments).

        The returned ``Status`` should be a ``RequirementStatus`` for
        the environment requirement if it evaluates to True (on success),
        but may be another subtype of ``Status`` on failure. A False
        status will have an ``errors`` property with a list of error
        strings.

        Args:
            project (Project): the project
            env_spec_name (str): environment name or None for all environments
            packages (list of str): packages
            pip (bool): Flag to request packages to be removed with pip if True else use Conda.

        Returns:
            ``Status`` instance

        """
        return project_ops.remove_packages(project=project, env_spec_name=env_spec_name, packages=packages, pip=pip)

    def lock(self, project, env_spec_name):
        """Attempt to freeze dependency versions in anaconda-project-lock.yml.

        If the env_spec_name is None rather than a name,
        all env specs are frozen.

        Args:
            project (Project): the project
            env_spec_name (str): environment spec name or None for all environment specs

        Returns:
            ``Status`` instance
        """
        return project_ops.lock(project=project, env_spec_name=env_spec_name)

    def update(self, project, env_spec_name):
        """Attempt to update frozen dependency versions in anaconda-project-lock.yml.

        If the env_spec_name is None rather than a name,
        all env specs are updated.

        If an env is not locked, this updates the installed dependencies but
        doesn't change anything about project configuration (does not save
        the lock file).

        Args:
            project (Project): the project
            env_spec_name (str): environment spec name or None for all environment specs

        Returns:
            ``Status`` instance
        """
        return project_ops.update(project=project, env_spec_name=env_spec_name)

    def unlock(self, project, env_spec_name):
        """Attempt to unfreeze dependency versions in anaconda-project-lock.yml.

        If the env_spec_name is None rather than a name,
        all env specs are unfrozen.

        Args:
            project (Project): the project
            env_spec_name (str): environment spec name or None for all environment specs

        Returns:
            ``Status`` instance
        """
        return project_ops.unlock(project=project, env_spec_name=env_spec_name)

    def add_platforms(self, project, env_spec_name, platforms):
        """Attempt to add platforms the project supports.

        If the env_spec_name is None rather than an env name,
        packages are added in the global platforms section (to
        all environment specs).

        The returned ``Status`` should be a ``RequirementStatus`` for
        the environment requirement if it evaluates to True (on success),
        but may be another subtype of ``Status`` on failure. A False
        status will have an ``errors`` property with a list of error
        strings.

        Args:
            project (Project): the project
            env_spec_name (str): environment spec name or None for all environment specs
            platforms (list of str): platforms to add

        Returns:
            ``Status`` instance
        """
        return project_ops.add_platforms(project=project, env_spec_name=env_spec_name, platforms=platforms)

    def remove_platforms(self, project, env_spec_name, platforms):
        """Attempt to remove platforms the project supports.

        If the env_spec_name is None rather than an env name,
        packages are added in the global platforms section (to
        all environment specs).

        The returned ``Status`` should be a ``RequirementStatus`` for
        the environment requirement if it evaluates to True (on success),
        but may be another subtype of ``Status`` on failure. A False
        status will have an ``errors`` property with a list of error
        strings.

        Args:
            project (Project): the project
            env_spec_name (str): environment spec name or None for all environment specs
            platforms (list of str): platforms to remove

        Returns:
            ``Status`` instance
        """
        return project_ops.remove_platforms(project=project, env_spec_name=env_spec_name, platforms=platforms)

    def add_command(self, project, name, command_type, command, env_spec_name=None, supports_http_options=None):
        """Add a command to anaconda-project.yml.

        Returns a ``Status`` subtype (it won't be a
        ``RequirementStatus`` as with some other functions, just a
        plain status).

        Args:
           project (Project): the project
           name (str): name of the command
           command_type (str): choice of `bokeh_app`, `notebook`, `unix` or `windows` command
           command (str): the command line or filename itself
           env_spec_name (str): env spec to use with this command
           supports_http_options (bool): whether command supports --anaconda-project-* http server options

        Returns:
           a ``Status`` instance

        """
        return project_ops.add_command(project=project,
                                       name=name,
                                       command_type=command_type,
                                       command=command,
                                       env_spec_name=env_spec_name,
                                       supports_http_options=supports_http_options)

    def update_command(self, project, name, command_type=None, command=None, new_name=None):
        """Update attributes of a command in anaconda-project.yml.

        Returns a ``Status`` subtype (it won't be a
        ``RequirementStatus`` as with some other functions, just a
        plain status).

        Args:
           project (Project): the project
           name (str): name of the command
           command_type (str or None): choice of `bokeh_app`, `notebook`, `unix` or `windows` command
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
        """Remove a command from anaconda-project.yml.

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

    def add_service(self, project, env_spec_name, service_type, variable_name=None):
        """Add a service to anaconda-project.yml.

        The returned ``Status`` should be a ``RequirementStatus`` for
        the service requirement if it evaluates to True (on success),
        but may be another subtype of ``Status`` on failure. A False
        status will have an ``errors`` property with a list of error
        strings.

        Args:
            project (Project): the project
            env_spec_name (str): environment spec name or None for all environment specs
            service_type (str): which kind of service
            variable_name (str): environment variable name (None for default)

        Returns:
            ``Status`` instance
        """
        return project_ops.add_service(project=project,
                                       env_spec_name=env_spec_name,
                                       service_type=service_type,
                                       variable_name=variable_name)

    def remove_service(self, project, env_spec_name, variable_name, prepare_result=None):
        """Remove a service to anaconda-project.yml.

        Returns a ``Status`` instance which evaluates to True on
        success and has an ``errors`` property (with a list of error
        strings) on failure.

        Args:
            project (Project): the project
            env_spec_name (str): environment spec name or None for all environment specs
            variable_name (str): environment variable name for the service requirement
            prepare_result (PrepareResult): result of a previous prepare or None

        Returns:
            ``Status`` instance
        """
        return project_ops.remove_service(project=project,
                                          env_spec_name=env_spec_name,
                                          variable_name=variable_name,
                                          prepare_result=prepare_result)

    def clean(self, project, prepare_result):
        """Blow away auto-provided state for the project.

        This should not remove any potential "user data" such as
        anaconda-project-local.yml.

        Args:
            project (Project): the project instance
            prepare_result (PrepareResult): result of a previous prepare

        Returns:
            a ``Status`` instance

        """
        return project_ops.clean(project=project, prepare_result=prepare_result)

    def archive(self, project, filename, pack_envs=False):
        """Make an archive of the non-ignored files in the project.

        Args:
            project (``Project``): the project
            filename (str): name of a zip, tar.gz, or tar.bz2 archive file
            pack_envs (bool): Flag to include conda-packs of each env_spec in the archive

        Returns:
            a ``Status``, if failed has ``errors``
        """
        return project_ops.archive(project=project, filename=filename, pack_envs=pack_envs)

    def unarchive(self, filename, project_dir, parent_dir=None, frontend=None):
        """Unpack an archive of the project.

        The archive can be untrusted (we will safely defeat attempts
        to put evil links in it, for example), but this function
        doesn't load or validate the unpacked project.

        The target directory must not exist or it's an error.

        project_dir can be None to auto-choose one.

        If parent_dir is non-None, place the project_dir in it. This is most useful
        if project_dir is None.

        Args:
            filename (str): name of a zip, tar.gz, or tar.bz2 archive file
            project_dir (str): the directory to place the project inside
            parent_dir (str): directory to place project_dir within
            frontend (Frontend): frontend instance representing current UX

        Returns:
            a ``Status``, if failed has ``errors``, on success has ``project_dir`` property.

        """
        return project_ops.unarchive(filename=filename,
                                     project_dir=project_dir,
                                     parent_dir=parent_dir,
                                     frontend=frontend)

    def upload(self, project, private=None, site=None, username=None, token=None, suffix='.tar.bz2', log_level=None):
        """Upload the project to the Anaconda server.

        Args:
            project (``Project``): the project
            private (bool): make project private
            site (str): site alias from Anaconda config
            username (str): Anaconda username
            token (str): Anaconda auth token
            log_level (str): Anaconda log level

        Returns:
            a ``Status``, if failed has ``errors``
        """
        return project_ops.upload(project=project,
                                  private=private,
                                  site=site,
                                  username=username,
                                  token=token,
                                  suffix=suffix,
                                  log_level=log_level)
