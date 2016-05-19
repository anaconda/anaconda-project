# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from copy import deepcopy
from distutils.spawn import find_executable
import os
import platform
import stat
import subprocess

import pytest

from anaconda_project.conda_meta_file import DEFAULT_RELATIVE_META_PATH, META_DIRECTORY
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.plugins.registry import PluginRegistry
from anaconda_project.plugins.requirement import EnvVarRequirement
from anaconda_project.plugins.requirements.conda_env import CondaEnvRequirement
from anaconda_project.plugins.requirements.service import ServiceRequirement
from anaconda_project.plugins.requirements.download import DownloadRequirement
from anaconda_project.project import Project
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME
from anaconda_project.test.environ_utils import minimal_environ
from anaconda_project.test.project_utils import project_no_dedicated_env


def test_properties():
    def check_properties(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.problems == []
        assert dirname == project.directory_path
        assert dirname == os.path.dirname(project.project_file.filename)
        assert dirname == os.path.dirname(os.path.dirname(project.conda_meta_file.filename))
        assert project.name == os.path.basename(dirname)

    with_directory_contents(dict(), check_properties)


def test_ignore_trailing_slash_on_dirname():
    def check_properties(dirname):
        project = project_no_dedicated_env(dirname + "/")
        assert project.problems == []
        assert dirname == project.directory_path
        assert dirname == os.path.dirname(project.project_file.filename)
        assert dirname == os.path.dirname(os.path.dirname(project.conda_meta_file.filename))
        assert project.name == os.path.basename(dirname)

    with_directory_contents(dict(), check_properties)


def test_single_env_var_requirement():
    def check_some_env_var(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        assert 2 == len(project.requirements)
        assert "FOO" == project.requirements[0].env_var
        assert dict() == project.requirements[0].options

        if platform.system() == 'Windows':
            assert "CONDA_DEFAULT_ENV" == project.requirements[1].env_var
        else:
            assert "CONDA_ENV_PATH" == project.requirements[1].env_var

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: {}
"""}, check_some_env_var)


def test_single_env_var_requirement_null_for_default():
    def check_some_env_var(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        assert 3 == len(project.requirements)
        assert "FOO" == project.requirements[0].env_var
        assert dict() == project.requirements[0].options
        assert "BAR" == project.requirements[1].env_var
        assert dict() == project.requirements[1].options

        if platform.system() == 'Windows':
            assert "CONDA_DEFAULT_ENV" == project.requirements[2].env_var
        else:
            assert "CONDA_ENV_PATH" == project.requirements[2].env_var

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: null
  BAR: { default: null }
"""}, check_some_env_var)


def test_single_env_var_requirement_string_for_default():
    def check_some_env_var(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        assert 2 == len(project.requirements)
        assert "FOO" == project.requirements[0].env_var
        assert dict(default='hello') == project.requirements[0].options

        if platform.system() == 'Windows':
            assert "CONDA_DEFAULT_ENV" == project.requirements[1].env_var
        else:
            assert "CONDA_ENV_PATH" == project.requirements[1].env_var

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: 'hello'
"""}, check_some_env_var)


def test_single_env_var_requirement_number_for_default():
    def check_some_env_var(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        assert 2 == len(project.requirements)
        assert "FOO" == project.requirements[0].env_var
        assert dict(default='42') == project.requirements[0].options

        if platform.system() == 'Windows':
            assert "CONDA_DEFAULT_ENV" == project.requirements[1].env_var
        else:
            assert "CONDA_ENV_PATH" == project.requirements[1].env_var

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: 42
"""}, check_some_env_var)


def test_single_env_var_requirement_default_is_in_dict():
    def check_some_env_var(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        assert 2 == len(project.requirements)
        assert "FOO" == project.requirements[0].env_var
        assert dict(default='42') == project.requirements[0].options

        if platform.system() == 'Windows':
            assert "CONDA_DEFAULT_ENV" == project.requirements[1].env_var
        else:
            assert "CONDA_ENV_PATH" == project.requirements[1].env_var

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: { default: 42 }
"""}, check_some_env_var)


def test_problem_in_project_file():
    def check_problem(dirname):
        project = project_no_dedicated_env(dirname)
        assert 0 == len(project.requirements)
        assert 1 == len(project.problems)

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
variables:
  42
"""}, check_problem)


def test_problem_empty_names():
    def check_problem(dirname):
        project = project_no_dedicated_env(dirname)
        assert "Variable name cannot be empty string, found: ' ' as name" in project.problems
        assert "Download name cannot be empty string, found: ' ' as name" in project.problems
        assert "Service name cannot be empty string, found: ' ' as name" in project.problems
        assert "Environment variable name cannot be empty string, found: ' ' as name" in project.problems
        assert "Command variable name cannot be empty string, found: ' ' as name" in project.problems

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  ' ': 'thing'
downloads:
  ' ': 'http://localhost:8000/foo.tgz'
services:
  ' ': redis
environments:
  ' ':
    dependencies:
       - python
commands:
  ' ':
    shell: echo 'foo'
"""}, check_problem)


def test_problem_empty_names_var_list():
    def check_problem(dirname):
        project = project_no_dedicated_env(dirname)
        assert "Variable name cannot be empty string, found: ' ' as name" in project.problems

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
variables:
  - ' '
"""}, check_problem)


def test_project_dir_does_not_exist():
    def check_does_not_exist(dirname):
        project_dir = os.path.join(dirname, 'foo')
        assert not os.path.isdir(project_dir)
        project = Project(project_dir)
        assert not os.path.isdir(project_dir)
        assert ["Project directory '%s' does not exist." % project_dir] == project.problems
        assert 0 == len(project.requirements)

    with_directory_contents(dict(), check_does_not_exist)


