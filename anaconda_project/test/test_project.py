# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from copy import deepcopy
from distutils.spawn import find_executable
import os
import platform
import stat
import subprocess
import sys
import time

import pytest
from unittest import SkipTest

from anaconda_project.env_spec import _load_environment_yml
from anaconda_project import __version__ as version
from anaconda_project.internal.test.tmpfile_utils import (with_directory_contents,
                                                          with_directory_contents_completing_project_file)
from anaconda_project.internal import conda_api
from anaconda_project.requirements_registry.registry import RequirementsRegistry
from anaconda_project.requirements_registry.requirement import EnvVarRequirement
from anaconda_project.requirements_registry.requirements.conda_env import CondaEnvRequirement
from anaconda_project.requirements_registry.requirements.service import ServiceRequirement
from anaconda_project.requirements_registry.requirements.download import DownloadRequirement
from anaconda_project.project import (Project, ProjectProblem)
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME
from anaconda_project.project_lock_file import DEFAULT_PROJECT_LOCK_FILENAME
from anaconda_project.test.environ_utils import minimal_environ
from anaconda_project.test.project_utils import project_no_dedicated_env


def _assert_find_executable(name, path):
    found = find_executable(name, path)
    if found is None:
        print("Did not find %s on path %r, running the tests requires it" % (name, path))
    assert found is not None
    return found


def test_properties():
    def check_properties(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.problems == []
        assert dirname == project.directory_path
        assert dirname == os.path.dirname(project.project_file.filename)
        assert project.name == os.path.basename(dirname)
        assert project.url_friendly_name == os.path.basename(dirname)
        assert project.description == ''

    with_directory_contents(dict(), check_properties)


def test_ignore_trailing_slash_on_dirname():
    def check_properties(dirname):
        project = project_no_dedicated_env(dirname + "/")
        assert project.problems == []
        assert dirname == project.directory_path
        assert dirname == os.path.dirname(project.project_file.filename)
        assert project.name == os.path.basename(dirname)

    with_directory_contents(dict(), check_properties)


def test_single_env_var_requirement():
    def check_some_env_var(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        requirements = project.requirements(project.default_env_spec_name)
        assert 2 == len(requirements)
        assert "FOO" == requirements[0].env_var
        assert dict() == requirements[0].options

        conda_env_var = conda_api.conda_prefix_variable()
        assert conda_env_var == requirements[1].env_var

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: {}
"""}, check_some_env_var)


def test_single_env_var_requirement_with_description():
    def check_some_env_var(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        requirements = project.requirements(project.default_env_spec_name)
        assert 2 == len(requirements)
        assert "FOO" == requirements[0].env_var
        assert {'description': "Set FOO to the value of your foo"} == requirements[0].options
        assert "Set FOO to the value of your foo" == requirements[0].description
        assert "FOO" == requirements[0].title

        conda_env_var = conda_api.conda_prefix_variable()
        assert conda_env_var == requirements[1].env_var

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: { description: "Set FOO to the value of your foo" }
"""}, check_some_env_var)


def test_single_env_var_requirement_null_for_default():
    def check_some_env_var(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        requirements = project.requirements(project.default_env_spec_name)
        assert 3 == len(requirements)
        assert "FOO" == requirements[0].env_var
        assert dict() == requirements[0].options
        assert "BAR" == requirements[1].env_var
        assert dict() == requirements[1].options

        conda_env_var = conda_api.conda_prefix_variable()
        assert conda_env_var == requirements[2].env_var

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: null
  BAR: { default: null }
"""}, check_some_env_var)


def test_single_env_var_requirement_string_for_default():
    def check_some_env_var(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        requirements = project.requirements(project.default_env_spec_name)
        assert 2 == len(requirements)
        assert "FOO" == requirements[0].env_var
        assert dict(default='hello') == requirements[0].options

        conda_env_var = conda_api.conda_prefix_variable()
        assert conda_env_var == requirements[1].env_var

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: 'hello'
"""}, check_some_env_var)


def test_single_env_var_requirement_number_for_default():
    def check_some_env_var(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        requirements = project.requirements(project.default_env_spec_name)
        assert 2 == len(requirements)
        assert "FOO" == requirements[0].env_var
        assert dict(default='42') == requirements[0].options

        conda_env_var = conda_api.conda_prefix_variable()
        assert conda_env_var == requirements[1].env_var

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: 42
"""}, check_some_env_var)


def test_single_env_var_requirement_default_is_in_dict():
    def check_some_env_var(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        requirements = project.requirements(project.default_env_spec_name)
        assert 2 == len(requirements)
        assert "FOO" == requirements[0].env_var
        assert dict(default='42') == requirements[0].options

        conda_env_var = conda_api.conda_prefix_variable()
        assert conda_env_var == requirements[1].env_var

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: { default: 42 }
"""}, check_some_env_var)


def test_requirement_inheritance():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        assert project.default_env_spec_name == 'foo'

        def var_reqs(name):
            conda_env_reqs = [req for req in project.requirements(name) if isinstance(req, CondaEnvRequirement)]
            assert 1 == len(conda_env_reqs)
            requirements = [(req.env_var, req.options.get('default')) for req in project.requirements(name)
                            if not isinstance(req, CondaEnvRequirement)]
            requirements = sorted(requirements, key=lambda x: x[0])
            return ([t[0] for t in requirements], [t[1] for t in requirements])

        requirements = var_reqs('foo')
        assert (['BAR', 'DOWNLOAD', 'FOO'], ['hi', None, 'global']) == requirements

        requirements = var_reqs('foo_with_override')
        assert (['DOWNLOAD', 'FOO'], [None, 'local']) == requirements

        requirements = var_reqs('bar')
        assert (['DOWNLOAD', 'FOO'], [None, 'global']) == requirements

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
variables:
  FOO: { default: "global" }
downloads:
  DOWNLOAD: "http://example.com"
env_specs:
  foo:
    variables:
      BAR: "hi"
  foo_with_override:
    variables:
      FOO: "local"
  bar:
    downloads:
      DOWNLOAD: "http://example.com/bar"
"""
        }, check)


def test_problem_in_project_file():
    def check_problem(dirname):
        project = project_no_dedicated_env(dirname)
        requirements = project.requirements(project.default_env_spec_name)
        assert 0 == len(requirements)
        assert 1 == len(project.problems)

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
variables:
  42
"""}, check_problem)


def test_problem_empty_names():
    def check_problem(dirname):
        project = project_no_dedicated_env(dirname)

        def _fn(s):
            return "%s: %s" % (project.project_file.basename, s)

        assert _fn("Variable name cannot be empty string, found: ' ' as name") in project.problems
        assert _fn("Download name cannot be empty string, found: ' ' as name") in project.problems
        assert _fn("Service name cannot be empty string, found: ' ' as name") in project.problems
        assert _fn("Environment spec name cannot be empty string, found: ' ' as name") in project.problems
        assert _fn("Command variable name cannot be empty string, found: ' ' as name") in project.problems

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
variables:
  ' ': 'thing'
downloads:
  ' ': 'http://localhost:8000/foo.tgz'
services:
  ' ': redis
env_specs:
  ' ':
    packages:
       - python
commands:
  ' ':
    shell: echo 'foo'
"""
        }, check_problem)


def test_problem_empty_names_var_list():
    def check_problem(dirname):
        project = project_no_dedicated_env(dirname)
        assert ("%s: Variable name cannot be empty string, found: ' ' as name" %
                project.project_file.basename) in project.problems

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
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
        requirements = project.requirements(project.default_env_spec_name)
        assert 0 == len(requirements)

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
        requirements = project.requirements(project.default_env_spec_name)
        assert 2 == len(requirements)
        assert "FOO" == requirements[0].env_var
        assert dict(default="hello") == requirements[0].options

        conda_env_var = conda_api.conda_prefix_variable()
        assert conda_env_var == requirements[1].env_var

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
variables:
    FOO: { default: "hello" }
"""}, check_some_env_var)


def test_override_plugin_registry():
    def check_override_plugin_registry(dirname):
        registry = RequirementsRegistry()
        project = project_no_dedicated_env(dirname, registry)
        assert project._config_cache.registry is registry

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: {}
"""}, check_override_plugin_registry)


def test_get_name_from_project_file():
    def check_name_from_project_file(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.name == "foo"

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
name: foo
    """}, check_name_from_project_file)


def test_broken_name_in_project_file():
    def check_name_from_project_file(dirname):
        project = project_no_dedicated_env(dirname)
        assert [(DEFAULT_PROJECT_FILENAME + ": name: field should have a string value not []")] == project.problems

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
name: []
    """}, check_name_from_project_file)


def test_get_name_from_directory_name():
    def check_name_from_directory_name(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.name == os.path.basename(dirname)

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
name: null
"""}, check_name_from_directory_name)


def test_set_name_in_project_file():
    def check_set_name(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.name == "foo"

        project.project_file.set_value('name', "bar")
        assert project.name == "foo"
        project.project_file.save()
        assert project.name == "bar"

        project2 = project_no_dedicated_env(dirname)
        assert project2.name == "bar"

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
name: foo
"""}, check_set_name)


def test_get_description_from_project_file():
    def check_description_from_project_file(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.description == "foo"

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
description: foo
    """}, check_description_from_project_file)


def test_broken_description_in_project_file():
    def check_description_from_project_file(dirname):
        project = project_no_dedicated_env(dirname)
        assert [(DEFAULT_PROJECT_FILENAME + ": description: field should have a string value not []")
                ] == project.problems

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
description: []
    """}, check_description_from_project_file)


def test_get_icon_from_project_file():
    def check_icon_from_project_file(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.icon == os.path.join(dirname, "foo.png")

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
icon: foo.png
        """,
            "foo.png": ""
        }, check_icon_from_project_file)


def test_broken_icon_in_project_file():
    def check_icon_from_project_file(dirname):
        project = project_no_dedicated_env(dirname)
        assert [(DEFAULT_PROJECT_FILENAME + ": icon: field should have a string value not []")] == project.problems

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
icon: []
    """}, check_icon_from_project_file)


def test_nonexistent_icon_in_project_file():
    def check_icon_from_project_file(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.icon is None
        assert ["Icon file %s does not exist." % (os.path.join(dirname, "foo.png"))] == project.problems

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
icon: foo.png
    """}, check_icon_from_project_file)


def test_set_icon_in_project_file():
    def check_set_icon(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.icon == os.path.join(dirname, "foo.png")

        project.project_file.set_value('icon', "bar.png")
        assert project.icon == os.path.join(dirname, "foo.png")
        project.project_file.save()
        assert project.icon == os.path.join(dirname, "bar.png")

        project2 = project_no_dedicated_env(dirname)
        assert project2.icon == os.path.join(dirname, "bar.png")

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
icon: foo.png
""",
            "foo.png": "",
            "bar.png": ""
        }, check_set_icon)


def test_get_dependencies_requirements_from_project_file():
    def check_get_packages(dirname):
        project = project_no_dedicated_env(dirname)
        env = project.env_specs['default']
        assert env.name == 'default'
        assert ("mtv", "hbo") == env.channels
        assert ("foo", "hello >= 1.0", "world") == env.conda_packages
        assert ("pip1", "pip2==1.3", "pip3") == env.pip_packages
        assert set(["foo", "hello", "world"]) == env.conda_package_names_set
        assert set(["pip1", "pip2", "pip3"]) == env.pip_package_names_set

        requirements = project.requirements(project.default_env_spec_name)

        # find CondaEnvRequirement
        conda_env_req = None
        for r in requirements:
            if isinstance(r, CondaEnvRequirement):
                assert conda_env_req is None  # only one
                conda_env_req = r
        assert len(conda_env_req.env_specs) == 1
        assert 'default' in conda_env_req.env_specs
        assert conda_env_req.env_specs['default'] is env

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
dependencies:
  - foo
  - hello >= 1.0
  - world
  - pip:
     - pip1
     - pip2==1.3
  - pip:
     - pip3

channels:
  - mtv
  - hbo
    """
        }, check_get_packages)


