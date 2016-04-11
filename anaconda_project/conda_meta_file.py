# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""conda.recipe/meta.yaml file loading and manipulation."""
from __future__ import absolute_import

import os

from anaconda_project.yaml_file import YamlFile

META_DIRECTORY = "conda.recipe"

# here we don't support .yml because conda build doesn't either
possible_meta_file_names = ('meta.yaml', 'conda.yaml')

DEFAULT_META_FILENAME = possible_meta_file_names[0]

DEFAULT_RELATIVE_META_PATH = os.path.join(META_DIRECTORY, DEFAULT_META_FILENAME)


class CondaMetaFile(YamlFile):
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
        for name in possible_meta_file_names:
            path = os.path.join(directory, META_DIRECTORY, name)
            if os.path.isfile(path):
                return CondaMetaFile(path)
        return CondaMetaFile(os.path.join(directory, DEFAULT_RELATIVE_META_PATH))

    def _default_comment(self):
        return "Conda meta.yaml file"

    @property
    def app_entry(self):
        """Get the command to run the app, as a string.

        This is under "app: entry: command" in meta.yaml.

        Conda parses this by splitting on whitespace, then
        replacing the string "${PREFIX}" inside each arg with the
        environment prefix, then replacing "argv[0]" with the full
        path. See conda/misc.py::launch().

        Returns:
            None if not found

        """
        return self.get_value(['app', 'entry'], default=None)

    @property
    def name(self):
        """Get the "package: name" field from the file."""
        return self.get_value(['package', 'name'], default=None)

    @property
    def icon(self):
        """Get the "app: icon" field from the file."""
        return self.get_value(['app', 'icon'], default=None)
