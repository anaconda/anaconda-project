# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Project lock file loading and manipulation."""
from __future__ import absolute_import

import os
from collections import OrderedDict

try:
    # this is the conda-packaged version of ruamel.yaml which has the
    # module renamed
    import ruamel_yaml as ryaml
except ImportError:  # pragma: no cover
    # this is the upstream version
    import ruamel.yaml as ryaml  # pragma: no cover

from anaconda_project.yaml_file import YamlFile, _CommentedMap, _block_style_all_nodes

# these are in the order we'll use them if multiple are present
possible_project_lock_file_names = ("anaconda-project-lock.yml", "anaconda-project-lock.yaml")

DEFAULT_PROJECT_LOCK_FILENAME = possible_project_lock_file_names[0]


class ProjectLockFile(YamlFile):
    """Represents the ``anaconda-project-lock.yml`` file which describes locked package versions."""

    @classmethod
    def load_for_directory(cls, directory):
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
        for name in possible_project_lock_file_names:
            path = os.path.join(directory, name)
            if os.path.isfile(path):
                return ProjectLockFile(path)
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

    def _default_content(self):
        header = (
            "This is an Anaconda project lock file.\n" +
            "The lock file locks down exact versions of all your dependencies.\n" + "\n" +
            "In most cases, this file is automatically maintained by the `anaconda-project` command or GUI tools.\n" +
            "It's best to keep this file in revision control (such as git or svn).\n" +
            "The file is in YAML format, please see http://www.yaml.org/start.html for more.\n")
        sections = OrderedDict()

        sections['locking_enabled'] = ("Set to false to ignore locked versions.")
        sections['env_specs'] = ("A key goes in here for each env spec.\n")

        # we make a big string and then parse it because I can't figure out the
        # ruamel.yaml API to insert comments in front of map keys.
        def comment_out(comment):
            return ("# " + "\n# ".join(comment.split("\n")) + "\n").replace("# \n", "#\n")

        to_parse = comment_out(header)
        for section_name, comment in sections.items():
            # future: this is if/else is silly, we should be
            # assigning these bodies up above when we assign the
            # comments.
            if section_name in ('env_specs', ):
                section_body = "  {}"
            elif section_name in ('locking_enabled', ):
                section_body = " false"
            to_parse = to_parse + "\n#\n" + comment_out(comment) + section_name + ":\n" + section_body + "\n\n\n"

        as_json = ryaml.load(to_parse, Loader=ryaml.RoundTripLoader)

        return as_json

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

    def _disable_locking(self, env_spec_name):
        """Library-internal method."""
        if env_spec_name is None:
            self.set_value(['locking_enabled'], False)
            self.unset_value(['env_specs'])
        else:
            self.set_value(['env_specs', env_spec_name, 'locked'], False)
            self.unset_value(['env_specs', env_spec_name, 'packages'])
            self.unset_value(['env_specs', env_spec_name, 'platforms'])
