# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
import codecs
import os

from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.project_file import ProjectFile, DEFAULT_PROJECT_FILENAME, possible_project_file_names

expected_default_file = """# This is an Anaconda project file.
#
# Here you can configure the requirements to run your code, such as
# packages, configuration, and services.
# If you run your code with the 'anaconda-project launch' command, or with
# project-aware tools such as Anaconda Navigator, the tools will be smart
# about checking for and meeting your requirements.
#
# The file is in YAML format, please see http://www.yaml.org/start.html for more.
# (But often you don't have to edit this file by hand!
# Try the anaconda-project command or Anaconda Navigator to set up your project.)
#
# If you want to edit by hand, here are some of the things you can set.
#
# Set the 'name' key to name your project:
# name: myproject
#
# Set the 'icon' key to give your project an icon in Navigator:
# icon: myicon.png
#
#

#
# In the commands section, list your runnable scripts, notebooks, and other code.
# You can give each item a name, and use it with anaconda-project launch, like this:
#     anaconda-project launch --command myscript
# Without the --command option, 'anaconda-project launch' will run the command named
# 'default', or the first command listed.
# Any .ipynb files in the project directory are added automatically and don't need
# to be listed here, but you can if you like.
#
# For example,
#
# commands:
#    default:
#       shell: echo "This project is in $PROJECT_DIR"
#       windows: echo "This project is in "%PROJECT_DIR%
#    myscript:
#       shell: main.py
#    my_bokeh_app:
#       bokeh_app: the_app_directory_name
#    my_notebook:
#       notebook: foo.ipynb
#
# Commands may have both a Unix shell version and a Windows cmd.exe version.
# In this example, my_notebook was automatically added as a command named
# 'foo.ipynb' but we've manually added it as 'my_notebook' also.
#
commands: {}
#
# In the runtime section, list any environment variables your code depends on.
#
# For example,
#
# runtime:
#    EC2_PASSWORD: null
#    NUMBER_OF_ITERATIONS: null
#
# If you give a value other than null for the variable, that value will be the default
# for everyone who runs this project.
# You can also set a local value (not shared with others) in project-local.yml.
#
runtime: {}
#
# In the downloads section, list any URLs to download to local files
# before your code runs.
# Each local filename is placed in an environment variable.
#
# For example,
#
# downloads:
#    MY_DATA_FILE: http://example.com/data.csv
#    ANOTHER_DATA_FILE: {
#      url: http://example.com/foo.csv
#      sha1: adc83b19e793491b1c6ea0fd8b46cd9f32e592fc
#      filename: local-name-for-foo.csv
#    }
#
# In this example, the MY_DATA_FILE environment variable would
# contain the full path to a local copy of data.csv, while
# ANOTHER_DATA_FILE would contain the full path to a local copy
# named local-name-for-foo.csv
#
downloads: {}
#
# In the dependencies section, list any packages that must be installed
# before your code runs.
# These packages will be installed in ALL Conda environments used for
# this project.
#
# For example,
# dependencies:
#    - bokeh=0.11.1
#    - numpy
#
dependencies: []
#
# In the channels section, list any Conda channel URLs to be searched
# for packages. These channels will be used by ALL Conda environments
# this project runs in.
#
# For example,
#
# channels:
#    - https://conda.anaconda.org/asmeurer
#
channels: []
#
# If you like, you can define multiple, named Conda environments.
# There's an implicit environment called 'default', which you can
# tune by naming it explicitly here. When you launch a command, use
# the --environment option to choose an environment.
#    anaconda-project launch --environment python27
#
# Each environment may have 'dependencies' or 'channels' sub-sections
# which are combined with any global 'dependencies' or 'channels'.
#
# For example,
#
# environments:
#   default:
#     dependencies:
#       - bokeh
#     channels:
#       - https://conda.anaconda.org/asmeurer
#   python27:
#     dependencies:
#       - python=2.7
#
#
environments: {}
"""


def test_create_missing_project_file():
    def create_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert not os.path.exists(filename)
        project_file = ProjectFile.load_for_directory(dirname)
        assert project_file is not None
        assert not os.path.exists(filename)
        project_file.save()
        assert os.path.exists(filename)
        with codecs.open(filename, 'r', 'utf-8') as file:
            contents = file.read()
            assert expected_default_file == contents

    with_directory_contents(dict(), create_file)


def _use_existing_project_file(relative_name):
    def check_file(dirname):
        filename = os.path.join(dirname, relative_name)
        assert os.path.exists(filename)
        project_file = ProjectFile.load_for_directory(dirname)
        value = project_file.get_value(["a", "b"])
        assert "c" == value

    with_directory_contents({relative_name: "a:\n  b: c"}, check_file)


def test_use_existing_project_file_default_name():
    _use_existing_project_file(DEFAULT_PROJECT_FILENAME)


def test_use_existing_project_file_all_names():
    for name in possible_project_file_names:
        _use_existing_project_file(name)


def test_load_directory_without_project_file():
    def read_missing_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert not os.path.exists(filename)
        project_file = ProjectFile.load_for_directory(dirname)
        assert project_file is not None
        assert not os.path.exists(filename)
        assert project_file.get_value(["a", "b"]) is None

    with_directory_contents(dict(), read_missing_file)