def test_project_dir_not_readable(monkeypatch):
    def check_not_readable(dirname):
        project_dir = os.path.join(dirname, 'foo')
        os.makedirs(project_dir)

        def mock_os_walk(dirname):
            raise OSError("NOPE")

        monkeypatch.setattr('os.walk', mock_os_walk)

        project = Project(project_dir)

        assert ["Could not list files in %s: NOPE." % project_dir] == project.problems

    with_directory_contents(dict(), check_not_readable)


def test_single_env_var_requirement_with_options():
    def check_some_env_var(dirname):
        project = project_no_dedicated_env(dirname)
        assert 2 == len(project.requirements)
        assert "FOO" == project.requirements[0].env_var
        assert dict(default="hello") == project.requirements[0].options

        if platform.system() == 'Windows':
            assert "CONDA_DEFAULT_ENV" == project.requirements[1].env_var
        else:
            assert "CONDA_ENV_PATH" == project.requirements[1].env_var

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
variables:
    FOO: { default: "hello" }
"""}, check_some_env_var)


def test_override_plugin_registry():
    def check_override_plugin_registry(dirname):
        registry = PluginRegistry()
        project = project_no_dedicated_env(dirname, registry)
        assert project._config_cache.registry is registry

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: {}
"""}, check_override_plugin_registry)


def test_get_name_from_conda_meta_yaml():
    def check_name_from_meta_file(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.name == "foo"

    with_directory_contents({DEFAULT_RELATIVE_META_PATH: """
package:
  name: foo
"""}, check_name_from_meta_file)


def test_broken_name_in_conda_meta_yaml():
    def check_name_from_meta_file(dirname):
        project = project_no_dedicated_env(dirname)
        assert [
            (os.path.join(dirname, DEFAULT_RELATIVE_META_PATH) +
             ": package: name: field should have a string value not []")
        ] == project.problems

    with_directory_contents({DEFAULT_RELATIVE_META_PATH: """
package:
  name: []
"""}, check_name_from_meta_file)


def test_get_name_from_project_file():
    def check_name_from_project_file(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.name == "foo"

        assert project.conda_meta_file.name == "from_meta"

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
name: foo
    """,
         DEFAULT_RELATIVE_META_PATH: """
package:
  name: from_meta
"""}, check_name_from_project_file)


def test_broken_name_in_project_file():
    def check_name_from_project_file(dirname):
        project = project_no_dedicated_env(dirname)
        assert [(os.path.join(dirname, DEFAULT_PROJECT_FILENAME) + ": name: field should have a string value not []")
                ] == project.problems

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
name: []
    """,
         DEFAULT_RELATIVE_META_PATH: """
package:
  name: from_meta
"""}, check_name_from_project_file)


def test_get_name_from_directory_name():
    def check_name_from_directory_name(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.name == os.path.basename(dirname)

    with_directory_contents(dict(), check_name_from_directory_name)


def test_set_name_in_project_file():
    def check_set_name(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.name == "foo"

        project.project_file.name = "bar"
        assert project.name == "foo"
        project.project_file.save()
        assert project.name == "bar"

        project2 = project_no_dedicated_env(dirname)
        assert project2.name == "bar"

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
name: foo
"""}, check_set_name)


def test_get_icon_from_conda_meta_yaml():
    def check_icon_from_meta_file(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.icon == os.path.join(dirname, META_DIRECTORY, "foo.png")

    with_directory_contents(
        {DEFAULT_RELATIVE_META_PATH: """
app:
  icon: foo.png
""",
         "conda.recipe/foo.png": ""}, check_icon_from_meta_file)


def test_broken_icon_in_conda_meta_yaml():
    def check_icon_from_meta_file(dirname):
        project = project_no_dedicated_env(dirname)
        assert [
            (os.path.join(dirname, DEFAULT_RELATIVE_META_PATH) + ": app: icon: field should have a string value not []")
        ] == project.problems

    with_directory_contents({DEFAULT_RELATIVE_META_PATH: """
app:
  icon: []
"""}, check_icon_from_meta_file)


def test_get_icon_from_project_file():
    def check_icon_from_project_file(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.icon == os.path.join(dirname, "foo.png")

        assert project.conda_meta_file.icon == "from_meta.png"

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
icon: foo.png
    """,
         DEFAULT_RELATIVE_META_PATH: """
app:
  icon: from_meta.png
""",
         "foo.png": "",
         "conda.recipe/from_meta.png": ""}, check_icon_from_project_file)


def test_broken_icon_in_project_file():
    def check_icon_from_project_file(dirname):
        project = project_no_dedicated_env(dirname)
        assert [(os.path.join(dirname, DEFAULT_PROJECT_FILENAME) + ": icon: field should have a string value not []")
                ] == project.problems

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
icon: []
    """,
         DEFAULT_RELATIVE_META_PATH: """
app:
  icon: from_meta.png
         """,
         "conda.recipe/from_meta.png": ""}, check_icon_from_project_file)


def test_nonexistent_icon_in_project_file():
    def check_icon_from_project_file(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.icon is None
        assert ["Icon file %s does not exist." % (os.path.join(dirname, "foo.png"))] == project.problems

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
icon: foo.png
    """}, check_icon_from_project_file)