def test_get_package_requirements_from_project_file():
    def check_get_packages(dirname):
        project = project_no_dedicated_env(dirname)
        env = project.env_specs['default']
        assert env.name == 'default'
        assert ("mtv", "hbo") == env.channels
        assert ("foo", "hello >= 1.0", "world") == env.conda_packages
        assert ("pip1", "pip2==1.3", "pip3") == env.pip_packages
        assert set(["foo", "hello", "world"]) == env.conda_package_names_set
        assert set(["pip1", "pip2", "pip3"]) == env.pip_package_names_set

        requirements = project.requirements(project.default_env_spec_name)

        # find CondaEnvRequirement
        conda_env_req = None
        for r in requirements:
            if isinstance(r, CondaEnvRequirement):
                assert conda_env_req is None  # only one
                conda_env_req = r
        assert len(conda_env_req.env_specs) == 1
        assert 'default' in conda_env_req.env_specs
        assert conda_env_req.env_specs['default'] is env

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
packages:
  - foo
  - hello >= 1.0
  - world
  - pip:
     - pip1
     - pip2==1.3
  - pip:
     - pip3

channels:
  - mtv
  - hbo
    """
        }, check_get_packages)


def test_get_package_requirements_from_empty_project():
    def check_get_packages(dirname):
        project = project_no_dedicated_env(dirname)
        assert () == project.env_specs['default'].conda_packages

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ""}, check_get_packages)


def test_complain_about_packages_not_a_list():
    def check_get_packages(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        "should be a list of strings not" in project.problems[0]

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
packages:
    foo: bar
    """}, check_get_packages)


def test_complain_about_pip_deps_not_a_list():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        "should be a list of strings not" in project.problems[0]

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
packages:
    - pip: bar
    """}, check)


def test_complain_about_pip_deps_not_a_string():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        "should be a list of pip package names" in project.problems[0]

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
packages:
    - pip:
      - {}
    """}, check)


def test_complain_about_packages_bad_spec():
    def check_get_packages(dirname):
        project = project_no_dedicated_env(dirname)
        filename = project.project_file.basename
        assert [
            "%s: invalid package specification: =" % filename,
            "%s: invalid package specification: foo bar" % filename,
            "%s: invalid pip package specifier: %%" % filename
        ] == project.problems

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
packages:
    - "="
    - foo bar
    - pip:
      - "%"
    """}, check_get_packages)


def test_complain_about_conda_env_in_variables_list():
    def check_complain_about_conda_env_var(dirname):
        project = project_no_dedicated_env(dirname)
        template = (project.project_file.basename + ": Environment variable %s is reserved for Conda's use, " +
                    "so it can't appear in the variables section.")
        assert [template % 'CONDA_ENV_PATH', template % 'CONDA_DEFAULT_ENV',
                template % 'CONDA_PREFIX'] == project.problems

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  - CONDA_ENV_PATH
  - CONDA_DEFAULT_ENV
  - CONDA_PREFIX
    """}, check_complain_about_conda_env_var)


def test_complain_about_conda_env_in_variables_dict():
    def check_complain_about_conda_env_var(dirname):
        project = project_no_dedicated_env(dirname)
        template = (project.project_file.basename + ": Environment variable %s is reserved for Conda's use, " +
                    "so it can't appear in the variables section.")
        assert [template % 'CONDA_ENV_PATH', template % 'CONDA_DEFAULT_ENV',
                template % 'CONDA_PREFIX'] == project.problems

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
variables:
  CONDA_ENV_PATH: {}
  CONDA_DEFAULT_ENV: {}
  CONDA_PREFIX: {}
    """
        }, check_complain_about_conda_env_var)


def test_load_environments():
    def check_environments(dirname):
        project = project_no_dedicated_env(dirname)
        assert 0 == len(project.problems)
        assert len(project.env_specs) == 5
        assert 'foo' in project.env_specs
        assert 'bar' in project.env_specs
        assert 'foo_child' in project.env_specs
        assert 'foo_grandchild' in project.env_specs
        assert 'mixin' in project.env_specs
        assert project.default_env_spec_name == 'foo'
        foo = project.env_specs['foo']
        bar = project.env_specs['bar']
        foo_child = project.env_specs['foo_child']
        foo_grandchild = project.env_specs['foo_grandchild']
        mixin = project.env_specs['mixin']
        assert foo.conda_packages == ('global1=1.0', 'global2=1.0', 'python', 'dog', 'cat', 'zebra')
        assert foo.description == "THE FOO"
        assert foo.pip_packages == ()
        assert foo.channels == ('univision', )
        assert foo.inherit_from == (project.global_base_env_spec, )
        assert bar.conda_packages == ('global1=1.0', 'global2=1.0')
        assert bar.description == "bar"
        assert bar.pip_packages == ()
        assert bar.channels == ('univision', )
        assert bar.inherit_from == (project.global_base_env_spec, )

        assert mixin.conda_packages == ('global1=1.0', 'bunny', 'walrus=1.0', 'global2=2.0')
        assert mixin.pip_packages == ('bear', )
        assert mixin.channels == (
            'univision',
            'hbo',
        )

        assert foo_child.description == 'foo_child'
        assert foo_child.conda_packages == ('global2=1.0', 'python', 'cat', 'zebra', 'dog=2.0', 'global1=2.0', 'lion')
        assert foo_child.pip_packages == ('fish', )
        assert foo_child.channels == (
            'univision',
            'abc',
        )
        assert foo_child.inherit_from == (foo, )

        assert foo_grandchild.description == 'foo_grandchild'
        # the resulting order here is important, and reflects that we linearized
        # the inheritance hierarchy
        assert foo_grandchild.conda_packages == ('python', 'cat', 'zebra', 'global1=2.0', 'lion', 'bunny',
                                                 'global2=2.0', 'walrus=2.0', 'dog=3.0')
        assert foo_grandchild.pip_packages == ('fish', 'bear', 'seahorse')
        assert foo_grandchild.channels == ('univision', 'abc', 'hbo', 'nbc')
        assert foo_grandchild.inherit_from == (foo_child, mixin)

        # While we have this complicated inheritance tree around, be
        # sure we can round-trip save it to environment.yml files
        for spec in (foo, bar, mixin, foo_child, foo_grandchild):
            saved = os.path.join(dirname, "saved-%s" % spec.name)
            spec.save_environment_yml(saved)
            loaded = _load_environment_yml(saved)

            assert loaded.inherit_from == ()
            assert loaded.inherit_from_names == ()
            assert loaded.name == spec.name
            assert loaded.conda_packages == spec.conda_packages
            assert loaded.pip_packages == spec.pip_packages
            assert loaded.channels == spec.channels

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
packages:
  - global1=1.0
  - global2=1.0
channels:
  - univision

env_specs:
  foo:
    description: "THE FOO"
    packages:
       - python
       - dog
       - cat
       - zebra
  bar: {}
  foo_child:
    inherit_from: foo
    packages:
       - dog=2.0
       - global1=2.0
       - lion
       - pip:
          - fish
    channels:
       - abc
  mixin:
    packages:
       - bunny
       - walrus=1.0
       - global2=2.0
       - pip:
         - bear
    channels:
       - hbo
  foo_grandchild:
    inherit_from: [foo_child, mixin]
    packages:
       - walrus=2.0
       - dog=3.0
       - pip:
         - seahorse
    channels:
       - nbc
    """
        }, check_environments)


def test_load_environments_merging_in_global():
    def check_environments(dirname):
        project = project_no_dedicated_env(dirname)
        assert 0 == len(project.problems)
        assert len(project.env_specs) == 3
        assert 'default' in project.env_specs
        assert 'foo' in project.env_specs
        assert 'bar' in project.env_specs
        assert project.default_env_spec_name == 'default'
        default = project.env_specs['default']
        foo = project.env_specs['foo']
        bar = project.env_specs['bar']
        assert default.conda_packages == ('dead-parrot', 'elephant', 'lion')
        assert foo.conda_packages == ('dead-parrot', 'elephant', 'python', 'dog', 'cat', 'zebra')
        assert bar.conda_packages == ('dead-parrot', 'elephant')
        assert default.channels == ('mtv', 'cartoons')
        assert foo.channels == ('mtv', 'hbo')
        assert bar.channels == ('mtv', )

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
packages:
  - dead-parrot
  - elephant

channels:
  - mtv

env_specs:
  foo:
    packages:
       - python
       - dog
       - cat
       - zebra
    channels:
       - hbo
  bar: {}
  default:
    packages:
      - lion
    channels:
      - cartoons
    """
        }, check_environments)


def test_load_environments_default_always_default_even_if_not_first():
    def check_environments(dirname):
        project = project_no_dedicated_env(dirname)
        assert 0 == len(project.problems)
        assert len(project.env_specs) == 3
        assert 'foo' in project.env_specs
        assert 'bar' in project.env_specs
        assert 'default' in project.env_specs
        assert project.default_env_spec_name == 'default'
        foo = project.env_specs['foo']
        bar = project.env_specs['bar']
        default = project.env_specs['default']
        assert foo.conda_packages == ()
        assert bar.conda_packages == ()
        assert default.conda_packages == ()

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
env_specs:
  foo: {}
  bar: {}
  default: {}
    """}, check_environments)


def test_complain_about_environments_not_a_dict():
    def check_environments(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        "should be a directory from environment name to environment attributes" in project.problems[0]

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
env_specs: 42
    """}, check_environments)


def test_complain_about_non_string_environment_description():
    def check_environments(dirname):
        project = project_no_dedicated_env(dirname)
        assert ["%s: 'description' field of environment foo must be a string" % (project.project_file.basename)
                ] == project.problems

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
env_specs:
   foo:
     description: []
    """}, check_environments)


def test_complain_about_non_string_inherit_from():
    def check_environments(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        assert "inherit_from: value should be a list of env spec names" in project.problems[0]

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
env_specs:
   foo:
     inherit_from: {}
    """}, check_environments)


def test_complain_about_packages_list_of_wrong_thing():
    def check_get_packages(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        "should be a string not '42'" in project.problems[0]

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
packages:
    - 42
    """}, check_get_packages)


def test_complain_about_env_spec_inherits_from_nonexistent():
    def check_environments(dirname):
        project = project_no_dedicated_env(dirname)
        assert [
            "%s: name 'bar' in 'inherit_from' field of env spec foo does not match the name of another env spec" %
            (project.project_file.basename)
        ] == project.problems

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
env_specs:
   foo:
      inherit_from: bar
    """}, check_environments)


def test_complain_about_cycle_of_two_env_specs():
    def check_environments(dirname):
        project = project_no_dedicated_env(dirname)
        assert [
            "%s: 'inherit_from' fields create circular inheritance among these env specs: bar, foo" %
            (project.project_file.basename)
        ] == project.problems

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
env_specs:
   foo:
      inherit_from: bar
   bar:
      inherit_from: foo
    """
        }, check_environments)


