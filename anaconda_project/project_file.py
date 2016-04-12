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

from anaconda_project.yaml_file import YamlFile

import ruamel.yaml as ryaml

# these are in the order we'll use them if multiple are present
possible_project_file_names = ("project.yml", "project.yaml")

DEFAULT_PROJECT_FILENAME = possible_project_file_names[0]


class ProjectFile(YamlFile):
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
        header = ("This is an Anaconda project file.\n" + "\n" +
                  "Here you can configure the requirements to run your code, such as\n" +
                  "packages, configuration, and services.\n" +
                  "If you run your code with the 'anaconda-project launch' command, or with\n" +
                  "project-aware tools such as Anaconda Navigator, the tools will be smart\n" +
                  "about checking for and meeting your requirements.\n" + "\n" +
                  "The file is in YAML format, please see http://www.yaml.org/start.html for more.\n" +
                  "(But often you don't have to edit this file by hand!\n" +
                  "Try the anaconda-project command or Anaconda Navigator to set up your project.)\n" + "\n" +
                  "If you want to edit by hand, here are some of the things you can set.\n" + "\n" +
                  "Set the 'name' key to name your project:\n" + "name: myproject\n" + "\n" +
                  "Set the 'icon' key to give your project an icon in Navigator:\n" + "icon: myicon.png\n" + "\n")

        sections = OrderedDict()

        sections['commands'] = (
            "In the commands section, list your runnable scripts, notebooks, and other code.\n" +
            "You can give each item a name, and use it with anaconda-project launch, like this:\n" +
            "    anaconda-project launch --command myscript\n"
            "Without the --command option, 'anaconda-project launch' will run the command named\n" +
            "'default', or the first command listed.\n" +
            "Any .ipynb files in the project directory are added automatically and don't need\n" +
            "to be listed here, but you can if you like.\n" + "\n" + "For example,\n" + "\n" + "commands:\n" +
            "   default:\n" + "      shell: echo \"This project is in $PROJECT_DIR\"\n" +
            "      windows: echo \"This project is in \"%PROJECT_DIR%\n" + "   myscript:\n" + "      shell: main.py\n" +
            "   my_bokeh_app:\n" + "      bokeh_app: the_app_directory_name\n" + "   my_notebook:\n" +
            "      notebook: foo.ipynb\n" + "\n" +
            "Commands may have both a Unix shell version and a Windows cmd.exe version.\n" +
            "In this example, my_notebook was automatically added as a command named\n" +
            "'foo.ipynb' but we've manually added it as 'my_notebook' also.\n")

        sections['runtime'] = (
            "In the runtime section, list any environment variables your code depends on.\n" + "\n" + "For example,\n" +
            "\n" + "runtime:\n" + "   EC2_PASSWORD: {}\n" + "   NUMBER_OF_ITERATIONS: {}\n")

        sections['downloads'] = (
            "In the downloads section, list any URLs to download to local files\n" + "before your code runs.\n" +
            "Each local filename is placed in an environment variable.\n" + "\n" + "For example,\n" + "\n" +
            "downloads:\n" + "   MY_DATA_FILE: http://example.com/data.csv\n" + "   ANOTHER_DATA_FILE: {\n" +
            "     url: http://example.com/foo.csv\n" + "     sha1: adc83b19e793491b1c6ea0fd8b46cd9f32e592fc\n" +
            "     filename: local-name-for-foo.csv\n" + "   }\n" + "\n" +
            "In this example, the MY_DATA_FILE environment variable would\n" +
            "contain the full path to a local copy of data.csv, while\n" +
            "ANOTHER_DATA_FILE would contain the full path to a local copy\n" + "named local-name-for-foo.csv\n")

        sections['dependencies'] = (
            "In the dependencies section, list any packages that must be installed\n" + "before your code runs.\n" +
            "These packages will be installed in ALL Conda environments used for\n" + "this project.\n" + "\n" +
            "For example,\n" + "dependencies:\n" + "   - bokeh=0.11.1\n" + "   - numpy\n")

        sections['channels'] = (
            "In the channels section, list any Conda channel URLs to be searched\n" +
            "for packages. These channels will be used by ALL Conda environments\n" + "this project runs in.\n" + "\n" +
            "For example,\n" + "\n" + "channels:\n" + "   - https://conda.anaconda.org/asmeurer\n")

        sections['environments'] = (
            "If you like, you can define multiple, named Conda environments.\n" +
            "There's an implicit environment called 'default', which you can\n" +
            "tune by naming it explicitly here. When you launch a command, use\n" +
            "the --environment option to choose an environment.\n" +
            "   anaconda-project launch --environment python27\n" + "\n" +
            "Each environment may have 'dependencies' or 'channels' sub-sections\n" +
            "which are combined with any global 'dependencies' or 'channels'.\n" + "\n" + "For example,\n" + "\n" +
            "environments:\n" + "  default:\n" + "    dependencies:\n" + "      - bokeh\n" + "    channels:\n" +
            "      - https://conda.anaconda.org/asmeurer\n" + "  python27:\n" + "    dependencies:\n" +
            "      - python=2.7\n"
            "\n")

        # we make a big string and then parse it because I can't figure out the
        # ruamel.yaml API to insert comments in front of map keys.
        def comment_out(comment):
            return ("# " + "\n# ".join(comment.split("\n")) + "\n").replace("# \n", "#\n")

        to_parse = comment_out(header)
        for section_name, comment in sections.items():
            if section_name == 'channels' or section_name == 'dependencies':
                section_body = "  []"
            else:
                section_body = "  {}"
            to_parse = to_parse + "\n#\n" + comment_out(comment) + section_name + ":\n" + section_body + "\n\n\n"

        return ryaml.load(to_parse, Loader=ryaml.RoundTripLoader)

    @property
    def name(self):
        """Get the "name" field from the file."""
        return self.get_value('name', default=None)

    @name.setter
    def name(self, value):
        """Set the "name" field in the file."""
        self.set_value('name', value)

    @property
    def icon(self):
        """Get the "icon" field from the file."""
        return self.get_value('icon', default=None)

    @icon.setter
    def icon(self, value):
        """Set the "icon" field in the file."""
        self.set_value('icon', value)