def test_set_icon_in_project_file():
    def check_set_icon(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.icon == os.path.join(dirname, "foo.png")

        project.project_file.icon = "bar.png"
        assert project.icon == os.path.join(dirname, "foo.png")
        project.project_file.save()
        assert project.icon == os.path.join(dirname, "bar.png")

        project2 = project_no_dedicated_env(dirname)
        assert project2.icon == os.path.join(dirname, "bar.png")

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
icon: foo.png
""",
         "foo.png": "",
         "bar.png": ""}, check_set_icon)


def test_get_package_requirements_from_project_file():
    def check_get_packages(dirname):
        project = project_no_dedicated_env(dirname)
        env = project.conda_environments['default']
        assert env.name == 'default'
        assert ("foo", "hello >= 1.0", "world") == env.dependencies
        assert ("mtv", "hbo") == env.channels
        assert set(["foo", "hello", "world"]) == env.conda_package_names_set

        # find CondaEnvRequirement
        conda_env_req = None
        for r in project.requirements:
            if isinstance(r, CondaEnvRequirement):
                assert conda_env_req is None  # only one
                conda_env_req = r
        assert len(conda_env_req.environments) == 1
        assert 'default' in conda_env_req.environments
        assert conda_env_req.environments['default'] is env

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
dependencies:
  - foo
  - hello >= 1.0
  - world

channels:
  - mtv
  - hbo
    """}, check_get_packages)


def test_get_package_requirements_from_empty_project():
    def check_get_packages(dirname):
        project = project_no_dedicated_env(dirname)
        assert () == project.conda_environments['default'].dependencies

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ""}, check_get_packages)


def test_complain_about_dependencies_not_a_list():
    def check_get_packages(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        "should be a list of strings not 'CommentedMap" in project.problems[0]

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
dependencies:
    foo: bar
    """}, check_get_packages)


def test_complain_about_conda_env_in_variables_list():
    def check_complain_about_conda_env_var(dirname):
        project = project_no_dedicated_env(dirname)
        template = "Environment variable %s is reserved for Conda's use, " + \
                   "so it can't appear in the variables section."
        assert [template % 'CONDA_ENV_PATH', template % 'CONDA_DEFAULT_ENV'] == project.problems

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  - CONDA_ENV_PATH
  - CONDA_DEFAULT_ENV
    """}, check_complain_about_conda_env_var)


def test_complain_about_conda_env_in_variables_dict():
    def check_complain_about_conda_env_var(dirname):
        project = project_no_dedicated_env(dirname)
        template = "Environment variable %s is reserved for Conda's use, " + \
                   "so it can't appear in the variables section."
        assert [template % 'CONDA_ENV_PATH', template % 'CONDA_DEFAULT_ENV'] == project.problems

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  CONDA_ENV_PATH: {}
  CONDA_DEFAULT_ENV: {}
    """}, check_complain_about_conda_env_var)


def test_load_environments():
    def check_environments(dirname):
        project = project_no_dedicated_env(dirname)
        assert 0 == len(project.problems)
        assert len(project.conda_environments) == 3
        assert 'default' in project.conda_environments
        assert 'foo' in project.conda_environments
        assert 'bar' in project.conda_environments
        assert project.default_conda_environment_name == 'default'
        default = project.conda_environments['default']
        foo = project.conda_environments['foo']
        bar = project.conda_environments['bar']
        assert default.dependencies == ()
        assert foo.dependencies == ('python', 'dog', 'cat', 'zebra')
        assert bar.dependencies == ()

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
environments:
  foo:
    dependencies:
       - python
       - dog
       - cat
       - zebra
  bar: {}
    """}, check_environments)


def test_load_environments_merging_in_global():
    def check_environments(dirname):
        project = project_no_dedicated_env(dirname)
        assert 0 == len(project.problems)
        assert len(project.conda_environments) == 3
        assert 'default' in project.conda_environments
        assert 'foo' in project.conda_environments
        assert 'bar' in project.conda_environments
        assert project.default_conda_environment_name == 'default'
        default = project.conda_environments['default']
        foo = project.conda_environments['foo']
        bar = project.conda_environments['bar']
        assert default.dependencies == ('dead-parrot', 'elephant', 'lion')
        assert foo.dependencies == ('dead-parrot', 'elephant', 'python', 'dog', 'cat', 'zebra')
        assert bar.dependencies == ('dead-parrot', 'elephant')
        assert default.channels == ('mtv', 'cartoons')
        assert foo.channels == ('mtv', 'hbo')
        assert bar.channels == ('mtv', )

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
dependencies:
  - dead-parrot
  - elephant

channels:
  - mtv

environments:
  foo:
    dependencies:
       - python
       - dog
       - cat
       - zebra
    channels:
       - hbo
  bar: {}
  default:
    dependencies:
      - lion
    channels:
      - cartoons
    """}, check_environments)


def test_load_environments_default_always_default_even_if_not_first():
    def check_environments(dirname):
        project = project_no_dedicated_env(dirname)
        assert 0 == len(project.problems)
        assert len(project.conda_environments) == 3
        assert 'foo' in project.conda_environments
        assert 'bar' in project.conda_environments
        assert 'default' in project.conda_environments
        assert project.default_conda_environment_name == 'default'
        foo = project.conda_environments['foo']
        bar = project.conda_environments['bar']
        default = project.conda_environments['default']
        assert foo.dependencies == ()
        assert bar.dependencies == ()
        assert default.dependencies == ()

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
environments:
  foo: {}
  bar: {}
  default: {}
    """}, check_environments)


def test_complain_about_environments_not_a_dict():
    def check_environments(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        "should be a directory from environment name to environment attributes, not 42" in project.problems[0]

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
environments: 42
    """}, check_environments)


def test_complain_about_dependencies_list_of_wrong_thing():
    def check_get_packages(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        "should be a string not '42'" in project.problems[0]

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
dependencies:
    - 42
    """}, check_get_packages)