def test_complain_about_cycle_of_many_env_specs():
    def check_environments(dirname):
        project = project_no_dedicated_env(dirname)
        assert [
            "%s: 'inherit_from' fields create circular inheritance among these env specs: a, b, c, d, e" %
            (project.project_file.basename)
        ] == project.problems

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
env_specs:
   a:
      inherit_from: b
   b:
      inherit_from: c
   c:
      inherit_from: d
   d:
      inherit_from: e
   e:
      inherit_from: a

    """
        }, check_environments)


def test_load_list_of_variables_requirements():
    def check_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        requirements = project.requirements(project.default_env_spec_name)
        assert 3 == len(requirements)
        assert isinstance(requirements[0], EnvVarRequirement)
        assert 'FOO' == requirements[0].env_var
        assert isinstance(requirements[1], EnvVarRequirement)
        assert 'BAR' == requirements[1].env_var
        assert isinstance(requirements[2], CondaEnvRequirement)

        conda_env_var = conda_api.conda_prefix_variable()
        assert conda_env_var == requirements[2].env_var

        assert dict() == requirements[2].options
        assert len(project.problems) == 0

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  - FOO\n  - BAR\n"},
                                                    check_file)


def test_load_dict_of_variables_requirements():
    def check_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        requirements = project.requirements(project.default_env_spec_name)
        assert 3 == len(requirements)
        assert isinstance(requirements[0], EnvVarRequirement)
        assert 'FOO' == requirements[0].env_var
        assert dict(a=1) == requirements[0].options
        assert isinstance(requirements[1], EnvVarRequirement)
        assert 'BAR' == requirements[1].env_var
        assert dict(b=2) == requirements[1].options
        assert isinstance(requirements[2], CondaEnvRequirement)

        conda_env_var = conda_api.conda_prefix_variable()
        assert conda_env_var == requirements[2].env_var

        assert dict() == requirements[2].options
        assert len(project.problems) == 0

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "variables:\n  FOO: { a: 1 }\n  BAR: { b: 2 }\n"}, check_file)


def test_non_string_variables_requirements():
    def check_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = project_no_dedicated_env(dirname)
        assert 2 == len(project.problems)
        requirements = project.requirements(project.default_env_spec_name)
        assert 0 == len(requirements)
        assert "42 is not a string" in project.problems[0]
        assert "43 is not a string" in project.problems[1]

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  - 42\n  - 43\n"},
                                                    check_file)


def test_variable_default_cannot_be_bool():
    def check_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = project_no_dedicated_env(dirname)
        requirements = project.requirements(project.default_env_spec_name)
        assert [] == requirements
        assert 1 == len(project.problems)
        assert "default value for variable FOO must be null, a string, or a number" in project.problems[0]

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  FOO: true\n"}, check_file)


def test_variable_default_cannot_be_list():
    def check_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = project_no_dedicated_env(dirname)
        requirements = project.requirements(project.default_env_spec_name)
        assert [] == requirements
        assert 1 == len(project.problems)
        assert "default value for variable FOO must be null, a string, or a number" in project.problems[0]

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  FOO: []\n"}, check_file)


def test_variable_default_missing_key_field():
    def check(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = project_no_dedicated_env(dirname)
        requirements = project.requirements(project.default_env_spec_name)
        assert [] == requirements
        assert 1 == len(project.problems)
        assert "default value for variable FOO must be null, a string, or a number" in project.problems[0]

    with_directory_contents_completing_project_file(
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
        requirements = project.requirements(project.default_env_spec_name)
        assert 0 == len(requirements)
        assert "variables section contains wrong value type 42" in project.problems[0]

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  42\n"}, check_file)


def test_corrupted_project_file():
    def check_problem(dirname):
        project = project_no_dedicated_env(dirname)
        requirements = project.requirements(project.default_env_spec_name)
        assert 0 == len(requirements)
        assert 1 == len(project.problems)
        assert 'anaconda-project.yml: Syntax error: ' in project.problems[0]

        problem1 = project.problem_objects[0]
        assert problem1.maybe_line_number == 2
        assert problem1.maybe_column_number == 9
        assert problem1.maybe_filename == project.project_file.filename
        assert problem1.text_without_filename.startswith("Syntax error:")

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
^
variables:
  FOO
"""}, check_problem)


def test_corrupted_project_lock_file():
    def check_problem(dirname):
        project = project_no_dedicated_env(dirname)
        requirements = project.requirements(project.default_env_spec_name)
        assert 0 == len(requirements)
        assert 1 == len(project.problems)
        assert 'anaconda-project-lock.yml: Syntax error: ' in project.problems[0]

        problem1 = project.problem_objects[0]
        assert problem1.maybe_line_number == 2
        assert problem1.maybe_column_number == 5
        assert problem1.maybe_filename == project.lock_file.filename
        assert problem1.text_without_filename.startswith("Syntax error:")

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_LOCK_FILENAME: """
^
stuff:
  FOO
"""}, check_problem)


def test_non_dict_commands_section():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: 'commands:' section should be a dictionary from command names to attributes, not %r" % (
            project.project_file.basename, 42)
        assert expected_error == project.problems[0]

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "commands:\n  42\n"}, check_app_entry)


def test_non_dict_services_section():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = ("%s: 'services:' section should be a dictionary from environment variable " +
                          "to service type, found %r") % (project.project_file.basename, 42)
        assert expected_error == project.problems[0]

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "services:\n  42\n"}, check_app_entry)


def test_non_string_as_value_of_command():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: command name '%s' should be followed by a dictionary of attributes not %r" % (
            project.project_file.basename, 'default', 42)
        assert expected_error == project.problems[0]

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "commands:\n default: 42\n"},
                                                    check_app_entry)


def test_empty_command():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: command '%s' does not have a command line in it" % (project.project_file.basename,
                                                                                  'default')
        assert expected_error == project.problems[0]

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "commands:\n default: {}\n"},
                                                    check_app_entry)


def test_command_with_bogus_key():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: command '%s' does not have a command line in it" % (project.project_file.basename,
                                                                                  'default')
        assert expected_error == project.problems[0]

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    foobar: 'boo'\n"}, check_app_entry)


def test_command_with_non_string_description():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: 'description' field of command %s must be a string" % (project.project_file.basename,
                                                                                     'default')
        assert expected_error == project.problems[0]

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n     unix: 'boo'\n     description: []\n"}, check)


def test_command_with_non_boolean_supports_http_options():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: 'supports_http_options' field of command %s must be a boolean" % (
            project.project_file.basename, 'default')
        assert expected_error == project.problems[0]

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n     unix: 'boo'\n     supports_http_options: 'blah'\n"},
        check)


def test_command_with_non_boolean_registers_fusion_function():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: 'registers_fusion_function' field of command %s must be a boolean" % (
            project.project_file.basename, 'default')
        assert expected_error == project.problems[0]

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n     unix: 'boo'\n     registers_fusion_function: 'blah'\n"},
        check)


def test_command_with_extras():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.extras == {"registers_fusion_function": True}

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n     unix: 'boo'\n     registers_fusion_function: true\n"},
        check)


def test_command_with_custom_description():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        command = project.default_command
        assert command.bokeh_app == 'test.py'
        assert command.description == 'hi'

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            "commands:\n default:\n    bokeh_app: test.py\n    description: hi\npackages:\n - bokeh\n"
        }, check)


def test_command_with_non_string_env_spec():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        expected_error = "%s: 'env_spec' field of command %s must be a string (an environment spec name)" % (
            project.project_file.basename, 'default')
        assert [expected_error] == project.problems

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n     unix: 'boo'\n     env_spec: []\n"}, check)


def test_command_with_nonexistent_env_spec():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        expected_error = "%s: env_spec 'boo' for command '%s' does not appear in the env_specs section" % (
            project.project_file.basename, 'default')
        assert [expected_error] == project.problems

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n     unix: 'boo'\n     env_spec: boo\n"}, check)


