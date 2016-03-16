from __future__ import absolute_import, print_function

from project.project import Project
from project.local_state_file import LocalStateFile


def project_dir_disable_dedicated_env(dirname):
    """Modify project config to disable having a dedicated environment."""
    local_state = LocalStateFile.load_for_directory(dirname)
    local_state.set_value('inherit_environment', True)
    local_state.save()


def project_no_dedicated_env(*args, **kwargs):
    """Get a project that won't create envs/default as long as there's an env already."""
    if len(args) > 0:
        dirname = args[0]
    elif 'directory_path' in kwargs:
        dirname = kwargs['directory_path']
    else:
        raise RuntimeError("no directory_path for Project")

    project_dir_disable_dedicated_env(dirname)

    project = Project(*args, **kwargs)

    return project
