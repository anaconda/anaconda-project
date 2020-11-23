# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Project file loading and manipulation."""
from __future__ import absolute_import

import os

from anaconda_project.yaml_file import YamlFile
from anaconda_project.env_spec import EnvSpec
import anaconda_project.internal.conda_api as conda_api

# these are in the order we'll use them if multiple are present
possible_project_file_names = ("anaconda-project.yml", "anaconda-project.yaml", "kapsel.yml", "kapsel.yaml")

DEFAULT_PROJECT_FILENAME = possible_project_file_names[0]


def _empty_default_env_spec():
    return (EnvSpec(name="default", channels=[], conda_packages=()), )


class ProjectFile(YamlFile):
    """Represents the ``anaconda-project.yml`` file which describes the project across machines/users.

    State that's specific to a machine/user/checkout/deployment
    should instead be in ``LocalStateFile``.  ``ProjectFile``
    would normally be checked in to source control or otherwise
    act as a shared resource.

    Be careful with creating your own instance of this class,
    because you have to think about when other code might load or
    save in a way that conflicts with your loads and saves.

    """

    template = '''
# This is an Anaconda project file.
#
# Here you can describe your project and how to run it.
# Use `anaconda-project run` to run the project.
# The file is in YAML format, please see http://www.yaml.org/start.html for more.
#

#
# Set the 'name' key to name your project
#
name:

#
# Set the 'icon' key to give your project an icon
#
icon:

#
# Set a one-sentence-or-so 'description' key with project details
#
description:

#
# In the commands section, list your runnable scripts, notebooks, and other code.
# Use `anaconda-project add-command` to add commands.
#
commands: {}

#
# In the variables section, list any environment variables your code depends on.
# Use `anaconda-project add-variable` to add variables.
#
variables: {}

#
# In the services section, list any services that should be
# available before your code runs.
# Use `anaconda-project add-service` to add services.
#
services: {}

#
# In the downloads section, list any URLs to download to local files
# before your code runs.
# Use `anaconda-project add-download` to add downloads.
#
downloads: {}

#
# In the packages section, list any packages that must be installed
# before your code runs.
# Use `anaconda-project add-packages` to add packages.
#
packages: []

#
# In the channels section, list any Conda channel URLs to be searched
# for packages.
#
# For example,
#
# channels:
#    - mychannel
#
channels: []

#
# In the platforms section, list platforms the project should work on
# Examples: "linux-64", "osx-64", "win-64"
# Use `anaconda-project add-platforms` to add platforms.
#
platforms: []

#
# You can define multiple, named environment specs.
# Each inherits any global packages or channels,
# but can have its own unique ones also.
# Use `anaconda-project add-env-spec` to add environment specs.
#
env_specs: {}
'''

    @classmethod
    def load_for_directory(cls, directory, default_env_specs_func=_empty_default_env_spec, scan_parents=True):
        """Load the project file from the given directory, even if it doesn't exist.

        If the directory has no project file, and the project file
        cannot be found in any parent directory, the loaded
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
            default_env_specs_func (function makes list of EnvSpec): if file is created, use these
            scan_parents (bool): if True search for anaconda-project.yml file in parent directories
                                 If one is found change the directory_path to its location.

        Returns:
            a new ``ProjectFile``

        """
        current_dir = directory
        while current_dir != os.path.realpath(os.path.dirname(current_dir)):
            for name in possible_project_file_names:
                path = os.path.join(current_dir, name)
                if os.path.isfile(path):
                    return ProjectFile(path)

            if scan_parents:
                current_dir = os.path.dirname(os.path.abspath(current_dir))
                continue
            else:
                break

        # No file was found, create a new one
        return ProjectFile(os.path.join(directory, DEFAULT_PROJECT_FILENAME), default_env_specs_func)

    def __init__(self, filename, default_env_specs_func=_empty_default_env_spec):
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
        self._default_env_specs_func = default_env_specs_func
        self.project_dir = os.path.dirname(filename)
        super(ProjectFile, self).__init__(filename)

    def _fill_default_content(self, as_json):
        as_json['name'] = os.path.basename(os.path.dirname(self.filename))
        as_json['platforms'].extend(conda_api.default_platforms_with_current())

        assert self._default_env_specs_func is not None
        default_env_specs = self._default_env_specs_func()
        assert default_env_specs is not None
        for env_spec in default_env_specs:
            as_json['env_specs'][env_spec.name] = env_spec.to_json()

        if len(default_env_specs) == 1:
            # if there's only one env spec, keep it for name/description
            # and put the packages and channels up in the global sections
            spec_name = next(iter(as_json['env_specs']))
            spec_json = as_json['env_specs'][spec_name]

            def move_list_elements(src, dest):
                # we want to preserve the dest list object with comments
                del dest[:]
                dest.extend(src)
                del src[:]

            if 'packages' in spec_json:
                move_list_elements(spec_json['packages'], as_json['packages'])
            if 'channels' in spec_json:
                move_list_elements(spec_json['channels'], as_json['channels'])
            if 'platforms' in spec_json:
                move_list_elements(spec_json['platforms'], as_json['platforms'])