def test_command_with_many_problems_at_once():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        expected_errors = [
            "%s: 'description' field of command default must be a string",
            "%s: env_spec 'nonexistent' for command 'default' does not appear in the env_specs section",
            "%s: command 'default' has multiple commands in it, 'notebook' can't go with 'unix'"
        ]
        expected_errors = list(map(lambda e: e % project.project_file.basename, expected_errors))
        assert expected_errors == project.problems

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
commands:
  default:
     unix: bar
     notebook: foo.ipynb
     env_spec: nonexistent
     description: []
        """
        }, check)


def test_command_with_bogus_key_and_ok_key():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        command = project.default_command
        assert command.name == 'default'
        assert command.unix_shell_commandline == 'bar'

        assert command.windows_cmd_commandline is None
        assert command.conda_app_entry is None

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    foobar: 'boo'\n\n    unix: 'bar'\n"}, check_app_entry)


def test_two_empty_commands():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert 2 == len(project.problems)
        expected_error_1 = "%s: command '%s' does not have a command line in it" % (project.project_file.basename,
                                                                                    'foo')
        expected_error_2 = "%s: command '%s' does not have a command line in it" % (project.project_file.basename,
                                                                                    'bar')
        assert expected_error_1 == project.problems[0]
        assert expected_error_2 == project.problems[1]

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "commands:\n foo: {}\n bar: {}\n"},
                                                    check_app_entry)


def test_non_string_as_value_of_conda_app_entry():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: command '%s' attribute '%s' should be a string not '%r'" % (
            project.project_file.basename, 'default', 'conda_app_entry', 42)
        assert expected_error == project.problems[0]

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    conda_app_entry: 42\n"}, check_app_entry)


def test_non_string_as_value_of_shell():
    def check_shell_non_dict(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: command '%s' attribute '%s' should be a string not '%r'" % (project.project_file.basename,
                                                                                          'default', 'unix', 42)
        assert expected_error == project.problems[0]

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    unix: 42\n"},
                                                    check_shell_non_dict)


def test_unix_template_command():
    def check_template_command(dirname):
        project = project_no_dedicated_env(dirname)
        command = project.default_command
        assert command.supports_http_options is False
        assert command.unix_shell_commandline == 'test {{port}}'
        assert command.windows_cmd_commandline is None
        assert command.conda_app_entry is None

        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(environ, extra_args=['--anaconda-project-port', '8888'])
        if cmd_exec is not None:
            assert cmd_exec.args == ['test 8888']
            assert cmd_exec.shell is True
        else:
            raise SkipTest

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    unix: test {{port}}\n    supports_http_options: false"},
        check_template_command)


def test_unix_template_command_with_extra_args():
    def check_template_command(dirname):
        project = project_no_dedicated_env(dirname)
        command = project.default_command
        assert command.supports_http_options is False
        assert command.unix_shell_commandline == 'test {{port}}'
        assert command.windows_cmd_commandline is None
        assert command.conda_app_entry is None

        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(
            environ, extra_args=['--anaconda-project-port', '8888', "--extra-arg-example", "foo"])
        if cmd_exec is not None:
            assert cmd_exec.args == ['test 8888 --extra-arg-example foo']
            assert cmd_exec.shell is True
        else:
            raise SkipTest

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    unix: test {{port}}\n    supports_http_options: false"},
        check_template_command)


def test_windows_template_command():
    def check_template_command(dirname):
        project = project_no_dedicated_env(dirname)
        command = project.default_command
        assert command.supports_http_options is False
        assert command.unix_shell_commandline is None
        assert command.windows_cmd_commandline == 'test {{port}}'
        assert command.conda_app_entry is None

        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(environ, extra_args=['--anaconda-project-port', '8888'])
        if cmd_exec is not None:
            assert cmd_exec.args == ['test 8888']
            assert cmd_exec.shell is True
        else:
            raise SkipTest

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            "commands:\n default:\n    windows: test {{port}}\n    supports_http_options: false"
        }, check_template_command)


def test_windows_template_command_with_extra_args():
    def check_template_command(dirname):
        project = project_no_dedicated_env(dirname)
        command = project.default_command
        assert command.supports_http_options is False
        assert command.unix_shell_commandline is None
        assert command.windows_cmd_commandline == 'test {{port}}'
        assert command.conda_app_entry is None

        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(
            environ, extra_args=['--anaconda-project-port', '8888', '--extra-arg-example', 'foo'])
        if cmd_exec is not None:
            assert cmd_exec.args == ['test 8888 --extra-arg-example foo']
            assert cmd_exec.shell is True
        else:
            raise SkipTest

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            "commands:\n default:\n    windows: test {{port}}\n    supports_http_options: false"
        }, check_template_command)


def test_notebook_command():
    def check_notebook_command(dirname):
        project = project_no_dedicated_env(dirname)
        command = project.default_command
        assert command.notebook == 'test.ipynb'
        assert command.unix_shell_commandline is None
        assert command.windows_cmd_commandline is None
        assert command.conda_app_entry is None

        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(environ)
        path = os.pathsep.join([environ['PROJECT_DIR'], environ['PATH']])
        jupyter_notebook = _assert_find_executable('jupyter-notebook', path)
        assert cmd_exec.args == [
            jupyter_notebook,
            os.path.join(dirname, 'test.ipynb'), '--NotebookApp.default_url=/notebooks/test.ipynb'
        ]
        assert cmd_exec.shell is False

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    notebook: test.ipynb\n"}, check_notebook_command)


def test_notebook_command_extra_args():
    def check_notebook_command_extra_args(dirname):
        project = project_no_dedicated_env(dirname)
        command = project.default_command
        assert command.notebook == 'test.ipynb'
        assert command.unix_shell_commandline is None
        assert command.windows_cmd_commandline is None
        assert command.conda_app_entry is None

        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(environ, extra_args=['foo', 'bar'])
        path = os.pathsep.join([environ['PROJECT_DIR'], environ['PATH']])
        jupyter_notebook = _assert_find_executable('jupyter-notebook', path)
        assert cmd_exec.args == [
            jupyter_notebook,
            os.path.join(dirname, 'test.ipynb'), '--NotebookApp.default_url=/notebooks/test.ipynb', 'foo', 'bar'
        ]
        assert cmd_exec.shell is False

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    notebook: test.ipynb\n"},
        check_notebook_command_extra_args)


def test_notebook_command_with_project_http_args():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        command = project.default_command
        assert command.notebook == 'test.ipynb'
        assert command.unix_shell_commandline is None
        assert command.windows_cmd_commandline is None
        assert command.conda_app_entry is None

        assert command.supports_http_options

        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(environ,
                                                     extra_args=[
                                                         'foo', 'bar', '--anaconda-project-url-prefix', 'blah',
                                                         '--anaconda-project-port', '1234', '--anaconda-project-host',
                                                         'example.com', '--anaconda-project-no-browser',
                                                         '--anaconda-project-iframe-hosts=foo1.com *.foo2.com',
                                                         '--anaconda-project-use-xheaders',
                                                         '--anaconda-project-address', '1.2.3.4'
                                                     ])
        path = os.pathsep.join([environ['PROJECT_DIR'], environ['PATH']])
        jupyter_notebook = _assert_find_executable('jupyter-notebook', path)
        assert cmd_exec.args == [
            jupyter_notebook,
            os.path.join(dirname, 'test.ipynb'), '--NotebookApp.default_url=/notebooks/test.ipynb', '--ip', '1.2.3.4',
            '--NotebookApp.tornado_settings=' +
            """{ 'headers': { 'Content-Security-Policy': "frame-ancestors 'self' foo1.com *.foo2.com" } }""",
            '--no-browser', '--port', '1234', '--NotebookApp.base_url=blah', '--NotebookApp.trust_xheaders=True', 'foo',
            'bar'
        ]
        assert cmd_exec.shell is False

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    notebook: test.ipynb\n"}, check)


def test_notebook_command_disabled_project_http_args():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        command = project.default_command
        assert command.notebook == 'test.ipynb'
        assert command.unix_shell_commandline is None
        assert command.windows_cmd_commandline is None
        assert command.conda_app_entry is None

        assert not command.supports_http_options

        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(environ,
                                                     extra_args=[
                                                         'foo', 'bar', '--anaconda-project-url-prefix', 'blah',
                                                         '--anaconda-project-port', '1234', '--anaconda-project-host',
                                                         'example.com', '--anaconda-project-no-browser',
                                                         '--anaconda-project-use-xheaders',
                                                         '--anaconda-project-address', '1.2.3.4'
                                                     ])
        path = os.pathsep.join([environ['PROJECT_DIR'], environ['PATH']])
        jupyter_notebook = _assert_find_executable('jupyter-notebook', path)
        assert cmd_exec.args == [jupyter_notebook, os.path.join(dirname, 'test.ipynb'), 'foo', 'bar']
        assert cmd_exec.shell is False

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            "commands:\n default:\n    notebook: test.ipynb\n    supports_http_options: false\n"
        }, check)


def test_notebook_command_project_http_args_after_double_hyphen():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        command = project.default_command
        assert command.notebook == 'test.ipynb'
        assert command.unix_shell_commandline is None
        assert command.windows_cmd_commandline is None
        assert command.conda_app_entry is None

        assert command.supports_http_options

        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(environ,
                                                     extra_args=[
                                                         '--', 'foo', 'bar', '--anaconda-project-url-prefix', 'blah',
                                                         '--anaconda-project-port', '1234', '--anaconda-project-host',
                                                         'example.com', '--anaconda-project-no-browser',
                                                         '--anaconda-project-use-xheaders'
                                                     ])
        path = os.pathsep.join([environ['PROJECT_DIR'], environ['PATH']])
        jupyter_notebook = _assert_find_executable('jupyter-notebook', path)
        assert cmd_exec.args == [
            jupyter_notebook,
            os.path.join(dirname, 'test.ipynb'), '--NotebookApp.default_url=/notebooks/test.ipynb', '--', 'foo', 'bar',
            '--anaconda-project-url-prefix', 'blah', '--anaconda-project-port', '1234', '--anaconda-project-host',
            'example.com', '--anaconda-project-no-browser', '--anaconda-project-use-xheaders'
        ]
        assert cmd_exec.shell is False

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    notebook: test.ipynb\n"}, check)


def test_notebook_command_with_project_http_args_separated_by_equals():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        command = project.default_command
        assert command.notebook == 'test.ipynb'
        assert command.unix_shell_commandline is None
        assert command.windows_cmd_commandline is None
        assert command.conda_app_entry is None

        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(environ,
                                                     extra_args=[
                                                         'foo', 'bar', '--anaconda-project-url-prefix=blah',
                                                         '--anaconda-project-port=1234',
                                                         '--anaconda-project-host=example.com',
                                                         '--anaconda-project-no-browser',
                                                         '--anaconda-project-address=1.2.3.4'
                                                     ])
        path = os.pathsep.join([environ['PROJECT_DIR'], environ['PATH']])
        jupyter_notebook = _assert_find_executable('jupyter-notebook', path)
        assert cmd_exec.args == [
            jupyter_notebook,
            os.path.join(dirname, 'test.ipynb'), '--NotebookApp.default_url=/notebooks/test.ipynb', '--ip', '1.2.3.4',
            '--no-browser', '--port', '1234', '--NotebookApp.base_url=blah', 'foo', 'bar'
        ]
        assert cmd_exec.shell is False

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    notebook: test.ipynb\n"}, check)


def test_notebook_guess_command():
    def check_notebook_guess_command(dirname):
        project = project_no_dedicated_env(dirname)

        assert ["%s: No command runs notebook test.ipynb" % project.project_file.basename] == project.suggestions

        project.suggestion_objects[0].fix(project)
        project.project_file.save()

        assert 'test.ipynb' in project.commands
        assert 'default' in project.commands
        assert len(project.commands) == 2  # we should have ignored all the ignored ones
        assert project.default_command.name == 'default'

        command = project.commands['test.ipynb']
        assert command.notebook == 'test.ipynb'
        assert command.unix_shell_commandline is None
        assert command.windows_cmd_commandline is None
        assert command.conda_app_entry is None

        expected_nb_path = os.path.join(dirname, 'test.ipynb')
        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(environ)
        path = os.pathsep.join([environ['PROJECT_DIR'], environ['PATH']])
        jupyter_notebook = _assert_find_executable('jupyter-notebook', path)
        assert cmd_exec.args == [jupyter_notebook, expected_nb_path, '--NotebookApp.default_url=/notebooks/test.ipynb']
        assert cmd_exec.shell is False

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            "commands:\n default:\n    unix: echo 'pass'\nservices:\n    REDIS_URL: redis\npackages: ['notebook']\n",
            'test.ipynb': '{}',
            'envs/should_ignore_this.ipynb': '{}',
            'services/should_ignore_this.ipynb': '{}',
            '.should_ignore_dotfile.ipynb': '{}',
            '.should_ignore_dotdir/foo.ipynb': '{}'
        }, check_notebook_guess_command)

    # anaconda-project run data.ipynb


def test_notebook_guess_command_can_be_default():
    def check_notebook_guess_command_can_be_default(dirname):
        project = project_no_dedicated_env(dirname)

        assert [
            "%s: No commands run notebooks a.ipynb, b.ipynb, c.ipynb, d/d.ipynb, e.ipynb, f.ipynb" %
            project.project_file.basename
        ] == project.suggestions

        project.suggestion_objects[0].fix(project)
        project.project_file.save()

        assert [] == project.problems
        assert len(project.commands) == 6
        assert project.default_command is not None
        assert project.default_command.notebook == 'a.ipynb'
        assert ['a.ipynb', 'b.ipynb', 'c.ipynb', 'd/d.ipynb', 'e.ipynb',
                'f.ipynb'] == sorted([c for c in project.commands])

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: "packages: ['notebook']\n",
            # we pick the first command alphabetically in this case
            # so the test looks for that
            'a.ipynb': '{}',
            'b.ipynb': '{}',
            'c.ipynb': '{}',
            'd/d.ipynb': '{}',
            'e.ipynb': '{}',
            'f.ipynb': '{}'
        },
        check_notebook_guess_command_can_be_default)


def test_notebook_command_jupyter_not_on_path(monkeypatch):
    def check_notebook_command(dirname):
        project = project_no_dedicated_env(dirname)
        command = project.default_command
        assert command.notebook == 'test.ipynb'

        environ = minimal_environ(PROJECT_DIR=dirname)

        def mock_find_executable(*args, **kwargs):
            return None

        monkeypatch.setattr('distutils.spawn.find_executable', mock_find_executable)

        cmd_exec = command.exec_info_for_environment(environ)
        assert 'jupyter-notebook' in cmd_exec.args[0]
        assert cmd_exec.args[1:] == [
            os.path.join(dirname, 'test.ipynb'), '--NotebookApp.default_url=/notebooks/test.ipynb'
        ]
        assert cmd_exec.shell is False

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    notebook: test.ipynb\n"}, check_notebook_command)


def test_multiple_notebooks_suggestion_rejected():
    def check(dirname):
        project = project_no_dedicated_env(dirname)

        assert ["%s: No commands run notebooks foo/test2.ipynb, test.ipynb" % project.project_file.basename
                ] == project.suggestions

        project.suggestion_objects[0].no_fix(project)
        project.project_file.save()

        assert 'test.ipynb' not in project.commands
        assert 'foo/test2.ipynb' not in project.commands
        assert 'default' in project.commands
        assert len(project.commands) == 1  # we should have ignored all the ignored ones
        assert project.default_command.name == 'default'

        # now we're skipping the import so it should have gone away
        assert project.suggestions == []

        assert ['foo/test2.ipynb', 'test.ipynb'] == project.project_file.get_value(['skip_imports', 'notebooks'])

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            "commands:\n default:\n    unix: echo 'pass'\nservices:\n    REDIS_URL: redis\npackages: ['notebook']\n",
            'test.ipynb': '{}',
            'foo/test2.ipynb': '{}',
            'envs/should_ignore_this.ipynb': 'pretend this is more notebook data',
            'services/should_ignore_this.ipynb': 'pretend this is more notebook data',
            '.should_ignore_dotfile.ipynb': 'moar fake notebook',
            '.should_ignore_dotdir/foo.ipynb': 'still moar fake notebook'
        }, check)


def test_skip_all_notebook_imports():
    def check(dirname):
        project = project_no_dedicated_env(dirname)

        assert [] == project.problems
        assert ["%s: No command runs notebook test.ipynb" % project.project_file.basename] == project.suggestions

        project.project_file.set_value(['skip_imports', 'notebooks'], True)
        project.project_file.save()

        assert [] == project.suggestions
        assert [] == project.problems

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            "commands:\n default:\n    unix: echo 'pass'\nservices:\n    REDIS_URL: redis\npackages: ['notebook']\n",
            'test.ipynb': '{}'
        }, check)


def test_invalid_skip_imports_notebooks():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        assert "'skip_imports: notebooks:' value should be a list" in project.problems[0]
        assert [] == project.suggestions

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: ("commands:\n default:\n    unix: echo 'pass'\nservices:\n" +
                                       "  REDIS_URL: redis\npackages: ['notebook']\nskip_imports:\n  notebooks: {}\n")
        }, check)


def test_single_notebook_suggestion_rejected():
    def check(dirname):
        project = project_no_dedicated_env(dirname)

        assert ["%s: No command runs notebook test.ipynb" % project.project_file.basename] == project.suggestions

        project.suggestion_objects[0].no_fix(project)
        project.project_file.save()

        assert 'test.ipynb' not in project.commands
        assert 'default' in project.commands
        assert len(project.commands) == 1  # we should have ignored all the ignored ones
        assert project.default_command.name == 'default'

        # now we're skipping the import so it should have gone away
        assert project.suggestions == []

        assert ['test.ipynb'] == project.project_file.get_value(['skip_imports', 'notebooks'])

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            "commands:\n default:\n    unix: echo 'pass'\nservices:\n    REDIS_URL: redis\npackages: ['notebook']\n",
            'test.ipynb': '{}',
            'envs/should_ignore_this.ipynb': 'pretend this is more notebook data',
            'services/should_ignore_this.ipynb': 'pretend this is more notebook data',
            '.should_ignore_dotfile.ipynb': 'moar fake notebook',
            '.should_ignore_dotdir/foo.ipynb': 'still moar fake notebook'
        }, check)


def test_notebook_command_conflict():
    def check_notebook_conflict_command(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: command '%s' has multiple commands in it, 'notebook' can't go with 'unix'" % (
            project.project_file.basename, 'default')
        assert expected_error == project.problems[0]

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    notebook: test.ipynb\n    unix: echo 'pass'"},
        check_notebook_conflict_command)


def test_bokeh_command_conflict():
    def check_bokeh_conflict_command(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: command '%s' has multiple commands in it, 'bokeh_app' can't go with 'unix'" % (
            project.project_file.basename, 'default')
        assert expected_error == project.problems[0]

    with_directory_contents_completing_project_file(
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

        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(environ)
        path = os.pathsep.join([environ['PROJECT_DIR'], environ['PATH']])
        bokeh = _assert_find_executable('bokeh', path)
        assert cmd_exec.args == [bokeh, 'serve', os.path.join(dirname, 'test.py'), '--show']
        assert cmd_exec.shell is False

    with_directory_contents_completing_project_file(
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

        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(environ, extra_args=['--foo'])
        path = os.pathsep.join([environ['PROJECT_DIR'], environ['PATH']])
        bokeh = _assert_find_executable('bokeh', path)
        assert cmd_exec.args == [bokeh, 'serve', os.path.join(dirname, 'test.py'), '--show', '--foo']
        assert cmd_exec.shell is False

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    bokeh_app: test.py\n"}, check_bokeh_command_extra_args)


def test_bokeh_command_with_project_http_args():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        command = project.default_command
        assert command.bokeh_app == 'test.py'
        assert command.notebook is None
        assert command.unix_shell_commandline is None
        assert command.windows_cmd_commandline is None
        assert command.conda_app_entry is None
        assert command.supports_http_options

        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(environ,
                                                     extra_args=[
                                                         '--foo', '--anaconda-project-url-prefix', 'blah',
                                                         '--anaconda-project-port', '1234', '--anaconda-project-host',
                                                         'example.com', '--anaconda-project-no-browser',
                                                         '--anaconda-project-iframe-hosts=foo1.com *.foo2.com',
                                                         '--anaconda-project-use-xheaders',
                                                         '--anaconda-project-address', '1.2.3.4'
                                                     ])
        path = os.pathsep.join([environ['PROJECT_DIR'], environ['PATH']])
        bokeh = _assert_find_executable('bokeh', path)
        assert cmd_exec.args == [
            bokeh, 'serve',
            os.path.join(dirname, 'test.py'), '--address', '1.2.3.4', '--host', 'example.com', '--port', '1234',
            '--prefix', 'blah', '--use-xheaders', '--foo'
        ]
        assert cmd_exec.shell is False

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    bokeh_app: test.py\n"}, check)


def test_bokeh_command_with_multiple_host_args():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        command = project.default_command
        assert command.bokeh_app == 'test.py'
        assert command.notebook is None
        assert command.unix_shell_commandline is None
        assert command.windows_cmd_commandline is None
        assert command.conda_app_entry is None
        assert command.supports_http_options

        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(
            environ, extra_args=['--anaconda-project-host', 'example.com', '--anaconda-project-host', 'example2.com'])
        path = os.pathsep.join([environ['PROJECT_DIR'], environ['PATH']])
        bokeh = _assert_find_executable('bokeh', path)
        assert cmd_exec.args == [
            bokeh, 'serve',
            os.path.join(dirname, 'test.py'), '--host', 'example.com', '--host', 'example2.com', '--show'
        ]
        assert cmd_exec.shell is False

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    bokeh_app: test.py\n"}, check)


def test_bokeh_command_with_multiple_iframe_hosts_args():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        command = project.default_command
        assert command.bokeh_app is None
        assert command.notebook == "test.ipynb"
        assert command.unix_shell_commandline is None
        assert command.windows_cmd_commandline is None
        assert command.conda_app_entry is None
        assert command.supports_http_options

        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(environ,
                                                     extra_args=[
                                                         '--anaconda-project-iframe-hosts', 'example.com',
                                                         '--anaconda-project-iframe-hosts', 'foo1.com *.foo2.com'
                                                     ])
        path = os.pathsep.join([environ['PROJECT_DIR'], environ['PATH']])
        jupyter = _assert_find_executable('jupyter-notebook', path)
        assert cmd_exec.args == [
            jupyter,
            os.path.join(dirname, 'test.ipynb'), '--NotebookApp.default_url=/notebooks/test.ipynb',
            '--NotebookApp.tornado_settings=' +
            """{ 'headers': { 'Content-Security-Policy': "frame-ancestors 'self' example.com foo1.com *.foo2.com" } }"""
        ]
        assert cmd_exec.shell is False

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    notebook: test.ipynb\n"}, check)


def test_bokeh_command_with_value_missing_for_project_http_args():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        command = project.default_command
        assert command.bokeh_app == 'test.py'
        assert command.notebook is None
        assert command.unix_shell_commandline is None
        assert command.windows_cmd_commandline is None
        assert command.conda_app_entry is None
        assert command.supports_http_options

        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(environ,
                                                     extra_args=[
                                                         '--foo', '--anaconda-project-url-prefix',
                                                         '--anaconda-project-port', '--anaconda-project-host',
                                                         '--anaconda-project-address'
                                                     ])
        path = os.pathsep.join([environ['PROJECT_DIR'], environ['PATH']])
        bokeh = _assert_find_executable('bokeh', path)
        assert cmd_exec.args == [
            bokeh, 'serve',
            os.path.join(dirname, 'test.py'), '--address', '', '--host', '', '--show', '--port', '', '--prefix', '',
            '--foo'
        ]
        assert cmd_exec.shell is False

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    bokeh_app: test.py\n"}, check)


def test_bokeh_command_with_disabled_project_http_args():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        command = project.default_command
        assert command.bokeh_app == 'test.py'
        assert command.notebook is None
        assert command.unix_shell_commandline is None
        assert command.windows_cmd_commandline is None
        assert command.conda_app_entry is None
        assert not command.supports_http_options

        environ = minimal_environ(PROJECT_DIR=dirname)
        cmd_exec = command.exec_info_for_environment(environ,
                                                     extra_args=[
                                                         '--foo', '--anaconda-project-url-prefix', 'blah',
                                                         '--anaconda-project-port', '1234', '--anaconda-project-host',
                                                         'example.com', '--anaconda-project-no-browser',
                                                         '--anaconda-project-use-xheaders'
                                                     ])
        path = os.pathsep.join([environ['PROJECT_DIR'], environ['PATH']])
        bokeh = _assert_find_executable('bokeh', path)
        assert cmd_exec.args == [bokeh, 'serve', os.path.join(dirname, 'test.py'), '--foo']
        assert cmd_exec.shell is False

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n default:\n    bokeh_app: test.py\n    supports_http_options: false\n"},
        check)


def test_run_argv_from_project_file_app_entry():
    def check_run_argv(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        command = project.default_command
        assert command.name == 'foo'
        assert command.conda_app_entry == "foo bar ${PREFIX}"

        assert 1 == len(project.commands)
        assert 'foo' in project.commands
        assert project.commands['foo'] is command

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  foo:
    conda_app_entry: foo bar ${PREFIX}
"""}, check_run_argv)