def test_load_list_of_variables_requirements():
    def check_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        requirements = project.requirements
        assert 3 == len(requirements)
        assert isinstance(requirements[0], EnvVarRequirement)
        assert 'FOO' == requirements[0].env_var
        assert isinstance(requirements[1], EnvVarRequirement)
        assert 'BAR' == requirements[1].env_var
        assert isinstance(requirements[2], CondaEnvRequirement)
        if platform.system() == 'Windows':
            assert "CONDA_DEFAULT_ENV" == project.requirements[2].env_var
        else:
            assert "CONDA_ENV_PATH" == project.requirements[2].env_var
        assert dict() == requirements[2].options
        assert len(project.problems) == 0

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  - FOO\n  - BAR\n"}, check_file)


def test_load_dict_of_variables_requirements():
    def check_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        requirements = project.requirements
        assert 3 == len(requirements)
        assert isinstance(requirements[0], EnvVarRequirement)
        assert 'FOO' == requirements[0].env_var
        assert dict(a=1) == requirements[0].options
        assert isinstance(requirements[1], EnvVarRequirement)
        assert 'BAR' == requirements[1].env_var
        assert dict(b=2) == requirements[1].options
        assert isinstance(requirements[2], CondaEnvRequirement)
        if platform.system() == 'Windows':
            assert "CONDA_DEFAULT_ENV" == project.requirements[2].env_var
        else:
            assert "CONDA_ENV_PATH" == project.requirements[2].env_var
        assert dict() == requirements[2].options
        assert len(project.problems) == 0

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  FOO: { a: 1 }\n  BAR: { b: 2 }\n"}, check_file)


def test_non_string_variables_requirements():
    def check_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = project_no_dedicated_env(dirname)
        assert 2 == len(project.problems)
        assert 0 == len(project.requirements)
        assert "42 is not a string" in project.problems[0]
        assert "43 is not a string" in project.problems[1]

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  - 42\n  - 43\n"}, check_file)


def test_variable_default_cannot_be_bool():
    def check_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = project_no_dedicated_env(dirname)
        assert [] == project.requirements
        assert 1 == len(project.problems)

        assert ("default value for variable FOO must be null, a string, or a number, not True.") == project.problems[0]

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  FOO: true\n"}, check_file)


def test_variable_default_cannot_be_list():
    def check_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = project_no_dedicated_env(dirname)
        assert [] == project.requirements
        assert 1 == len(project.problems)

        assert ("default value for variable FOO must be null, a string, or a number, not [].") == project.problems[0]

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  FOO: []\n"}, check_file)


def test_variable_default_missing_encrypted_field():
    def check(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = project_no_dedicated_env(dirname)
        assert [] == project.requirements
        assert 1 == len(project.problems)

        assert ("default value for variable FOO can be a dict but only if it contains 'key' and 'encrypted' fields; " +
                "found {'key': 'MASTER_PASSWORD'}") == project.problems[0]

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  FOO:
    default: { key: 'MASTER_PASSWORD' }
"""}, check)


def test_variable_default_missing_key_field():
    def check(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = project_no_dedicated_env(dirname)
        assert [] == project.requirements
        assert 1 == len(project.problems)

        assert ("default value for variable FOO can be a dict but only if it contains 'key' and 'encrypted' fields; " +
                "found {'encrypted': 'abcdefg'}") == project.problems[0]

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  FOO:
    default: { encrypted: 'abcdefg' }
"""}, check)


def test_variables_requirements_not_a_collection():
    def check_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        assert 0 == len(project.requirements)
        assert "variables section contains wrong value type 42" in project.problems[0]

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  42\n"}, check_file)


def test_corrupted_project_file_and_meta_file():
    def check_problem(dirname):
        project = project_no_dedicated_env(dirname)
        assert 0 == len(project.requirements)
        assert 2 == len(project.problems)
        assert 'project.yml has a syntax error that needs to be fixed by hand' in project.problems[0]
        assert 'meta.yaml has a syntax error that needs to be fixed by hand' in project.problems[1]

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
^
variables:
  FOO
""",
         DEFAULT_RELATIVE_META_PATH: """
^
package:
  name: foo
  version: 1.2.3
