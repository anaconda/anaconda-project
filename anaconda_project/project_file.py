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

try:
    # this is the conda-packaged version of ruamel.yaml which has the
    # module renamed
    import ruamel_yaml as ryaml
except ImportError:  # pragma: no cover
    # this is the upstream version
    import ruamel.yaml as ryaml  # pragma: no cover

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
                  "If you run your code with the 'anaconda-project run' command, or with\n" +
                  "project-aware tools such as Anaconda Navigator, the tools will be smart\n" +
                  "about checking for and meeting your requirements.\n" + "\n" +
                  "The file is in YAML format, please see http://www.yaml.org/start.html for more.\n" +
                  "(But often you don't have to edit this file by hand!\n" +
                  "Try the anaconda-project command or Anaconda Navigator to set up your project.)\n")

        sections = OrderedDict()

        sections['name'] = ("Set the 'name' key to name your project:\n" + "name: myproject\n")

        sections['icon'] = ("Set the 'icon' key to give your project an icon in Navigator:\n" + "icon: myicon.png\n")

        sections['commands'] = (
            "In the commands section, list your runnable scripts, notebooks, and other code.\n" +
            "You can give each item a name, and use it with anaconda-project run, like this:\n" +
            "    anaconda-project run --command myscript\n"
            "Without the --command option, 'anaconda-project run' will run the command named\n" +
            "'default', or the first command listed.\n" +
            "Any .ipynb files in the project directory are added automatically and don't need\n" +
            "to be listed here, but you can if you like.\n" + "\n" + "For example,\n" + "\n" + "commands:\n" +
            "   default:\n" + "      unix: echo \"This project is in $PROJECT_DIR\"\n" +
            "      windows: echo \"This project is in \"%PROJECT_DIR%\n" + "   myscript:\n" + "      unix: main.py\n" +
            "   my_bokeh_app:\n" + "      bokeh_app: the_app_directory_name\n" + "   my_notebook:\n" +
            "      notebook: foo.ipynb\n" + "\n" +
            "Commands may have both a Unix shell version and a Windows cmd.exe version.\n" +
            "In this example, my_notebook was automatically added as a command named\n" +
            "'foo.ipynb' but we've manually added it as 'my_notebook' also.\n" + "\n" +
            "If you prefer, add commands using anaconda-project like this:\n" +
            "    anaconda-project add-command --type=bokeh_app myappname myappdir\n")

        sections['variables'] = (
            "In the variables section, list any environment variables your code depends on.\n" + "\n" +
            "For example,\n\n" + "variables:\n" + "   EC2_PASSWORD: null\n" + "   NUMBER_OF_ITERATIONS: null\n\n" +
            "If you give a value other than null for the variable, that value will be the default\n" +
            "for everyone who runs this project.\n" +
            "You can also set a local value (not shared with others) in project-local.yml.\n")

        sections['services'] = (
            "In the services section, list any services that should be\n" +
            "available before your code runs. Each service's address\n" +
            "will be provided to your code in an environment variable.\n" + "\n" + "For example,\n" + "\n" +
            "services:\n" + "   REDIS_URL: redis\n" + "   # the above can be written more verbosely\n" +
            "   REDIS_URL2: { type: redis }\n" + "   # in the long form, you can specify options\n" +
            "   REDIS_URL3: { type: redis, default: \"redis://localhost:123456\" }\n" + "\n" +
            "Services can be added with anaconda-project:\n" + "   anaconda-project add-service redis\n")

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
            "tune by naming it explicitly here. When you run a command, use\n" +
            "the --environment option to choose an environment.\n" +
            "   anaconda-project run --environment python27\n\n" +
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
            if section_name in ('name', 'icon'):
                section_body = ""
            elif section_name in ('channels', 'dependencies'):
                section_body = "  []"
            else:
                section_body = "  {}"
            to_parse = to_parse + "\n#\n" + comment_out(comment) + section_name + ":\n" + section_body + "\n\n\n"

        return ryaml.load(to_parse, Loader=ryaml.RoundTripLoader)