def test_run_argv_from_project_file_shell():
    def check_run_argv(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        command = project.default_command
        assert command.name == 'foo'
        assert command.unix_shell_commandline == "foo bar ${PREFIX}"

        assert 1 == len(project.commands)
        assert 'foo' in project.commands
        assert project.commands['foo'] is command

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  foo:
    unix: foo bar ${PREFIX}
"""}, check_run_argv)


def test_run_argv_from_project_file_windows(monkeypatch):
    def check_run_argv(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        command = project.default_command
        assert command.name == 'foo'
        assert command.windows_cmd_commandline == "foo bar %CONDA_DEFAULT_ENV%"
        assert command.unix_shell_commandline is None

        assert 1 == len(project.commands)
        assert 'foo' in project.commands
        assert project.commands['foo'] is command

        def mock_platform_system():
            return 'Windows'

        monkeypatch.setattr('platform.system', mock_platform_system)

        environ = minimal_environ(PROJECT_DIR=dirname)

        exec_info = project.default_exec_info_for_environment(environ)
        assert exec_info.shell

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  foo:
    windows: foo bar %CONDA_DEFAULT_ENV%
"""}, check_run_argv)


def test_exec_info_is_none_when_no_commands():
    def check_exec_info(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        command = project.default_command
        assert command is None

        environ = minimal_environ(PROJECT_DIR=dirname)

        exec_info = project.default_exec_info_for_environment(environ)
        assert exec_info is None

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
"""}, check_exec_info)


def test_exec_info_is_none_when_command_not_for_our_platform():
    def check_exec_info(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        command = project.default_command
        assert command is not None
        assert command.name == 'foo'

        environ = minimal_environ(PROJECT_DIR=dirname)

        exec_info = project.default_exec_info_for_environment(environ)
        assert exec_info is None

    import platform
    not_us = 'windows'
    if platform.system() == 'Windows':
        not_us = 'unix'
    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  foo:
    %s: foo
""" % not_us}, check_exec_info)