"""}, check_problem)


def test_non_dict_meta_yaml_app_entry():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.conda_meta_file.app_entry == 42
        assert 1 == len(project.problems)
        expected_error = "%s: app: entry: should be a string not '%r'" % (project.conda_meta_file.filename, 42)
        assert expected_error == project.problems[0]

    with_directory_contents({DEFAULT_RELATIVE_META_PATH: "app:\n  entry: 42\n"}, check_app_entry)


def test_non_dict_commands_section():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: 'commands:' section should be a dictionary from command names to attributes, not %r" % (
            project.project_file.filename, 42)
        assert expected_error == project.problems[0]

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "commands:\n  42\n"}, check_app_entry)


def test_non_dict_services_section():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = ("%s: 'services:' section should be a dictionary from environment variable " +
                          "to service type, found %r") % (project.project_file.filename, 42)
        assert expected_error == project.problems[0]

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "services:\n  42\n"}, check_app_entry)


def test_non_string_as_value_of_command():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: command name '%s' should be followed by a dictionary of attributes not %r" % (
            project.project_file.filename, 'default', 42)
        assert expected_error == project.problems[0]

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "commands:\n default: 42\n"}, check_app_entry)


def test_empty_command():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: command '%s' does not have a command line in it" % (project.project_file.filename,
                                                                                  'default')
        assert expected_error == project.problems[0]

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "commands:\n default: {}\n"}, check_app_entry)


def test_command_with_bogus_key():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: command '%s' does not have a command line in it" % (project.project_file.filename,
                                                                                  'default')
        assert expected_error == project.problems[0]

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    foobar: 'boo'\n"}, check_app_entry)


def test_command_with_bogus_key_and_ok_key():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        command = project.default_command
        assert command.name == 'default'
        assert command.unix_shell_commandline == 'bar'
        assert not command.auto_generated
        assert command.windows_cmd_commandline is None
        assert command.conda_app_entry is None

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    foobar: 'boo'\n\n    unix: 'bar'\n"}, check_app_entry)


def test_two_empty_commands():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert 2 == len(project.problems)
        expected_error_1 = "%s: command '%s' does not have a command line in it" % (project.project_file.filename,
                                                                                    'foo')
        expected_error_2 = "%s: command '%s' does not have a command line in it" % (project.project_file.filename,
                                                                                    'bar')
        assert expected_error_1 == project.problems[0]
        assert expected_error_2 == project.problems[1]

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "commands:\n foo: {}\n bar: {}\n"}, check_app_entry)


def test_non_string_as_value_of_conda_app_entry():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: command '%s' attribute '%s' should be a string not '%r'" % (
            project.project_file.filename, 'default', 'conda_app_entry', 42)
        assert expected_error == project.problems[0]

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    conda_app_entry: 42\n"}, check_app_entry)


def test_non_string_as_value_of_shell():
    def check_shell_non_dict(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: command '%s' attribute '%s' should be a string not '%r'" % (project.project_file.filename,
                                                                                          'default', 'unix', 42)
        assert expected_error == project.problems[0]

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    unix: 42\n"}, check_shell_non_dict)


def test_notebook_command():
    def check_notebook_command(dirname):
        project = project_no_dedicated_env(dirname)
        command = project.default_command
        assert command.notebook == 'test.ipynb'
        assert command.unix_shell_commandline is None
        assert command.windows_cmd_commandline is None
        assert command.conda_app_entry is None
        assert not command.auto_generated

        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(environ)
        path = os.pathsep.join([environ['PROJECT_DIR'], environ['PATH']])
        jupyter_notebook = find_executable('jupyter-notebook', path)
        assert cmd_exec.args == [jupyter_notebook, os.path.join(dirname, 'test.ipynb')]
        assert cmd_exec.shell is False
        assert cmd_exec.notebook == 'test.ipynb'

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    notebook: test.ipynb\n"}, check_notebook_command)


def test_notebook_command_extra_args():
    def check_notebook_command_extra_args(dirname):
        project = project_no_dedicated_env(dirname)
        command = project.default_command
        assert command.notebook == 'test.ipynb'
        assert command.unix_shell_commandline is None
        assert command.windows_cmd_commandline is None
        assert command.conda_app_entry is None
        assert not command.auto_generated

        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(environ, extra_args=['foo', 'bar'])
        path = os.pathsep.join([environ['PROJECT_DIR'], environ['PATH']])
        jupyter_notebook = find_executable('jupyter-notebook', path)
        assert cmd_exec.args == [jupyter_notebook, os.path.join(dirname, 'test.ipynb'), 'foo', 'bar']
        assert cmd_exec.shell is False
        assert cmd_exec.notebook == 'test.ipynb'

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    notebook: test.ipynb\n"},
        check_notebook_command_extra_args)


def test_notebook_guess_command():
    def check_notebook_guess_command(dirname):
        project = project_no_dedicated_env(dirname)
        assert 'test.ipynb' in project.commands
        assert 'default' in project.commands
        assert len(project.commands) == 2  # we should have ignored all the ignored ones
        assert project.default_command.name == 'default'

        command = project.commands['test.ipynb']
        assert command.notebook == 'test.ipynb'
        assert command.unix_shell_commandline is None
        assert command.windows_cmd_commandline is None
        assert command.conda_app_entry is None
        assert command.auto_generated

        expected_nb_path = os.path.join(dirname, 'test.ipynb')
        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(environ)
        path = os.pathsep.join([environ['PROJECT_DIR'], environ['PATH']])
        jupyter_notebook = find_executable('jupyter-notebook', path)
        assert cmd_exec.args == [jupyter_notebook, expected_nb_path]
        assert cmd_exec.shell is False
        assert cmd_exec.notebook == 'test.ipynb'

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    unix: echo 'pass'",
            'test.ipynb': 'pretend there is notebook data here',
            'envs/should_ignore_this.ipynb': 'pretend this is more notebook data',
            'services/should_ignore_this.ipynb': 'pretend this is more notebook data',
            '.should_ignore_dotfile.ipynb': 'moar fake notebook',
            '.should_ignore_dotdir/foo.ipynb': 'still moar fake notebook'
        }, check_notebook_guess_command)

    # anaconda-project launch --command data.ipynb


def test_notebook_guess_command_can_be_default():
    def check_notebook_guess_command_can_be_default(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        assert len(project.commands) == 4
        assert project.default_command is not None
        assert project.default_command.notebook == 'a.ipynb'

    with_directory_contents(
        {
            # we pick the first command alphabetically in this case
            # so the test looks for that
            'a.ipynb': 'pretend there is notebook data here',
            'b.ipynb': 'pretend there is notebook data here',
            'c.ipynb': 'pretend there is notebook data here',
            'd.ipynb': 'pretend there is notebook data here'
        },
        check_notebook_guess_command_can_be_default)


def test_notebook_command_conflict():
    def check_notebook_conflict_command(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: command '%s' has conflicting statements, 'notebook' must stand alone" % (
            project.project_file.filename, 'default')
        assert expected_error == project.problems[0]

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    notebook: test.ipynb\n    unix: echo 'pass'"},
        check_notebook_conflict_command)


def test_bokeh_command_conflict():
    def check_bokeh_conflict_command(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: command '%s' has conflicting statements, 'bokeh_app' must stand alone" % (
            project.project_file.filename, 'default')
        assert expected_error == project.problems[0]

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    bokeh_app: app.py\n    unix: echo 'pass'"},
        check_bokeh_conflict_command)


def test_bokeh_command():
    def check_bokeh_command(dirname):
        project = project_no_dedicated_env(dirname)
        command = project.default_command
        assert command.bokeh_app == 'test.py'
        assert command.notebook is None
        assert command.unix_shell_commandline is None
        assert command.windows_cmd_commandline is None
        assert command.conda_app_entry is None
        assert not command.auto_generated

        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(environ)
        path = os.pathsep.join([environ['PROJECT_DIR'], environ['PATH']])
        bokeh = find_executable('bokeh', path)
        assert cmd_exec.args == [bokeh, 'serve', os.path.join(dirname, 'test.py')]
        assert cmd_exec.shell is False
        assert cmd_exec.bokeh_app == 'test.py'

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    bokeh_app: test.py\n"}, check_bokeh_command)


def test_bokeh_command_with_extra_args():
    def check_bokeh_command_extra_args(dirname):
        project = project_no_dedicated_env(dirname)
        command = project.default_command
        assert command.bokeh_app == 'test.py'
        assert command.notebook is None
        assert command.unix_shell_commandline is None
        assert command.windows_cmd_commandline is None
        assert command.conda_app_entry is None
        assert not command.auto_generated

        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(environ, extra_args=['--show'])
        path = os.pathsep.join([environ['PROJECT_DIR'], environ['PATH']])
        bokeh = find_executable('bokeh', path)
        assert cmd_exec.args == [bokeh, 'serve', os.path.join(dirname, 'test.py'), '--show']
        assert cmd_exec.shell is False
        assert cmd_exec.bokeh_app == 'test.py'

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    bokeh_app: test.py\n"}, check_bokeh_command_extra_args)


def test_launch_argv_from_project_file_app_entry():
    def check_launch_argv(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        command = project.default_command
        assert command.name == 'foo'
        assert command.conda_app_entry == "foo bar ${PREFIX}"
        assert not command.auto_generated

        assert 1 == len(project.commands)
        assert 'foo' in project.commands
        assert project.commands['foo'] is command

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  foo:
    conda_app_entry: foo bar ${PREFIX}
"""}, check_launch_argv)


