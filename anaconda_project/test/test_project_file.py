# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
import codecs
import os

from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.test.project_utils import assert_identical_except_blank_lines
from anaconda_project.project_file import ProjectFile, DEFAULT_PROJECT_FILENAME, possible_project_file_names
from anaconda_project.env_spec import EnvSpec
from anaconda_project.internal import conda_api

expected_default_file_template = """# This is an Anaconda project file.
#
# Here you can describe your project and how to run it.
# Use `anaconda-project run` to run the project.
# The file is in YAML format, please see http://www.yaml.org/start.html for more.
#

#
# Set the 'name' key to name your project
#
name: <NAME>
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
%s%s%s%s"""

empty_global_packages = """#
# In the packages section, list any packages that must be installed
# before your code runs.
# Use `anaconda-project add-packages` to add packages.
#
packages: []
"""

empty_global_channels = """#
# In the channels section, list any Conda channel URLs to be searched
# for packages.
#
# For example,
#
# channels:
#    - mychannel
#
channels: []
"""

default_global_platforms = """#
# In the platforms section, list platforms the project should work on
# Examples: "linux-64", "osx-64", "win-64"
# Use `anaconda-project add-platforms` to add platforms.
#
platforms:
{platforms}
""".format(platforms='\n'.join(['- {p}'.format(p=p) for p in conda_api.default_platforms_with_current()]))

empty_default_env_specs = """#
# You can define multiple, named environment specs.
# Each inherits any global packages or channels,
# but can have its own unique ones also.
# Use `anaconda-project add-env-spec` to add environment specs.
#
env_specs:
  default:
    packages: []
    channels: []
"""


def _make_file_contents(packages, channels, platforms, env_specs):
    return expected_default_file_template % (packages, channels, platforms, env_specs)


expected_default_file = _make_file_contents(packages=empty_global_packages,
                                            channels=empty_global_channels,
                                            platforms=default_global_platforms,
                                            env_specs=empty_default_env_specs)


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
            expected = expected_default_file.replace("<NAME>", os.path.basename(dirname))
            assert_identical_except_blank_lines(expected, contents)

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


def _use_existing_project_file_from_subdir(relative_name):
    def check_file(dirname):
        filename = os.path.join(dirname, relative_name)
        assert os.path.exists(filename)
        subdir = os.path.join(dirname, 'subdir')
        os.makedirs(subdir)
        project_file = ProjectFile.load_for_directory(subdir)
        value = project_file.get_value(["a", "b"])
        assert "c" == value

    with_directory_contents({relative_name: "a:\n  b: c"}, check_file)


def test_use_existing_project_file_from_subdir():
    _use_existing_project_file_from_subdir(DEFAULT_PROJECT_FILENAME)


def test_load_directory_without_project_file():
    def read_missing_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert not os.path.exists(filename)
        project_file = ProjectFile.load_for_directory(dirname)
        assert project_file is not None
        assert not os.path.exists(filename)
        assert project_file.get_value(["a", "b"]) is None

    with_directory_contents(dict(), read_missing_file)


anaconda_global_packages = """#
# In the packages section, list any packages that must be installed
# before your code runs.
# Use `anaconda-project add-packages` to add packages.
#
packages:
- anaconda
"""

mychannel_global_channels = """#
# In the channels section, list any Conda channel URLs to be searched
# for packages.
#
# For example,
#
# channels:
#    - mychannel
#
channels:
- mychannel
"""

abc_empty_env_spec = """#
# You can define multiple, named environment specs.
# Each inherits any global packages or channels,
# but can have its own unique ones also.
# Use `anaconda-project add-env-spec` to add environment specs.
#
env_specs:
  abc:
    description: ABC
    packages: []
    channels: []
"""

expected_one_env_spec_contents = _make_file_contents(packages=anaconda_global_packages,
                                                     channels=mychannel_global_channels,
                                                     platforms=default_global_platforms,
                                                     env_specs=abc_empty_env_spec)


def test_create_missing_project_file_one_default_env_spec():
    def create_file(dirname):
        def default_env_specs_func():
            return [
                EnvSpec(name='abc',
                        conda_packages=['anaconda'],
                        pip_packages=[],
                        channels=['mychannel'],
                        description="ABC",
                        inherit_from_names=(),
                        inherit_from=())
            ]

        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert not os.path.exists(filename)
        project_file = ProjectFile.load_for_directory(dirname, default_env_specs_func=default_env_specs_func)
        assert project_file is not None
        assert not os.path.exists(filename)
        project_file.save()
        assert os.path.exists(filename)
        with codecs.open(filename, 'r', 'utf-8') as file:
            contents = file.read()
            expected = expected_one_env_spec_contents.replace("<NAME>", os.path.basename(dirname))
            assert_identical_except_blank_lines(expected, contents)

    with_directory_contents(dict(), create_file)