def _run_argv_for_environment(environ=None, expected_output=None, chdir=False, os_specific=False, extra_args=None):
    environ = minimal_environ(**(environ or {}))

    prefix_var = conda_api.conda_prefix_variable() if os_specific else 'PREFIX'
    if platform.system() == 'Windows':
        echo_stuff = 'echo_stuff.bat'
        echo_path = '%PROJECT_DIR%\\\\' + echo_stuff
        prefix_var = '%{}%'.format(prefix_var)
        command_name = 'windows'
    else:
        echo_stuff = 'echo_stuff.sh'
        echo_path = '${PROJECT_DIR}/' + echo_stuff
        prefix_var = '${%s}' % prefix_var
        command_name = 'unix'
    if not os_specific:
        command_name = 'conda_app_entry'
        echo_path = echo_stuff
    if expected_output is None:
        args = ' '.join(['foo', 'bar'] + (extra_args or []))
        expected_output = conda_api.environ_get_prefix(os.environ) + ' ' + args
    command_line = '%s: "%s %s foo bar"' % (command_name, echo_path, prefix_var)
    print('YAML command line: %s' % command_line)
    print('Expected output: %s' % expected_output)
    print('Current directory: %s' % os.getcwd())
    print('Path: %s' % os.environ.get('PATH'))

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
            exec_info = project.default_exec_info_for_environment(environ, extra_args=extra_args)
            if exec_info.shell:
                args = exec_info.args[0]
            else:
                args = exec_info.args
            print('Command args: %s' % repr(args))
            print('Using shell: %s' % str(exec_info.shell))
            output = subprocess.check_output(args, shell=exec_info.shell, env=environ).decode()
            # strip() removes \r\n or \n so we don't have to deal with the difference
            print('Actual output: %s' % output.strip())
            assert output.strip() == expected_output.format(dirname=dirname)
        finally:
            if old_dir is not None:
                print("Changing back to %s from %s" % (old_dir, dirname), file=sys.stderr)
                os.chdir(old_dir)
            # this should happen automatically but it's failing sometimes on
            # Windows maybe because of a race where echo_stuff.bat is still
            # in use.
            batscript = os.path.join(dirname, "echo_stuff.bat")
            attempts = 6
            print("os.path.exists(%s) = %s" % (batscript, repr(os.path.exists(batscript))), file=sys.stderr)
            print("before remove, os.stat(%s) = %r" % (batscript, os.stat(batscript)))
            print("before remove, os.stat(%s) = %r" % (dirname, os.stat(dirname)))
            while attempts > 0 and os.path.exists(batscript):
                try:
                    print("Attempting to remove %s" % (batscript), file=sys.stderr)
                    os.remove(batscript)
                except Exception as e:
                    print("Failed to remove %s: %s" % (batscript, str(e)), file=sys.stderr)
                    time.sleep(1)
                    attempts = attempts - 1
                else:
                    print("os.remove did not throw removing %s" % (batscript), file=sys.stderr)
                    print("after remove, os.path.exists(%s) = %s" % (batscript, repr(os.path.exists(batscript))),
                          file=sys.stderr)
                    try:
                        print("after remove, os.stat(%s) = %r" % (batscript, os.stat(batscript)))
                    except Exception:
                        print("after remove, could not stat the script")

                    try:
                        print("after remove, files in %s: %r" % (dirname, os.listdir(dirname)), file=sys.stderr)
                    except Exception:
                        pass

    with_directory_contents_completing_project_file(
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


def test_run_command_in_project_dir():
    # We can't use a generic command name with Windows batch files
    if platform.system() != 'Windows':
        _run_argv_for_environment(os_specific=False, extra_args=[])


def test_run_command_in_project_dir_extra_args():
    # We can't use a generic command name with Windows batch files
    if platform.system() != 'Windows':
        _run_argv_for_environment(os_specific=False, extra_args=["baz"])


def test_run_command_in_project_dir_os_specific(monkeypatch):
    _run_argv_for_environment(os_specific=True, extra_args=[])


def test_run_command_in_project_dir_os_specific_extra_args(monkeypatch):
    _run_argv_for_environment(os_specific=True, extra_args=["baz"])


def test_run_command_in_project_dir_os_specific_and_cwd_is_project_dir():
    # We can't use a generic command name with Windows batch files
    _run_argv_for_environment(os_specific=True, extra_args=[], chdir=True)


def test_run_command_in_project_dir_os_specific_with_conda_env():
    _run_argv_for_environment(dict(CONDA_PREFIX='/someplace',
                                   CONDA_ENV_PATH='/someplace',
                                   CONDA_DEFAULT_ENV='/someplace'),
                              "/someplace foo bar",
                              os_specific=True)


def test_run_command_is_on_system_path():
    def check_python_version_output(dirname):
        environ = minimal_environ(PROJECT_DIR=dirname)
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        exec_info = project.default_exec_info_for_environment(environ)
        output = subprocess.check_output(exec_info.args, shell=exec_info.shell, stderr=subprocess.STDOUT).decode()
        assert output.startswith("Python")

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  default:
    conda_app_entry: python --version
"""}, check_python_version_output)


def test_run_command_does_not_exist():
    def check_error_on_nonexistent_path(dirname):
        import errno
        environ = minimal_environ(PROJECT_DIR=dirname)
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        exec_info = project.default_exec_info_for_environment(environ)
        assert exec_info.args[0] == 'this-command-does-not-exist'
        try:
            FileNotFoundError  # noqa
        except NameError:
            # python 2
            FileNotFoundError = OSError
        with pytest.raises(FileNotFoundError) as excinfo:
            subprocess.check_output(exec_info.args, stderr=subprocess.STDOUT, shell=exec_info.shell).decode()
        assert excinfo.value.errno == errno.ENOENT

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  default:
    conda_app_entry: this-command-does-not-exist
"""}, check_error_on_nonexistent_path)


def test_run_command_stuff_missing_from_environment():
    def check_run_with_stuff_missing(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        environ = minimal_environ(PROJECT_DIR=dirname)
        conda_var = conda_api.conda_prefix_variable()
        for key in ('PATH', conda_var, 'PROJECT_DIR'):
            environ_copy = deepcopy(environ)
            del environ_copy[key]
            with pytest.raises(ValueError) as excinfo:
                project.default_exec_info_for_environment(environ_copy)
            assert ('%s must be set' % key) in repr(excinfo.value)

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
commands:
  default:
    conda_app_entry: foo
"""}, check_run_with_stuff_missing)


def test_get_publication_info_from_empty_project():
    def check_publication_info_from_empty(dirname):
        project = project_no_dedicated_env(dirname)
        expected = {
            'name': os.path.basename(dirname),
            'url_friendly_name': os.path.basename(dirname),
            'description': '',
            'anaconda_project_version': version,
            'commands': {},
            'env_specs': {
                'default': {
                    'channels': [],
                    'packages': [],
                    'description': 'Default',
                    'locked': False,
                    'platforms': [],
                    'variables': {},
                    'downloads': {},
                    'services': {}
                }
            },
        }
        assert expected == project.publication_info()

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
env_specs:
  default:
    description: "Default"
    """}, check_publication_info_from_empty)


_complicated_project_contents = """
name: foo bar
description: "A very complicated project."

commands:
  foo:
    unix: echo hi
    description: "say hi"
    supports_http_options: true
  bar:
    windows: echo boo
    env_spec: lol
  baz:
    conda_app_entry: echo blah
  myapp:
    bokeh_app: main.py
    env_spec: woot
  foo.ipynb:
    description: 'Notebook foo.ipynb'
    notebook: foo.ipynb
    registers_fusion_function: true

packages:
  - foo

channels:
  - bar

env_specs:
  default:
    description: "Default"
    packages:
      - notebook
  woot:
    packages:
      - blah
      - bokeh
    channels:
      - woohoo
  w00t:
    description: "double 0"
    packages:
      - something
  lol: {}

downloads:
  FOO: https://example.com/blah

services:
  REDIS_URL: redis

variables:
  SOMETHING: {}
  SOMETHING_ELSE:
     default: 42
"""


def test_get_publication_info_from_complex_project():
    def check_publication_info_from_complex(dirname):
        project = project_no_dedicated_env(dirname)

        expected = {
            'name': 'foo bar',
            'url_friendly_name': 'foo-bar',
            'description': 'A very complicated project.',
            'anaconda_project_version': version,
            'commands': {
                'bar': {
                    'description': 'echo boo',
                    'env_spec': 'lol',
                    'windows': 'echo boo',
                    'supports_http_options': False
                },
                'baz': {
                    'description': 'echo blah',
                    'env_spec': 'default',
                    'supports_http_options': False
                },
                'foo': {
                    'description': 'say hi',
                    'default': True,
                    'env_spec': 'default',
                    'unix': 'echo hi',
                    'supports_http_options': True
                },
                'myapp': {
                    'description': 'Bokeh app main.py',
                    'bokeh_app': 'main.py',
                    'env_spec': 'woot',
                    'supports_http_options': True
                },
                'foo.ipynb': {
                    'description': 'Notebook foo.ipynb',
                    'notebook': 'foo.ipynb',
                    'env_spec': 'default',
                    'supports_http_options': True,
                    'registers_fusion_function': True
                }
            },
            'env_specs': {
                'default': {
                    'channels': ['bar'],
                    'packages': ['foo', 'notebook'],
                    'description': 'Default',
                    'locked': False,
                    'platforms': ['linux-64', 'osx-64', 'win-64'],
                    'downloads': {
                        'FOO': {
                            'encrypted': False,
                            'title': 'FOO',
                            'description': 'A downloaded file which is referenced by FOO.',
                            'url': 'https://example.com/blah'
                        }
                    },
                    'variables': {
                        'SOMETHING': {
                            'encrypted': False,
                            'title': 'SOMETHING',
                            'description': 'SOMETHING environment variable must be set.'
                        },
                        'SOMETHING_ELSE': {
                            'encrypted': False,
                            'title': 'SOMETHING_ELSE',
                            'description': 'SOMETHING_ELSE environment variable must be set.',
                            'default': "42"
                        }
                    },
                    'services': {
                        'REDIS_URL': {
                            'title': 'REDIS_URL',
                            'description': 'A running Redis server, located by a redis: URL set as REDIS_URL.',
                            'type': 'redis',
                            'encrypted': False
                        }
                    }
                },
                'lol': {
                    'channels': ['bar'],
                    'packages': ['foo'],
                    'description': 'lol',
                    'locked': False,
                    'platforms': ['linux-64', 'osx-64', 'win-64'],
                    'downloads': {
                        'FOO': {
                            'encrypted': False,
                            'title': 'FOO',
                            'description': 'A downloaded file which is referenced by FOO.',
                            'url': 'https://example.com/blah'
                        }
                    },
                    'variables': {
                        'SOMETHING': {
                            'encrypted': False,
                            'title': 'SOMETHING',
                            'description': 'SOMETHING environment variable must be set.'
                        },
                        'SOMETHING_ELSE': {
                            'encrypted': False,
                            'title': 'SOMETHING_ELSE',
                            'description': 'SOMETHING_ELSE environment variable must be set.',
                            'default': "42"
                        }
                    },
                    'services': {
                        'REDIS_URL': {
                            'title': 'REDIS_URL',
                            'description': 'A running Redis server, located by a redis: URL set as REDIS_URL.',
                            'type': 'redis',
                            'encrypted': False
                        }
                    }
                },
                'w00t': {
                    'channels': ['bar'],
                    'packages': ['foo', 'something'],
                    'description': 'double 0',
                    'locked': False,
                    'platforms': ['linux-64', 'osx-64', 'win-64'],
                    'downloads': {
                        'FOO': {
                            'encrypted': False,
                            'title': 'FOO',
                            'description': 'A downloaded file which is referenced by FOO.',
                            'url': 'https://example.com/blah'
                        }
                    },
                    'variables': {
                        'SOMETHING': {
                            'encrypted': False,
                            'title': 'SOMETHING',
                            'description': 'SOMETHING environment variable must be set.'
                        },
                        'SOMETHING_ELSE': {
                            'encrypted': False,
                            'title': 'SOMETHING_ELSE',
                            'description': 'SOMETHING_ELSE environment variable must be set.',
                            'default': "42"
                        }
                    },
                    'services': {
                        'REDIS_URL': {
                            'title': 'REDIS_URL',
                            'description': 'A running Redis server, located by a redis: URL set as REDIS_URL.',
                            'type': 'redis',
                            'encrypted': False
                        }
                    }
                },
                'woot': {
                    'channels': ['bar', 'woohoo'],
                    'packages': ['foo', 'blah', 'bokeh'],
                    'description': 'woot',
                    'locked': False,
                    'platforms': ['linux-64', 'osx-64', 'win-64'],
                    'downloads': {
                        'FOO': {
                            'encrypted': False,
                            'title': 'FOO',
                            'description': 'A downloaded file which is referenced by FOO.',
                            'url': 'https://example.com/blah'
                        }
                    },
                    'variables': {
                        'SOMETHING': {
                            'encrypted': False,
                            'title': 'SOMETHING',
                            'description': 'SOMETHING environment variable must be set.'
                        },
                        'SOMETHING_ELSE': {
                            'encrypted': False,
                            'title': 'SOMETHING_ELSE',
                            'description': 'SOMETHING_ELSE environment variable must be set.',
                            'default': "42"
                        }
                    },
                    'services': {
                        'REDIS_URL': {
                            'title': 'REDIS_URL',
                            'description': 'A running Redis server, located by a redis: URL set as REDIS_URL.',
                            'type': 'redis',
                            'encrypted': False
                        }
                    }
                }
            }
        }

        assert expected == project.publication_info()
        assert len(project.suggestions) == 0

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: _complicated_project_contents,
            "main.py": "",
            "foo.ipynb": ""
        }, check_publication_info_from_complex)


def test_find_requirements():
    def check_find_requirements(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        spec_name = project.default_env_spec_name

        reqs = project.find_requirements(spec_name, env_var='SOMETHING')
        assert len(reqs) == 1
        assert reqs[0].env_var == 'SOMETHING'

        reqs = project.find_requirements(spec_name, klass=CondaEnvRequirement)
        assert len(reqs) == 1
        assert isinstance(reqs[0], CondaEnvRequirement)

        reqs = project.find_requirements(spec_name, klass=ServiceRequirement)
        assert len(reqs) == 1
        assert isinstance(reqs[0], ServiceRequirement)

        reqs = project.find_requirements(spec_name, klass=DownloadRequirement)
        assert len(reqs) == 1
        assert isinstance(reqs[0], DownloadRequirement)

        # the klass and env_var kwargs must be "AND"-ed together
        reqs = project.find_requirements(spec_name, klass=CondaEnvRequirement, env_var='SOMETHING')
        assert [] == reqs

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: _complicated_project_contents,
            "main.py": "",
            "foo.ipynb": ""
        }, check_find_requirements)


