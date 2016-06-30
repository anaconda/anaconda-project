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
#    - https://conda.anaconda.org/asmeurer
#
channels: []
#
# If you like, you can define multiple, named environment specs.
# There's an implicit environment spec called 'default', which you can
# tune by naming it explicitly here.
# Use `anaconda-project add-env-spec` to add environment specs.
#
env_specs: {}
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
