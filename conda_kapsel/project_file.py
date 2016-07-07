# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Project file loading and manipulation."""
from __future__ import absolute_import

import os
from collections import OrderedDict

from conda_kapsel.yaml_file import YamlFile

try:
    # this is the conda-packaged version of ruamel.yaml which has the
    # module renamed
    import ruamel_yaml as ryaml
except ImportError:  # pragma: no cover
    # this is the upstream version
    import ruamel.yaml as ryaml  # pragma: no cover

# these are in the order we'll use them if multiple are present
possible_project_file_names = ("kapsel.yml", "kapsel.yaml")

DEFAULT_PROJECT_FILENAME = possible_project_file_names[0]


class ProjectFile(YamlFile):
    """Represents the ``kapsel.yml`` file which describes the project across machines/users.

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
        for name in possible_project_file_names:
            path = os.path.join(directory, name)
            if os.path.isfile(path):
                return ProjectFile(path)
        return ProjectFile(os.path.join(directory, DEFAULT_PROJECT_FILENAME))

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

    def _default_content(self):
        header = (
            "This is an Anaconda project file.\n" + "\n" + "Here you can describe your project and how to run it.\n" +
            "Use `conda-kapsel run` to run the project.\n" +
            "The file is in YAML format, please see http://www.yaml.org/start.html for more.\n")
        sections = OrderedDict()

        sections['name'] = ("Set the 'name' key to name your project\n")

        sections['icon'] = ("Set the 'icon' key to give your project an icon\n")

        sections['commands'] = ("In the commands section, list your runnable scripts, notebooks, and other code.\n" +
                                "Use `conda-kapsel add-command` to add commands.\n")

        sections['variables'] = ("In the variables section, list any environment variables your code depends on.\n"
                                 "Use `conda-kapsel add-variable` to add variables.\n")

        sections['services'] = (
            "In the services section, list any services that should be\n" + "available before your code runs.\n" +
            "Use `conda-kapsel add-service` to add services.\n")

        sections['downloads'] = ("In the downloads section, list any URLs to download to local files\n" +
                                 "before your code runs.\n" + "Use `conda-kapsel add-download` to add downloads.\n")

        sections['packages'] = ("In the packages section, list any packages that must be installed\n" +
                                "before your code runs.\n" + "Use `conda-kapsel add-packages` to add packages.\n")

        sections['channels'] = (
            "In the channels section, list any Conda channel URLs to be searched\n" + "for packages.\n" + "\n" +
            "For example,\n" + "\n" + "channels:\n" + "   - https://conda.anaconda.org/asmeurer\n")

        sections['env_specs'] = ("If you like, you can define multiple, named environment specs.\n" +
                                 "There's an implicit environment spec called 'default', which you can\n" +
                                 "tune by naming it explicitly here.\n"
                                 "Use `conda-kapsel add-env-spec` to add environment specs.\n")

        # we make a big string and then parse it because I can't figure out the
        # ruamel.yaml API to insert comments in front of map keys.
        def comment_out(comment):
            return ("# " + "\n# ".join(comment.split("\n")) + "\n").replace("# \n", "#\n")

        to_parse = comment_out(header)
        for section_name, comment in sections.items():
            if section_name in ('name', 'icon'):
                section_body = ""
            elif section_name in ('channels', 'packages'):
                section_body = "  []"
            else:
                section_body = "  {}"
            to_parse = to_parse + "\n#\n" + comment_out(comment) + section_name + ":\n" + section_body + "\n\n\n"

        return ryaml.load(to_parse, Loader=ryaml.RoundTripLoader)
