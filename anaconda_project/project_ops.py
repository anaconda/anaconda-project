# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""High-level operations on a project."""
from __future__ import absolute_import

import os

from anaconda_project.project import Project, _COMMAND_CHOICES
from anaconda_project import prepare
from anaconda_project.local_state_file import LocalStateFile
from anaconda_project.plugins.requirement import EnvVarRequirement
from anaconda_project.plugins.requirements.conda_env import CondaEnvRequirement
from anaconda_project.internal.simple_status import SimpleStatus


def create(directory_path, make_directory=False):
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
    if make_directory and not os.path.exists(directory_path):
        try:
            os.makedirs(directory_path)
        except (IOError, OSError):  # py3=IOError, py2=OSError
            # allow project.problems to report the issue
            pass

    project = Project(directory_path)

    # write out the project.yml; note that this will try to create
    # the directory which we may not want... so only do it if
    # we're problem-free.
    if len(project.problems) == 0:
        project.project_file.save()

    return project


def _commit_requirement_if_it_works(project, env_var_or_class, default_environment_name=None):
    project.project_file.use_changes_without_saving()

    # See if we can perform the download
    result = prepare.prepare_without_interaction(project, provide_whitelist=(env_var_or_class, ))

    status = result.status_for(env_var_or_class)
    if status is None or not status:
        # reload from disk, discarding our changes because they did not work
        project.project_file.load()
    else:
        # yay!
        project.project_file.save()
    return status


def add_download(project, env_var, url):
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
    # Modify the project file _in memory only_, do not save
    existing = project.project_file.get_value(['downloads', env_var])
    if existing is not None and isinstance(existing, dict):
        project.project_file.set_value(['downloads', env_var, 'url'], url)
    else:
        project.project_file.set_value(['downloads', env_var], url)

    return _commit_requirement_if_it_works(project, env_var)


def _update_environment(project, name, packages, channels, create):
    if packages is None:
        packages = []
    if channels is None:
        channels = []

    if not create and (name is not None):
        if name not in project.conda_environments:
            problem = "Environment {} doesn't exist.".format(name)
            return SimpleStatus(success=False, description=problem)

    # Due to https://github.com/Anaconda-Server/anaconda-project/issues/163
    # we don't have a way to "choose" this environment when we do the prepare
    # in _commit_requirement_if_it_works, so we will have to hack things and
    # make a temporary Project here then reload the original project.
    # Doh.
    original_project = project
    project = Project(original_project.directory_path, default_conda_environment=name)
    if name is None:
        env_dict = project.project_file.root
    else:
        env_dict = project.project_file.get_value(['environments', name])
        if env_dict is None:
            env_dict = dict()
            project.project_file.set_value(['environments', name], env_dict)

    # dependencies may be a "CommentedSeq" and we don't want to lose the comments,
    # so don't convert this thing to a regular list.
    dependencies = env_dict.get('dependencies', [])
    old_dependencies_set = set(dependencies)
    for dep in packages:
        # note: we aren't smart enough to merge deps with the same
        # package name but different versions.
        if dep not in old_dependencies_set:
            dependencies.append(dep)
    env_dict['dependencies'] = dependencies

    # channels may be a "CommentedSeq" and we don't want to lose the comments,
    # so don't convert this thing to a regular list.
    new_channels = env_dict.get('channels', [])
    old_channels_set = set(new_channels)
    for channel in channels:
        if channel not in old_channels_set:
            new_channels.append(channel)
    env_dict['channels'] = new_channels

    status = _commit_requirement_if_it_works(project, CondaEnvRequirement)

    # reload original project, hackaround for
    # https://github.com/Anaconda-Server/anaconda-project/issues/163
    if status:
        # reload the new config
        original_project.project_file.load()

    return status


def add_environment(project, name, packages, channels):
    """Attempt to create the environment and add it to project.yml.

    The returned status would be None if we failed to even check the status for
    some reason... currently this would happen if the project has non-empty
    ``project.problems``.

    If the returned status is not None, if it's True we were
    successful, and if it's false ``status.errors`` may
    (hopefully) contain a list of useful error strings.  The
    status will usually be a ``RequirementStatus`` but may be some
    other subtype of ``Status``.

    Args:
        project (Project): the project
        name (str): environment name
        packages (list of str): dependencies (with optional version info, as for conda install)
        channels (list of str): channels (as they should be passed to conda --channel)

    Returns:
        ``Status`` instance or None

    """
    assert name is not None
    return _update_environment(project, name, packages, channels, create=True)


def add_dependencies(project, environment, packages, channels):
    """Attempt to install dependencies then add them to project.yml.

    If the environment is None rather than an env name,
    dependencies are added in the global dependencies section (to
    all environments).

    The returned status would be None if we failed to even check the status for
    some reason... currently this would happen if the project has non-empty
    ``project.problems``.

    If the returned status is not None, if it's True we were
    successful, and if it's false ``status.errors`` may
    (hopefully) contain a list of useful error strings.  The
    status will usually be a ``RequirementStatus`` but may be some
    other subtype of ``Status``.

    Args:
        project (Project): the project
        environment (str): environment name or None for all environments
        packages (list of str): dependencies (with optional version info, as for conda install)
        channels (list of str): channels (as they should be passed to conda --channel)

    Returns:
        ``Status`` instance or None

    """
    return _update_environment(project, environment, packages, channels, create=False)


def add_variables(project, vars_to_add):
    """Add variables in project.yml and set their values in local project state.

    Args:
        project (Project): the project
        vars_to_add (list of tuple): key-value pairs

    Returns:
        None
    """
    local_state = LocalStateFile.load_for_directory(project.directory_path)
    present_vars = {req.env_var for req in project.requirements if isinstance(req, EnvVarRequirement)}
    for varname, value in vars_to_add:
        local_state.set_value(['variables', varname], value)
        if varname not in present_vars:
            project.project_file.set_value(['variables', varname], None)
    project.project_file.save()
    local_state.save()


def remove_variables(project, vars_to_remove):
    """Add variables in project.yml and set their values in local project state.

    Args:
        project (Project): the project
        vars_to_remove (list of tuple): key-value pairs

    Returns:
        None
    """
    local_state = LocalStateFile.load_for_directory(project.directory_path)
    for varname in vars_to_remove:
        local_state.unset_value(['variables', varname])
        project.project_file.unset_value(['variables', varname])
    project.project_file.save()
    local_state.save()


def add_command(project, command_type, name, command):
    """Add a command to project.yml.

    Args:
       project (Project): the project
       command_type: choice of `bokeh_app`, `notebook`, `shell` or `windows` command

    Returns:
       None on success, list of error strings otherwise
    """
    if command_type not in _COMMAND_CHOICES:
        raise ValueError("Invalid command type " + command_type + " choose from " + repr(_COMMAND_CHOICES))

    command_dict = project.project_file.get_value(['commands', name])
    if command_dict is None:
        command_dict = dict()
        project.project_file.set_value(['commands', name], command_dict)

    command_dict[command_type] = command

    project.project_file.use_changes_without_saving()

    if len(project.problems) > 0:
        problems = project.problems
        # reset, maybe someone added conflicting command line types or something
        project.project_file.load()
        return problems
    else:
        project.project_file.save()
        return None