def test_create_missing_project_file_one_default_env_spec_deps():
    def create_file(dirname):
        def default_env_specs_func():
            return [
                EnvSpec(name='abc',
                        conda_packages=['anaconda'],
                        pip_packages=[],
                        channels=['mychannel'],
                        description="ABC",
                        inherit_from_names=(),
                        inherit_from=())
            ]

        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert not os.path.exists(filename)
        project_file = ProjectFile.load_for_directory(dirname, default_env_specs_func=default_env_specs_func)
        assert project_file is not None
        assert not os.path.exists(filename)
        project_file.save()
        assert os.path.exists(filename)
        print(filename)
        with codecs.open(filename, 'r', 'utf-8') as file:
            contents = file.read()
            contents = contents.replace('packages', 'dependencies')
            expected_one_env_spec_contents_deps = expected_one_env_spec_contents.replace('packages', 'dependencies')
            expected = expected_one_env_spec_contents_deps.replace("<NAME>", os.path.basename(dirname))
            assert_identical_except_blank_lines(expected, contents)

    with_directory_contents(dict(), create_file)


abc_xyz_env_specs = """#
# You can define multiple, named environment specs.
# Each inherits any global packages or channels,
# but can have its own unique ones also.
# Use `anaconda-project add-env-spec` to add environment specs.
#
env_specs:
  abc:
    description: ABC
    packages:
    - anaconda
    channels:
    - mychannel
  xyz:
    description: XYZ
    packages:
    - foo
    channels:
    - bar
"""

expected_two_env_spec_contents = _make_file_contents(packages=empty_global_packages,
                                                     channels=empty_global_channels,
                                                     platforms=default_global_platforms,
                                                     env_specs=abc_xyz_env_specs)


def test_create_missing_project_file_two_default_env_specs():
    def create_file(dirname):
        def default_env_specs_func():
            return [
                EnvSpec(name='abc',
                        conda_packages=['anaconda'],
                        pip_packages=[],
                        channels=['mychannel'],
                        description="ABC",
                        inherit_from_names=(),
                        inherit_from=()),
                EnvSpec(name='xyz',
                        conda_packages=['foo'],
                        pip_packages=[],
                        channels=['bar'],
                        description="XYZ",
                        inherit_from_names=(),
                        inherit_from=())
            ]

        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert not os.path.exists(filename)
        project_file = ProjectFile.load_for_directory(dirname, default_env_specs_func=default_env_specs_func)
        assert project_file is not None
        assert not os.path.exists(filename)
        project_file.save()
        assert os.path.exists(filename)
        with codecs.open(filename, 'r', 'utf-8') as file:
            contents = file.read()
            expected = expected_two_env_spec_contents.replace("<NAME>", os.path.basename(dirname))
            assert_identical_except_blank_lines(expected, contents)

    with_directory_contents(dict(), create_file)


def test_create_missing_project_file_two_default_env_specs_deps():
    def create_file(dirname):
        def default_env_specs_func():
            return [
                EnvSpec(name='abc',
                        conda_packages=['anaconda'],
                        pip_packages=[],
                        channels=['mychannel'],
                        description="ABC",
                        inherit_from_names=(),
                        inherit_from=()),
                EnvSpec(name='xyz',
                        conda_packages=['foo'],
                        pip_packages=[],
                        channels=['bar'],
                        description="XYZ",
                        inherit_from_names=(),
                        inherit_from=())
            ]

        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert not os.path.exists(filename)
        project_file = ProjectFile.load_for_directory(dirname, default_env_specs_func=default_env_specs_func)
        assert project_file is not None
        assert not os.path.exists(filename)
        project_file.save()
        assert os.path.exists(filename)
        with codecs.open(filename, 'r', 'utf-8') as file:
            contents = file.read()
            contents = contents.replace('packages', 'dependencies')
            expected_two_env_spec_contents_deps = expected_two_env_spec_contents.replace('packages', 'dependencies')
            expected = expected_two_env_spec_contents_deps.replace("<NAME>", os.path.basename(dirname))
            assert_identical_except_blank_lines(expected, contents)

    with_directory_contents(dict(), create_file)
