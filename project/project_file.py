"""Project file loading and manipulation."""
from __future__ import absolute_import

import os

from project.yaml_file import YamlFile
from project.project_meta_common import _ProjectMetaCommon

# use .yml not .yaml to make Windows happy
PROJECT_FILENAME = "project.yml"


class ProjectFile(YamlFile, _ProjectMetaCommon):
    """Represents the ``project.yml`` file which describes the project across machines/users.

    State that's specific to a machine/user/checkout/deployment
    should instead be in ``LocalStateFile``.  ``ProjectFile``
    would normally be checked in to source control or otherwise
    act as a shared resource.

    Be careful with creating your own instance of this class,
    because you have to think about when other code might load or
    save in a way that conflicts with your loads and saves.

    """

    @classmethod
    def load_for_directory(cls, directory):
        """Load the project file from the given directory, even if it doesn't exist.

        If the directory has no project file, the loaded
        ``ProjectFile`` will be empty. It won't actually be
        created on disk unless you call ``save()``.

        If the file has syntax problems, this sets the
        ``corrupted`` and ``corrupted_error_message`` properties,
        and attempts to modify the file will raise an
        exception. If the project file has semantic problems, they
        are not detected by this class but are reported by the
        ``Project`` class.

        Args:
            directory (str): path to the project directory

        Returns:
            a new ``ProjectFile``

        """
        path = os.path.join(directory, PROJECT_FILENAME)
        return ProjectFile(path)

    def __init__(self, filename):
        """Construct a ``ProjectFile`` with the given filename and requirement registry.

        It's easier to use ``ProjectFile.load_for_directory()`` in most cases.

        If the file has syntax problems, this sets the
        ``corrupted`` and ``corrupted_error_message`` properties,
        and attempts to modify the file will raise an
        exception. If the project file has semantic problems, they
        are not detected by this class but are reported by the
        ``Project`` class.

        Args:
            filename (str): path to the project file

        """
        super(ProjectFile, self).__init__(filename)

    def _default_comment(self):
        return "Anaconda project file"