def test_requirements_subsets():
    def check_requirements_subsets(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        services = project.service_requirements(project.default_env_spec_name)
        assert len(services) == 1
        assert isinstance(services[0], ServiceRequirement)
        assert services[0].env_var == 'REDIS_URL'

        downloads = project.download_requirements(project.default_env_spec_name)
        assert len(downloads) == 1
        assert isinstance(downloads[0], DownloadRequirement)
        assert downloads[0].env_var == 'FOO'

        everything = project.all_variable_requirements(project.default_env_spec_name)
        everything_names = [req.env_var for req in everything]
        # the first element is CONDA_PREFIX, CONDA_ENV_PATH, or CONDA_DEFAULT_ENV
        assert ['FOO', 'REDIS_URL', 'SOMETHING', 'SOMETHING_ELSE'] == sorted(everything_names)[1:]

        plain = project.plain_variable_requirements(project.default_env_spec_name)
        plain_names = [req.env_var for req in plain]
        assert ['SOMETHING', 'SOMETHING_ELSE'] == sorted(plain_names)

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: _complicated_project_contents,
            "main.py": "",
            "foo.ipynb": ""
        }, check_requirements_subsets)


def test_env_var_name_list_properties():
    def check_env_var_name_list_properties(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        services = project.services(project.default_env_spec_name)
        assert ['REDIS_URL'] == services

        downloads = project.downloads(project.default_env_spec_name)
        assert ['FOO'] == downloads

        everything = project.all_variables(project.default_env_spec_name)
        # the first element is CONDA_PREFIX, CONDA_ENV_PATH, or CONDA_DEFAULT_ENV
        assert ['FOO', 'REDIS_URL', 'SOMETHING', 'SOMETHING_ELSE'] == sorted(everything)[1:]

        plain = project.plain_variables(project.default_env_spec_name)
        assert ['SOMETHING', 'SOMETHING_ELSE'] == sorted(plain)

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: _complicated_project_contents,
            "main.py": "",
            "foo.ipynb": ""
        }, check_env_var_name_list_properties)


def test_project_problem():
    unfixable = ProjectProblem(text="foo")
    assert unfixable.text == "foo"
    assert not unfixable.can_fix
    assert unfixable.fix(None) is None

    def fixit(project):
        return 42

    fixable = ProjectProblem(text="bar", fix_prompt="prompt", fix_function=fixit)
    assert fixable.text == "bar"
    assert fixable.can_fix
    assert fixable.fix(None) == 42


def test_auto_fix_missing_name():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert len(project.problems) == 1
        assert len(project.problem_objects) == 1
        problem = project.problem_objects[0]
        assert problem.text == ("%s: The 'name:' field is missing." % DEFAULT_PROJECT_FILENAME)
        assert problem.can_fix

        problem.fix(project)
        project.project_file.save()

        assert project.problems == []
        assert project.name == os.path.basename(dirname)
        assert 'name' in project.project_file.root

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: "env_specs:\n  default: {}\nplatforms: [linux-32,linux-64,osx-64,win-32,win-64]\n"},
        check)


def test_auto_fix_env_spec_import():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert len(project.problems) == 1
        assert len(project.problem_objects) == 1
        assert len(project.fixable_problems) == 1
        problem = project.problem_objects[0]
        assert problem.text == "Environment spec 'stuff' from environment.yml is not in anaconda-project.yml."
        assert problem.can_fix

        problem.fix(project)
        project.project_file.save()

        assert project.problems == []
        assert list(project.env_specs.keys()) == ['stuff']
        spec = project.env_specs['stuff']
        assert spec.conda_packages == ('a', 'b')
        assert spec.pip_packages == ('foo', )
        assert spec.channels == ('bar', )

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME: "name: foo\nenv_specs: {}\nplatforms: [linux-32,linux-64,osx-64,win-32,win-64]\n",
            "environment.yml": """
name: stuff
dependencies:
 - a
 - b
 - pip:
   - foo
channels:
 - bar
"""
        }, check)


def test_auto_fix_requirements_txt_import():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert len(project.problems) == 1
        assert len(project.problem_objects) == 1
        assert len(project.fixable_problems) == 1
        problem = project.problem_objects[0]
        assert problem.text == "Environment spec 'default' from requirements.txt is not in anaconda-project.yml."
        assert problem.can_fix

        problem.fix(project)
        project.project_file.save()

        assert project.problems == []
        assert list(project.env_specs.keys()) == ['default']
        spec = project.env_specs['default']
        assert spec.conda_packages == ()
        assert spec.pip_packages == ('abc', 'efg')
        assert spec.channels == ()

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME: "name: foo\nenv_specs: {}\nplatforms: [linux-32,linux-64,osx-64,win-32,win-64]\n",
            "requirements.txt": """
# these are some pip packages.
abc
efg
"""
        }, check)


def test_auto_fix_env_spec_out_of_sync():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert len(project.problems) == 1
        assert len(project.problem_objects) == 1
        assert len(project.fixable_problems) == 1
        problem = project.problem_objects[0]
        assert ("Environment spec 'stuff' from environment.yml is out of sync with anaconda-project.yml. Diff:\n" +
                "  channels:\n    + bar\n+ a\n+ b\n  pip:\n    + foo") == problem.text
        assert problem.can_fix

        problem.fix(project)
        project.project_file.save()

        assert project.problems == []
        assert list(project.env_specs.keys()) == ['stuff']
        spec = project.env_specs['stuff']
        assert spec.conda_packages == ('a', 'b')
        assert spec.pip_packages == ('foo', )
        assert spec.channels == ('bar', )

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME: "name: foo\nenv_specs: { 'stuff': { 'packages':[] } }"
            "\nplatforms: [linux-32,linux-64,osx-64,win-32,win-64]\n",
            "environment.yml": """
name: stuff
dependencies:
 - a
 - b
 - pip:
   - foo
channels:
 - bar
"""
        }, check)


def test_auto_fix_env_spec_import_saying_no():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert len(project.problems) == 1
        assert len(project.problem_objects) == 1
        assert len(project.fixable_problems) == 1
        problem = project.problem_objects[0]
        assert problem.text == "Environment spec 'stuff' from environment.yml is not in anaconda-project.yml."
        assert problem.can_fix

        problem.no_fix(project)
        project.project_file.save()

        assert project.problems == []
        assert list(project.env_specs.keys()) == ['default']

        skip_importing_hash = project.project_file.get_value(['skip_imports', 'environment'])
        assert skip_importing_hash is not None
        assert skip_importing_hash != ''

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME:
            "name: foo\nenv_specs: {'default':{'packages':[]}}\nplatforms: [linux-32,linux-64,osx-64,win-32,win-64]\n",
            "environment.yml": """
name: stuff
dependencies:
 - a
 - b
 - pip:
   - foo
channels:
 - bar
"""
        }, check)


def test_no_auto_fix_env_spec_with_notebook_bokeh_injection():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert len(project.problems) == 1
        assert len(project.problem_objects) == 1
        assert len(project.fixable_problems) == 1
        problem = project.problem_objects[0]
        assert ("Environment spec 'stuff' from environment.yml is out of sync with anaconda-project.yml. Diff:\n" +
                "  channels:\n    + bar\n+ a\n+ b\n  pip:\n    + foo") == problem.text
        assert problem.can_fix

        problem.fix(project)
        project.project_file.save()

        assert project.problems == []
        assert list(project.env_specs.keys()) == ['stuff']
        spec = project.env_specs['stuff']
        assert spec.conda_packages == ('a', 'b')
        assert spec.pip_packages == ('foo', )
        assert spec.channels == ('bar', )

        # add bokeh and notebook, which we should ignore
        packages = project.project_file.get_value(['env_specs', 'stuff', 'packages'])
        packages.extend(['bokeh', 'notebook'])
        project.project_file.set_value(['env_specs', 'stuff', 'packages'], packages)
        project.project_file.save()

        # no problems despite the diff
        assert project.problems == []
        spec = project.env_specs['stuff']
        assert spec.conda_packages == ('a', 'b', 'bokeh', 'notebook')

        # add some other package, should NOT ignore
        packages = project.project_file.get_value(['env_specs', 'stuff', 'packages'])
        packages.extend(['someother'])
        project.project_file.set_value(['env_specs', 'stuff', 'packages'], packages)
        project.project_file.save()

        assert len(project.problems) == 1

        # remove that again
        packages = project.project_file.get_value(['env_specs', 'stuff', 'packages'])
        packages.remove('someother')
        project.project_file.set_value(['env_specs', 'stuff', 'packages'], packages)
        project.project_file.save()

        assert len(project.problems) == 0

        # add a channel, should NOT ignore
        channels = project.project_file.get_value(['env_specs', 'stuff', 'channels'])
        channels.append("boo")
        project.project_file.set_value(['env_specs', 'stuff', 'channels'], channels)
        project.project_file.save()

        assert len(project.problems) == 1
        spec = project.env_specs['stuff']
        assert spec.channels == ('bar', 'boo')

        # remove the channel
        channels = project.project_file.get_value(['env_specs', 'stuff', 'channels'])
        channels.remove("boo")
        project.project_file.set_value(['env_specs', 'stuff', 'channels'], channels)
        project.project_file.save()

        assert len(project.problems) == 0

        # add a pip package, should NOT ignore
        packages = project.project_file.get_value(['env_specs', 'stuff', 'packages'])
        pip_list = None
        for p in packages:
            if isinstance(p, dict):
                pip_list = p['pip']
        pip_list.append('someother')
        project.project_file.use_changes_without_saving()
        project.project_file.save()

        assert len(project.problems) == 1
        spec = project.env_specs['stuff']
        assert spec.pip_packages == ('foo', 'someother')

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME: "name: foo\nenv_specs: { 'stuff': { 'packages':[] } }"
            "\nplatforms: [linux-32,linux-64,osx-64,win-32,win-64]\n",
            "environment.yml": """
name: stuff
dependencies:
 - a
 - b
 - pip:
   - foo
channels:
 - bar
"""
        }, check)


def test_auto_fix_notebook_dep():
    def check(dirname):
        project = project_no_dedicated_env(dirname)

        assert len(project.problems) == 0
        assert len(project.problem_objects) == 0
        assert len(project.fixable_problems) == 0
        assert len(project.suggestions) == 1
        assert len(project.suggestion_objects) == 1
        assert len(project.env_specs['default'].conda_package_names_set) == 0

        problem = project.suggestion_objects[0]
        assert ("%s: Command foo.ipynb uses env spec default which does not have the packages: notebook" %
                project.project_file.basename) == problem.text
        assert problem.can_fix

        problem.fix(project)
        project.project_file.save()

        assert project.problems == []
        assert project.suggestions == []
        assert project.env_specs['default'].conda_package_names_set == set(['notebook'])

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                       '  foo.ipynb:\n'
                                       '    notebook: foo.ipynb\n'),
            'foo.ipynb': 'not a real notebook'
        }, check)


def test_no_auto_fix_notebook_dep_if_we_have_anaconda():
    def check(dirname):
        project = project_no_dedicated_env(dirname)

        assert project.problems == []
        assert project.suggestions == []
        assert project.env_specs['default'].conda_package_names_set == set(['anaconda'])

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: ('packages:\n'
                                       ' - anaconda\n'
                                       'commands:\n'
                                       '  foo.ipynb:\n'
                                       '    notebook: foo.ipynb\n'),
            'foo.ipynb':
            'not a real notebook'
        }, check)


def test_no_auto_fix_notebook_dep_if_we_have_notebook():
    def check(dirname):
        project = project_no_dedicated_env(dirname)

        assert project.problems == []
        assert project.env_specs['default'].conda_package_names_set == set(['notebook'])

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: ('packages:\n'
                                       ' - notebook\n'
                                       'commands:\n'
                                       '  foo.ipynb:\n'
                                       '    notebook: foo.ipynb\n'),
            'foo.ipynb':
            'not a real notebook'
        }, check)


def test_auto_fix_bokeh_dep():
    def check(dirname):
        project = project_no_dedicated_env(dirname)

        assert len(project.problems) == 0
        assert len(project.problem_objects) == 0
        assert len(project.fixable_problems) == 0
        assert len(project.suggestions) == 1
        assert len(project.suggestion_objects) == 1
        assert len(project.env_specs['default'].conda_package_names_set) == 0

        problem = project.suggestion_objects[0]
        assert ("%s: Command bokeh_test uses env spec default which does not have the packages: bokeh" %
                project.project_file.basename) == problem.text
        assert problem.can_fix

        problem.fix(project)
        project.project_file.save()

        assert project.problems == []
        assert project.env_specs['default'].conda_package_names_set == set(['bokeh'])

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                       '  bokeh_test:\n'
                                       '    bokeh_app: main.py\n'),
            'main.py': 'hello'
        }, check)