def test_launch_argv_from_project_file_shell():
    def check_launch_argv(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        command = project.default_command
        assert command.name == 'foo'
        assert command.unix_shell_commandline == "foo bar ${PREFIX}"
        assert not command.auto_generated

        assert 1 == len(project.commands)
        assert 'foo' in project.commands
        assert project.commands['foo'] is command

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  foo:
    unix: foo bar ${PREFIX}
"""}, check_launch_argv)


def test_launch_argv_from_project_file_windows(monkeypatch):
    def check_launch_argv(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        command = project.default_command
        assert command.name == 'foo'
        assert command.windows_cmd_commandline == "foo bar %CONDA_DEFAULT_ENV%"
        assert command.unix_shell_commandline is None
        assert not command.auto_generated

        assert 1 == len(project.commands)
        assert 'foo' in project.commands
        assert project.commands['foo'] is command

        def mock_platform_system():
            return 'Windows'

        monkeypatch.setattr('platform.system', mock_platform_system)

        environ = minimal_environ(PROJECT_DIR=dirname)

        exec_info = project.exec_info_for_environment(environ)
        assert exec_info.shell

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  foo:
    windows: foo bar %CONDA_DEFAULT_ENV%
"""}, check_launch_argv)


def test_exec_info_is_none_when_no_commands():
    def check_exec_info(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        command = project.default_command
        assert command is None

        environ = minimal_environ(PROJECT_DIR=dirname)

        exec_info = project.exec_info_for_environment(environ)
        assert exec_info is None

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
"""}, check_exec_info)


def test_exec_info_is_none_when_command_not_for_our_platform():
    def check_exec_info(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        command = project.default_command
        assert command is not None
        assert command.name == 'foo'

        environ = minimal_environ(PROJECT_DIR=dirname)

        exec_info = project.exec_info_for_environment(environ)
        assert exec_info is None

    import platform
    not_us = 'windows'
    if platform.system() == 'Windows':
        not_us = 'unix'
    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
commands:
  foo:
    %s: foo
""" % not_us}, check_exec_info)


def test_launch_argv_from_meta_file():
    def check_launch_argv(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        command = project.default_command
        assert command.name == 'default'
        assert command.conda_app_entry == 'foo bar ${PREFIX}'
        assert command.unix_shell_commandline is None
        assert command.windows_cmd_commandline is None
        assert command.auto_generated

    with_directory_contents({DEFAULT_RELATIVE_META_PATH: """
app:
  entry: foo bar ${PREFIX}
"""}, check_launch_argv)


# we used to fill in empty commands from meta.yaml, but no more,
def test_launch_argv_from_meta_file_with_name_in_project_file():
    def check_launch_argv(dirname):
        project = project_no_dedicated_env(dirname)
        assert ["%s: command 'foo' does not have a command line in it" % project.project_file.filename
                ] == project.problems

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME: """
commands:
  foo: {}
""",
            DEFAULT_RELATIVE_META_PATH: """
app:
  entry: foo bar ${PREFIX}
"""
        }, check_launch_argv)


if platform.system() == 'Windows':
    echo_stuff = "echo_stuff.bat"
else:
    echo_stuff = "echo_stuff.sh"


