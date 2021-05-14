# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Project lock file loading and manipulation."""
from __future__ import absolute_import

import os

from anaconda_project.yaml_file import YamlFile, _CommentedMap, _block_style_all_nodes

# these are in the order we'll use them if multiple are present
possible_project_lock_file_names = ("anaconda-project-lock.yml", "anaconda-project-lock.yaml")

DEFAULT_PROJECT_LOCK_FILENAME = possible_project_lock_file_names[0]


class ProjectLockFile(YamlFile):
    """Represents the ``anaconda-project-lock.yml`` file which describes locked package versions."""

    template = '''
# This is an Anaconda project lock file.
# The lock file locks down exact versions of all your dependencies.
#
# In most cases, this file is automatically maintained by the `anaconda-project` command or GUI tools.
# It's best to keep this file in revision control (such as git or svn).
# The file is in YAML format, please see http://www.yaml.org/start.html for more.
#

#
# Set to false to ignore locked versions.
#
locking_enabled: false

#
# A key goes in here for each env spec.
#
env_specs: {}
'''

    @classmethod
    def load_for_directory(cls, directory, scan_parents=True):
        """Load the project lock file from the given directory, even if it doesn't exist.

        If the directory has no project file, the loaded
        ``ProjectLockFile`` will be empty. It won't actually be
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
            a new ``ProjectLockFile``

        """
        current_dir = directory
        while current_dir != os.path.realpath(os.path.dirname(current_dir)):
            for name in possible_project_lock_file_names:
                path = os.path.join(current_dir, name)
                if os.path.isfile(path):
                    return ProjectLockFile(path)

            if scan_parents:
                current_dir = os.path.dirname(os.path.abspath(current_dir))
                continue
            else:
                break

        # No file was found, create a new one
        return ProjectLockFile(os.path.join(directory, DEFAULT_PROJECT_LOCK_FILENAME))

    def __init__(self, filename):
        """Construct a ``ProjectLockFile`` with the given filename.

        It's easier to use ``ProjectLockFile.load_for_directory()`` in most cases.

        If the file has syntax problems, this sets the
        ``corrupted`` and ``corrupted_error_message`` properties,
        and attempts to modify the file will raise an
        exception. If the project file has semantic problems, they
        are not detected by this class but are reported by the
        ``Project`` class.

        Args:
            filename (str): path to the project file
        """
        super(ProjectLockFile, self).__init__(filename)

    def _save_default_content(self):
        # We don't want to save empty lock files.
        return False

    def _set_lock_set_hash(self, env_spec_name, env_spec_hash):
        """Library-internal method."""
        self.set_value(['env_specs', env_spec_name, 'env_spec_hash'], env_spec_hash)

    def _set_lock_set(self, env_spec_name, lock_set, all_names):
        """Library-internal method."""
        assert env_spec_name is not None
        assert lock_set is not None
        assert all_names is not None
        assert env_spec_name in all_names

        # if all locking is disabled, switch to individually
        # disabling each env spec so we can enable the one
        # we care about here.
        for_all = self.get_value(['locking_enabled'], True)
        if not for_all:
            self.set_value(['locking_enabled'], True)

            new_env_specs = self.get_value(['env_specs'], None)
            if new_env_specs is None:
                new_env_specs = _CommentedMap()
                _block_style_all_nodes(new_env_specs)
                self.set_value(['env_specs'], new_env_specs)

            for name in all_names:
                if name == env_spec_name:
                    continue
                single_env = new_env_specs.get(name, None)
                if single_env is None:
                    single_env = _CommentedMap()
                    _block_style_all_nodes(single_env)
                    new_env_specs[name] = single_env

                single_env['locked'] = False

        # now set up the one env
        as_json = lock_set.to_json()
        self.set_value(['env_specs', env_spec_name], as_json)

    def _add_pip_packages(self, env_spec_name, pip_packages):
        self.set_value(['env_specs', env_spec_name, 'packages', 'pip'], pip_packages)

    def _disable_locking(self, env_spec_name):
        """Library-internal method."""
        if env_spec_name is None:
            self.set_value(['locking_enabled'], False)
            self.unset_value(['env_specs'])
        else:
            self.set_value(['env_specs', env_spec_name, 'locked'], False)
            self.unset_value(['env_specs', env_spec_name, 'packages'])
            self.unset_value(['env_specs', env_spec_name, 'platforms'])
