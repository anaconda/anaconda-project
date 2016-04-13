# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""High-level operations on a project."""
from __future__ import absolute_import

import os

from anaconda_project.project import Project
from anaconda_project import prepare
from anaconda_project.local_state_file import LocalStateFile
from anaconda_project.plugins.requirement import EnvVarRequirement


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


def add_download(project, env_var, url):
    """Attempt to download the URL; if successful, add it as a download to the project.

    The returned status would be None if we failed to even check the status for
    some reason... currently this would happen if the project has non-empty
    ``project.problems``.

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
    project.project_file.use_changes_without_saving()

    # See if we can perform the download
    result = prepare.prepare_without_interaction(project, provide_whitelist=(env_var, ))

    status = result.status_for_env_var(env_var)
    if status is None or not status:
        # reload from disk, discarding our changes because they did not work
        project.project_file.load()
    else:
        # yay!
        project.project_file.save()
    return status


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
            project.project_file.set_value(['runtime', varname], {})
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
        project.project_file.unset_value(['runtime', varname])
    project.project_file.save()
    local_state.save()