def _launch_argv_for_environment(environ,
                                 expected_output,
                                 chdir=False,
                                 command_line=('conda_app_entry: %s ${PREFIX} foo bar' % echo_stuff),
                                 extra_args=None):
    environ = minimal_environ(**environ)

    def check_echo_output(dirname):
        if 'PROJECT_DIR' not in environ:
            environ['PROJECT_DIR'] = dirname
        os.chmod(os.path.join(dirname, echo_stuff), stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        old_dir = None
        if chdir:
            old_dir = os.getcwd()
            os.chdir(dirname)
        try:
            project = project_no_dedicated_env(dirname)
            assert [] == project.problems
            exec_info = project.exec_info_for_environment(environ, extra_args=extra_args)
            if exec_info.shell:
                args = exec_info.args[0]
            else:
                args = exec_info.args
            output = subprocess.check_output(args, shell=exec_info.shell, env=environ).decode()
            # strip() removes \r\n or \n so we don't have to deal with the difference
            assert output.strip() == expected_output.format(dirname=dirname)
        finally:
            if old_dir is not None:
                os.chdir(old_dir)

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME: """
commands:
  default:
    %s
""" % command_line,
            "echo_stuff.sh": """#!/bin/sh
echo "$*"
""",
            "echo_stuff.bat": """
@echo off
echo %*
"""
        }, check_echo_output)


def test_launch_command_in_project_dir():
    prefix = os.getenv('CONDA_ENV_PATH', os.getenv('CONDA_DEFAULT_ENV'))
    _launch_argv_for_environment(dict(), "%s foo bar" % (prefix))


def test_launch_command_in_project_dir_extra_args():
    prefix = os.getenv('CONDA_ENV_PATH', os.getenv('CONDA_DEFAULT_ENV'))
    _launch_argv_for_environment(dict(), "%s foo bar baz" % (prefix), extra_args=["baz"])


def test_launch_command_in_project_dir_with_shell(monkeypatch):
    if platform.system() == 'Windows':
        print("Cannot test shell on Windows")
        return
    prefix = os.getenv('CONDA_ENV_PATH', os.getenv('CONDA_DEFAULT_ENV'))
    _launch_argv_for_environment(dict(),
                                 "%s foo bar" % (prefix),
                                 command_line='unix: "${PROJECT_DIR}/echo_stuff.sh ${CONDA_ENV_PATH} foo bar"')


def test_launch_command_in_project_dir_with_shell_extra_args(monkeypatch):
    if platform.system() == 'Windows':
        print("Cannot test shell on Windows")
        return
    prefix = os.getenv('CONDA_ENV_PATH', os.getenv('CONDA_DEFAULT_ENV'))
    _launch_argv_for_environment(dict(),
                                 "%s foo bar baz" % (prefix),
                                 command_line='unix: "${PROJECT_DIR}/echo_stuff.sh ${CONDA_ENV_PATH} foo bar"',
                                 extra_args=["baz"])


def test_launch_command_in_project_dir_with_windows(monkeypatch):
    if platform.system() != 'Windows':
        print("Cannot test windows cmd on unix")
        return
    prefix = os.getenv('CONDA_ENV_PATH', os.getenv('CONDA_DEFAULT_ENV'))
    _launch_argv_for_environment(
        dict(),
        "%s foo bar" % (prefix),
        command_line='''windows: "\\"%PROJECT_DIR%\\\\echo_stuff.bat\\" %CONDA_DEFAULT_ENV% foo bar"''')


def test_launch_command_in_project_dir_with_windows_extra_args(monkeypatch):
    if platform.system() != 'Windows':
        print("Cannot test windows cmd on unix")
        return
    prefix = os.getenv('CONDA_ENV_PATH', os.getenv('CONDA_DEFAULT_ENV'))
    _launch_argv_for_environment(
        dict(),
        "%s foo bar baz" % (prefix),
        command_line='''windows: "\\"%PROJECT_DIR%\\\\echo_stuff.bat\\" %CONDA_DEFAULT_ENV% foo bar"''',
        extra_args=["baz"])


def test_launch_command_in_project_dir_and_cwd_is_project_dir():
    prefix = os.getenv('CONDA_ENV_PATH', os.getenv('CONDA_DEFAULT_ENV'))
    _launch_argv_for_environment(dict(),
                                 "%s foo bar" % prefix,
                                 chdir=True,
                                 command_line=('conda_app_entry: %s ${PREFIX} foo bar' % os.path.join(".", echo_stuff)))


def test_launch_command_in_project_dir_with_conda_env():
    _launch_argv_for_environment(
        dict(CONDA_ENV_PATH='/someplace',
             CONDA_DEFAULT_ENV='/someplace'),
        "/someplace foo bar")


def test_launch_command_is_on_system_path():
    def check_python_version_output(dirname):
        environ = minimal_environ(PROJECT_DIR=dirname)
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        exec_info = project.exec_info_for_environment(environ)
        output = subprocess.check_output(exec_info.args, shell=exec_info.shell, stderr=subprocess.STDOUT).decode()
        assert output.startswith("Python")

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  default:
    conda_app_entry: python --version
"""}, check_python_version_output)


def test_launch_command_does_not_exist():
    def check_error_on_nonexistent_path(dirname):
        import errno
        environ = minimal_environ(PROJECT_DIR=dirname)
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        exec_info = project.exec_info_for_environment(environ)
        assert exec_info.args[0] == 'this-command-does-not-exist'
        try:
            FileNotFoundError
        except NameError:
            # python 2
            FileNotFoundError = OSError
        with pytest.raises(FileNotFoundError) as excinfo:
            subprocess.check_output(exec_info.args, stderr=subprocess.STDOUT, shell=exec_info.shell).decode()
        assert excinfo.value.errno == errno.ENOENT

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  default:
    conda_app_entry: this-command-does-not-exist
"""}, check_error_on_nonexistent_path)