def test_unknown_field_in_root():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        expected_suggestion = ("%s: Unknown field name 'somejunk'" % project.project_file.basename)
        assert [expected_suggestion] == project.suggestions

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "somejunk: False\n"}, check)


def test_unknown_field_in_command():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        expected_suggestion = ("%s: Unknown field name 'somejunk'" % project.project_file.basename)
        assert [expected_suggestion] == project.suggestions

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "commands:\n  foo:\n    unix: something\n    somejunk: True\n"}, check)


def test_unknown_field_in_env_spec():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        expected_suggestion = ("%s: Unknown field name 'somejunk'" % project.project_file.basename)
        assert [expected_suggestion] == project.suggestions

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "env_specs:\n  foo:\n    packages: [something]\n    somejunk: True\n"}, check)


def test_unknown_field_in_env_spec_allowed():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        assert [] == project.suggestions

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            "env_specs:\n  foo:\n    packages: [something]\n    somejunk: True\n    user_fields: [somejunk]\n"
        }, check)


def test_unknown_field_in_root_of_lock_file():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        expected_suggestion = ("%s: Unknown field name 'somejunk'" % project.lock_file.basename)
        assert [expected_suggestion] == project.suggestions

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: false\nsomejunk: False\n"}, check)


def test_unknown_field_in_lock_set_of_lock_file():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        expected_suggestion = ("%s: Unknown field name 'somejunk'" % project.lock_file.basename)
        assert [expected_suggestion] == project.suggestions

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_LOCK_FILENAME:
            """
env_specs:
  default:
     platforms: [linux-64,osx-64,win-64]
     somejunk: True
    """
        }, check)


def test_empty_file_has_problems():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert ["anaconda-project.yml: The 'name:' field is missing."] == project.problems

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ""}, check)


def test_with_one_locked_env_spec_has_problems():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [
            "anaconda-project.yml: The 'name:' field is missing.",
            "anaconda-project.yml: The 'platforms:' field should list platforms the project supports."
        ] == project.problems

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME: """
env_specs:
  foo:
     packages: []
""",
            DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"
        }, check)


def test_with_locking_enabled_no_env_specs_has_problems():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [
            "anaconda-project.yml: The 'name:' field is missing.",
            "anaconda-project.yml: The 'platforms:' field should list platforms the project supports."
        ] == project.problems

    with_directory_contents({
        DEFAULT_PROJECT_FILENAME: "",
        DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"
    }, check)


def test_with_locking_disabled_no_platforms_required():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME: "name: foo\nenv_specs:\n  default:\n    packages: []\n",
            DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: false\n"
        }, check)


def test_load_weird_platform():
    def check(dirname):
        project = project_no_dedicated_env(dirname)

        assert [
            "anaconda-project.yml: Unusual platform name 'weird-valid' may be a typo "
            "(more usual examples: linux-64, osx-64, win-64)"
        ] == project.suggestions
        assert [
            "anaconda-project.yml: Platform name 'weirdinvalid' is invalid "
            "(valid examples: linux-64, osx-64, win-64)"
        ] == project.problems

        spec = project.env_specs['default']
        assert spec.platforms == ('linux-64', 'weird-valid')

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME:
            """
name: foo
platforms: [linux-64, weird-valid, weirdinvalid]
env_specs:
  default:
    packages: [foo]
"""
        }, check)


def test_only_some_env_specs_have_platforms_locking_disabled():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME:
            """
name: foo

env_specs:
  default:
    platforms: [linux-64]
    packages: [foo]
  no_platforms:
    packages: [bar]
"""
        }, check)


def test_only_some_env_specs_have_platforms_locking_enabled():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [("anaconda-project.yml: Env spec no_platforms does not have anything in its " + "'platforms:' field.")
                ] == project.problems

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME: """
name: foo

env_specs:
  default:
    platforms: [linux-64]
    packages: [foo]
  no_platforms:
    packages: [bar]
        """,
            DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"
        }, check)


def test_empty_lock_file_enables_locking():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.locking_globally_enabled

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_LOCK_FILENAME: """
"""}, check)


def test_default_lock_file_disables_locking():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert not project.locking_globally_enabled

    with_directory_contents_completing_project_file(dict(), check)


def test_lock_file_non_bool_locking_enabled():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        expected_error = "%s: Value for locking_enabled should be true or false, found %r" % (
            project.lock_file.basename, 42)
        assert [expected_error] == project.problems

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled:  42\n"}, check)


def test_lock_file_non_dict_env_specs():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        expected_error = ("%s: 'env_specs:' section in lock file should be a dictionary " +
                          "from env spec names to lock information, found %r") % (project.lock_file.basename, 42)
        assert [expected_error] == project.problems

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_LOCK_FILENAME: "env_specs:  42\n"}, check)


def test_lock_file_non_dict_lock_set():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        expected_error = ("%s: Field 'default' in env_specs in lock file should be a dictionary, " +
                          "found %r") % (project.lock_file.basename, 42)
        assert [expected_error] == project.problems

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_LOCK_FILENAME: """
env_specs:
  default: 42
"""}, check)


def test_lock_file_non_bool_lock_set_locked():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        expected_error = ("%s: Value for locked for env spec 'default' should be true or false, " +
                          "found %r") % (project.lock_file.basename, 42)
        assert [expected_error] == project.problems

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_LOCK_FILENAME: """
env_specs:
  default:
    locked: 42
"""}, check)


def test_lock_file_non_string_lock_set_hash():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        expected_error = ("%s: Value for env_spec_hash for env spec 'default' should be a string, " +
                          "found %r") % (project.lock_file.basename, 42)
        assert [expected_error] == project.problems

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_LOCK_FILENAME: """
env_specs:
  default:
    env_spec_hash: 42
"""}, check)


def test_lock_file_non_dict_lock_set_packages():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        expected_error = ("%s: 'packages:' section in env spec 'default' in lock file should be a dictionary, " +
                          "found %r") % (project.lock_file.basename, 42)
        assert [expected_error] == project.problems

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_LOCK_FILENAME: """
env_specs:
  default:
    packages: 42
"""}, check)


def test_lock_file_has_pip_packages():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        expected_warning = ("%s: env spec 'default': pip dependencies are currently ignored in the lock file") % (
            project.lock_file.basename, )
        assert [expected_warning] == project.suggestions

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_LOCK_FILENAME:
            """
env_specs:
  default:
    platforms: [linux-64,osx-64,win-64]
    packages:
      all:
        - pip:
          - foobar
"""
        }, check)


def test_lock_file_has_invalid_packages():
    def check(dirname):
        project = project_no_dedicated_env(dirname)

        filename = project.lock_file.basename
        assert [
            "%s: invalid package specification: =" % filename,
            "%s: invalid package specification: foo bar" % filename,
            "%s: invalid pip package specifier: %%" % filename
        ] == project.problems

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_LOCK_FILENAME:
            """
env_specs:
  default:
    packages:
      all:
        - "="
        - foo bar
        - pip:
          - "%"
"""
        }, check)


def test_lock_file_has_wrong_platforms():
    def check(dirname):
        project = project_no_dedicated_env(dirname)

        assert [] == project.problems
        assert [
            "anaconda-project-lock.yml: Env spec 'default' specifies platforms "
            "'linux-64,osx-64,win-64' but the lock file has locked "
            "versions for platforms 'win-64'"
        ] == project.suggestions

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_LOCK_FILENAME:
            """
env_specs:
  default:
    platforms: ["win-64"]
    packages:
      all: [foo]
"""
        }, check)


def test_lock_file_has_zero_platforms():
    def check(dirname):
        project = project_no_dedicated_env(dirname)

        assert [] == project.problems
        assert [
            "anaconda-project-lock.yml: Env spec 'default' specifies platforms "
            "'linux-64,osx-64,win-64' but the lock file lists no platforms for it"
        ] == project.suggestions

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_LOCK_FILENAME: """
env_specs:
  default:
    platforms: []
    packages:
      all: [foo]
"""}, check)


def test_lock_file_has_wrong_hash():
    def check(dirname):
        project = project_no_dedicated_env(dirname)

        assert [] == project.problems
        assert [
            "anaconda-project-lock.yml: Env spec 'default' has changed since the lock "
            'file was last updated (env spec hash has changed from wrong to '
            'a30f02c961ef4f3fe07ceb09e0906394c3885a79)'
        ] == project.suggestions

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_LOCK_FILENAME:
            """
env_specs:
  default:
    env_spec_hash: wrong
    platforms: [linux-64,osx-64,win-64]
    packages:
      all: [foo]
"""
        }, check)


def test_lock_file_has_empty_and_wrong_package_lists():
    def check(dirname):
        project = project_no_dedicated_env(dirname)

        assert [] == project.problems
        # yapf: disable
        assert [
            'anaconda-project-lock.yml: Lock file lists no packages for env spec '
            "'default' on platform linux-64",
            'anaconda-project-lock.yml: Lock file is missing 1 packages for env spec '
            'default on osx-64 (hello)',
            'anaconda-project-lock.yml: Lock file lists no packages for env spec '
            "'default' on platform win-64"
        ] == project.suggestions
        # yapf: enable

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
env_specs:
   default:
      packages:
         - hello
""",
            DEFAULT_PROJECT_LOCK_FILENAME:
            """
env_specs:
  default:
    platforms: [linux-64,osx-64,win-64]
    packages:
      linux-64: []
      win-64: []
      win-32: [foo]
      osx-64: [bar]
      linux-32: [baz]
"""
        }, check)


def test_lock_file_has_orphan_env_spec():
    def check(dirname):
        project = project_no_dedicated_env(dirname)

        assert [] == project.problems
        assert ["anaconda-project-lock.yml: Lock file lists env spec 'orphan' which is not in anaconda-project.yml"
                ] == project.suggestions

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
env_specs:
   default:
      packages:
         - hello
""",
            DEFAULT_PROJECT_LOCK_FILENAME:
            """
env_specs:
  default:
    platforms: [linux-64,osx-64,win-64]
    packages:
      all: [hello]
  orphan:
    platforms: [linux-64,osx-64,win-64]
    packages: {}
"""
        }, check)


def test_fix_project_file_with_no_platforms():
    def check(dirname):
        project = project_no_dedicated_env(dirname)

        assert ["anaconda-project.yml: The 'platforms:' field should list platforms the project supports."
                ] == project.problems

        assert () == project.env_specs['default'].platforms

        project.fix_problems_and_suggestions()

        assert [] == project.problems

        assert conda_api.default_platforms_with_current() == project.env_specs['default'].platforms

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME: """
name: foo
env_specs:
   default:
      packages:
         - hello
""",
            DEFAULT_PROJECT_LOCK_FILENAME: """
locking_enabled: true
"""
        }, check)


def test_fix_env_spec_with_no_platforms():
    def check(dirname):
        project = project_no_dedicated_env(dirname)

        assert [
            "anaconda-project.yml: Env spec bar does not have anything in its 'platforms:' field.",
            "anaconda-project.yml: Env spec foo does not have anything in its 'platforms:' field."
        ] == project.problems

        assert ('linux-64', ) == project.env_specs['default'].platforms
        assert () == project.env_specs['foo'].platforms
        assert () == project.env_specs['bar'].platforms

        project.fix_problems_and_suggestions()

        assert [] == project.problems

        assert ('linux-64', ) == project.env_specs['default'].platforms
        assert conda_api.default_platforms_with_current() == project.env_specs['foo'].platforms
        assert conda_api.default_platforms_with_current() == project.env_specs['bar'].platforms

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME: """
name: foo
env_specs:
   default:
      platforms: ['linux-64']
      packages:
         - hello
   foo:
      platforms: []
      packages:
         - apackage
   bar:
      platforms: []
      packages:
         - package2
""",
            DEFAULT_PROJECT_LOCK_FILENAME: """
locking_enabled: true
"""
        }, check)
