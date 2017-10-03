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
from collections import OrderedDict
import json

from anaconda_project.yaml_file import YamlFile
from anaconda_project.env_spec import EnvSpec
import anaconda_project.internal.conda_api as conda_api

try:
    # this is the conda-packaged version of ruamel.yaml which has the
    # module renamed
    import ruamel_yaml as ryaml
except ImportError:  # pragma: no cover
    # this is the upstream version
    import ruamel.yaml as ryaml  # pragma: no cover

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

    @classmethod
    def load_for_directory(cls, directory, default_env_specs_func=_empty_default_env_spec):
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
            default_env_specs_func (function makes list of EnvSpec): if file is created, use these

        Returns:
            a new ``ProjectFile``

        """
        for name in possible_project_file_names:
            path = os.path.join(directory, name)
            if os.path.isfile(path):
                return ProjectFile(path)
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
            default_env_specs_func (function makes list of EnvSpec): if file is created, use these

        """
        self._default_env_specs_func = default_env_specs_func
        super(ProjectFile, self).__init__(filename)

    def _default_content(self):
        header = (
            "This is an Anaconda project file.\n" + "\n" + "Here you can describe your project and how to run it.\n" +
            "Use `anaconda-project run` to run the project.\n" +
            "The file is in YAML format, please see http://www.yaml.org/start.html for more.\n")
        sections = OrderedDict()

        sections['name'] = ("Set the 'name' key to name your project\n")

        sections['icon'] = ("Set the 'icon' key to give your project an icon\n")

        sections['description'] = ("Set a one-sentence-or-so 'description' key with project details\n")

        sections['commands'] = ("In the commands section, list your runnable scripts, notebooks, and other code.\n" +
                                "Use `anaconda-project add-command` to add commands.\n")

        sections['variables'] = ("In the variables section, list any environment variables your code depends on.\n"
                                 "Use `anaconda-project add-variable` to add variables.\n")

        sections['services'] = (
            "In the services section, list any services that should be\n" + "available before your code runs.\n" +
            "Use `anaconda-project add-service` to add services.\n")

        sections['downloads'] = ("In the downloads section, list any URLs to download to local files\n" +
                                 "before your code runs.\n" + "Use `anaconda-project add-download` to add downloads.\n")

        sections['packages'] = ("In the packages section, list any packages that must be installed\n" +
                                "before your code runs.\n" + "Use `anaconda-project add-packages` to add packages.\n")

        sections['channels'] = ("In the channels section, list any Conda channel URLs to be searched\n" +
                                "for packages.\n" + "\n" + "For example,\n" + "\n" + "channels:\n" + "   - mychannel\n")

        sections['platforms'] = ("In the platforms section, list platforms the project should work on\n" +
                                 "Examples: \"linux-64\", \"osx-64\", \"win-64\"\n" +
                                 "Use `anaconda-project add-platforms` to add platforms.\n")

        sections['env_specs'] = (
            "You can define multiple, named environment specs.\n" + "Each inherits any global packages or channels,\n" +
            "but can have its own unique ones also.\n" +
            "Use `anaconda-project add-env-spec` to add environment specs.\n")

        assert self._default_env_specs_func is not None
        default_env_specs = self._default_env_specs_func()
        assert default_env_specs is not None

        # we make a big string and then parse it because I can't figure out the
        # ruamel.yaml API to insert comments in front of map keys.
        def comment_out(comment):
            return ("# " + "\n# ".join(comment.split("\n")) + "\n").replace("# \n", "#\n")

        to_parse = comment_out(header)
        for section_name, comment in sections.items():
            # future: this is if/else is silly, we should be
            # assigning these bodies up above when we assign the
            # comments.
            if section_name == 'name':
                default_name = os.path.basename(os.path.dirname(self.filename))
                section_body = " " + json.dumps(default_name)
            elif section_name in ('icon', 'description'):
                section_body = ""  # empty body means null, not empty string
            elif section_name in ('channels', 'packages'):
                section_body = "  []"
            elif section_name == 'platforms':
                platforms = conda_api.default_platforms_with_current()
                section_body = "  [" + ", ".join(platforms) + "]"
            else:
                section_body = "  {}"
            to_parse = to_parse + "\n#\n" + comment_out(comment) + section_name + ":\n" + section_body + "\n\n\n"

        as_json = ryaml.load(to_parse, Loader=ryaml.RoundTripLoader)

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

        return as_json
