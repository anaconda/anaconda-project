"""conda.recipe/meta.yaml file loading and manipulation."""
from __future__ import absolute_import

import os

from project.yaml_file import YamlFile
from project.project_meta_common import _ProjectMetaCommon

META_DIRECTORY = "conda.recipe"

# hmm. this one uses .yaml and our others use .yml,
# as does environment.yml
META_FILENAME = "meta.yaml"


class CondaMetaFile(YamlFile, _ProjectMetaCommon):
    """Represents the ``conda.recipe/meta.yaml`` file which describes the project for packaging.

    Anaconda Project reads this, if present, for information not found in project.yml.

    See file format docs at http://conda.pydata.org/docs/building/meta-yaml.html
    """

    @classmethod
    def load_for_directory(cls, directory):
        """Load the meta.yml file from the given directory, even if it doesn't exist.

        If the directory has no project file, the loaded
        ``MetaFile`` will be empty. It won't actually be
        created on disk unless you call ``save()``.

        If the file has syntax problems, this sets the
        ``corrupted`` and ``corrupted_error_message`` properties,
        and attempts to modify the file will raise an
        exception.

        Args:
            directory (str): path to the project directory

        Returns:
            a new ``MetaFile``

        """
        path = os.path.join(directory, META_DIRECTORY, META_FILENAME)
        return CondaMetaFile(path)

    def _default_comment(self):
        return "Conda meta.yaml file"