def test_launch_command_stuff_missing_from_environment():
    def check_launch_with_stuff_missing(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        environ = minimal_environ(PROJECT_DIR=dirname)
        conda_var = 'CONDA_ENV_PATH'
        if platform.system() == 'Windows':
            conda_var = 'CONDA_DEFAULT_ENV'
        for key in ('PATH', conda_var, 'PROJECT_DIR'):
            environ_copy = deepcopy(environ)
            del environ_copy[key]
            with pytest.raises(ValueError) as excinfo:
                project.exec_info_for_environment(environ_copy)
            assert ('%s must be set' % key) in repr(excinfo.value)

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  default:
    conda_app_entry: foo
"""}, check_launch_with_stuff_missing)


def test_get_publication_info_from_empty_project():
    def check_publication_info_from_empty(dirname):
        project = project_no_dedicated_env(dirname)
        expected = {
            'name': os.path.basename(dirname),
            'commands': {},
            'environments': {
                'default': {
                    'channels': [],
                    'dependencies': []
                }
            },
            'variables': {},
            'downloads': {},
            'services': {}
        }
        assert expected == project.publication_info()

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ""}, check_publication_info_from_empty)


_complicated_project_contents = """
name: foobar

commands:
  foo:
    unix: echo hi
  bar:
    windows: echo boo
  baz:
    conda_app_entry: echo blah
  myapp:
    bokeh_app: main.py

dependencies:
  - foo

channels:
  - bar

environments:
  woot:
    dependencies:
      - blah
    channels:
      - woohoo
  w00t:
    dependencies:
      - something
  lol: {}

downloads:
  FOO: https://example.com/blah

services:
  REDIS_URL: redis

variables:
  SOMETHING: {}
  SOMETHING_ELSE: {}

"""


def test_get_publication_info_from_complex_project():
    def check_publication_info_from_complex(dirname):
        project = project_no_dedicated_env(dirname)

        expected = {
            'name': 'foobar',
            'commands': {'bar': {'description': 'echo boo'},
                         'baz': {'description': 'echo blah'},
                         'foo': {'description': 'echo hi',
                                 'default': True},
                         'myapp': {'description': 'Bokeh app main.py',
                                   'bokeh_app': 'main.py'},
                         'foo.ipynb': {'description': 'Notebook foo.ipynb',
                                       'notebook': 'foo.ipynb'}},
            'downloads': {'FOO': {'encrypted': False,
                                  'title': 'A downloaded file which is referenced by FOO',
                                  'url': 'https://example.com/blah'}},
            'environments': {'default': {'channels': ['bar'],
                                         'dependencies': ['foo']},
                             'lol': {'channels': ['bar'],
                                     'dependencies': ['foo']},
                             'w00t': {'channels': ['bar'],
                                      'dependencies': ['foo', 'something']},
                             'woot': {'channels': ['bar', 'woohoo'],
                                      'dependencies': ['foo', 'blah']}},
            'variables': {'SOMETHING': {'encrypted': False,
                                        'title': 'SOMETHING environment variable must be set'},
                          'SOMETHING_ELSE': {'encrypted': False,
                                             'title': 'SOMETHING_ELSE environment variable must be set'}},
            'services': {'REDIS_URL': {'title': 'A running Redis server, located by a redis: URL set as REDIS_URL',
                                       'type': 'redis'}}
        }

        assert expected == project.publication_info()

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: _complicated_project_contents,
         "main.py": "",
         "foo.ipynb": ""}, check_publication_info_from_complex)


def test_find_requirements():
    def check_find_requirements(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        reqs = project.find_requirements(env_var='SOMETHING')
        assert len(reqs) == 1
        assert reqs[0].env_var == 'SOMETHING'

        reqs = project.find_requirements(klass=CondaEnvRequirement)
        assert len(reqs) == 1
        assert isinstance(reqs[0], CondaEnvRequirement)

        reqs = project.find_requirements(klass=ServiceRequirement)
        assert len(reqs) == 1
        assert isinstance(reqs[0], ServiceRequirement)

        reqs = project.find_requirements(klass=DownloadRequirement)
        assert len(reqs) == 1
        assert isinstance(reqs[0], DownloadRequirement)

        # the klass and env_var kwargs must be "AND"-ed together
        reqs = project.find_requirements(klass=CondaEnvRequirement, env_var='SOMETHING')
        assert [] == reqs

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: _complicated_project_contents,
         "main.py": "",
         "foo.ipynb": ""}, check_find_requirements)


def test_requirements_subsets():
    def check_requirements_subsets(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        services = project.service_requirements
        assert len(services) == 1
        assert isinstance(services[0], ServiceRequirement)
        assert services[0].env_var == 'REDIS_URL'

        downloads = project.download_requirements
        assert len(downloads) == 1
        assert isinstance(downloads[0], DownloadRequirement)
        assert downloads[0].env_var == 'FOO'

        everything = project.all_variable_requirements
        everything_names = [req.env_var for req in everything]
        # the first element is CONDA_ENV_PATH or the Windows equivalent CONDA_DEFAULT_ENV
        assert ['FOO', 'REDIS_URL', 'SOMETHING', 'SOMETHING_ELSE'] == sorted(everything_names)[1:]

        plain = project.plain_variable_requirements
        plain_names = [req.env_var for req in plain]
        assert ['SOMETHING', 'SOMETHING_ELSE'] == sorted(plain_names)

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: _complicated_project_contents,
         "main.py": "",
         "foo.ipynb": ""}, check_requirements_subsets)


def test_env_var_name_list_properties():
    def check_env_var_name_list_properties(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        services = project.services
        assert ['REDIS_URL'] == services

        downloads = project.downloads
        assert ['FOO'] == downloads

        everything = project.all_variables
        # the first element is CONDA_ENV_PATH or the Windows equivalent CONDA_DEFAULT_ENV
        assert ['FOO', 'REDIS_URL', 'SOMETHING', 'SOMETHING_ELSE'] == sorted(everything)[1:]

        plain = project.plain_variables
        assert ['SOMETHING', 'SOMETHING_ELSE'] == sorted(plain)

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: _complicated_project_contents,
         "main.py": "",
         "foo.ipynb": ""}, check_env_var_name_list_properties)
