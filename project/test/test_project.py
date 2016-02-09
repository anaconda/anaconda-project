from __future__ import absolute_import, print_function

from copy import deepcopy
import os
import stat
import subprocess

import pytest

from project.internal.test.tmpfile_utils import with_directory_contents
from project.plugins.requirement import RequirementRegistry, EnvVarRequirement
from project.project import Project
from project.project_file import PROJECT_FILENAME
from project.conda_meta_file import META_DIRECTORY, META_FILENAME


def test_properties():
    def check_properties(dirname):
        project = Project(dirname)
        assert dirname == project.directory_path
        assert dirname == os.path.dirname(project.project_file.filename)
        assert dirname == os.path.dirname(os.path.dirname(project.conda_meta_file.filename))
        assert project.name == os.path.basename(dirname)
        assert project.version == "unknown"
        assert project.problems == []

    with_directory_contents(dict(), check_properties)


def test_ignore_trailing_slash_on_dirname():
    def check_properties(dirname):
        project = Project(dirname + "/")
        assert dirname == project.directory_path
        assert dirname == os.path.dirname(project.project_file.filename)
        assert dirname == os.path.dirname(os.path.dirname(project.conda_meta_file.filename))
        assert project.name == os.path.basename(dirname)
        assert project.version == "unknown"
        assert project.problems == []

    with_directory_contents(dict(), check_properties)


def test_single_env_var_requirement():
    def check_some_env_var(dirname):
        project = Project(dirname)
        assert 1 == len(project.requirements)
        assert "FOO" == project.requirements[0].env_var
        assert [] == project.problems

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  FOO: {}
"""}, check_some_env_var)


def test_problem_in_project_file():
    def check_problem(dirname):
        project = Project(dirname)
        assert 0 == len(project.requirements)
        assert 1 == len(project.problems)

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  42
"""}, check_problem)


def test_single_env_var_requirement_with_options():
    def check_some_env_var(dirname):
        project = Project(dirname)
        assert 1 == len(project.requirements)
        assert "FOO" == project.requirements[0].env_var
        assert dict(default="hello") == project.requirements[0].options

    with_directory_contents({PROJECT_FILENAME: """
runtime:
    FOO: { default: "hello" }
"""}, check_some_env_var)


def test_override_requirement_registry():
    def check_override_requirement_registry(dirname):
        requirement_registry = RequirementRegistry()
        project = Project(dirname, requirement_registry)
        assert project._config_cache.requirement_registry is requirement_registry

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  FOO: {}
"""}, check_override_requirement_registry)


def test_get_name_and_version_from_conda_meta_yaml():
    def check_conda_meta(dirname):
        project = Project(dirname)
        assert project.name == "foo"
        assert project.version == "1.2.3"

    with_directory_contents(
        {
            META_DIRECTORY + "/" + META_FILENAME: """
package:
  name: foo
  version: 1.2.3
"""
        }, check_conda_meta)


def test_get_name_and_version_from_project_file():
    def check_name_and_version(dirname):
        project = Project(dirname)
        assert project.name == "foo"
        assert project.version == "1.2.3"

        assert project.conda_meta_file.name == "from_meta"
        assert project.conda_meta_file.version == "1.2.3meta"

    with_directory_contents(
        {PROJECT_FILENAME: """
package:
  name: foo
  version: 1.2.3
    """,
         META_DIRECTORY + "/" + META_FILENAME: """
package:
  name: from_meta
  version: 1.2.3meta
"""}, check_name_and_version)


def test_set_name_and_version_in_project_file():
    def check_name_and_version(dirname):
        project = Project(dirname)
        assert project.name == "foo"
        assert project.version == "1.2.3"

        project.project_file.name = "bar"
        project.project_file.version = "4.5.6"
        assert project.name == "bar"
        assert project.version == "4.5.6"
        project.project_file.save()

        project2 = Project(dirname)
        assert project2.name == "bar"
        assert project2.version == "4.5.6"

    with_directory_contents(
        {PROJECT_FILENAME: """
package:
  name: foo
  version: 1.2.3
    """}, check_name_and_version)


def test_get_package_requirements_from_project_and_meta_files():
    def check_get_packages(dirname):
        project = Project(dirname)
        # note that the current algorithm is that we do not
        # de-duplicate; testing that specifically so we'll
        # notice if it changes.
        assert ["foo", "bar", "foo", "hello >= 1.0", "world"] == project.requirements_run

        # find CondaEnvRequirement
        conda_env_req = None
        for r in project.requirements:
            if hasattr(r, 'conda_package_specs'):
                assert conda_env_req is None  # only one
                conda_env_req = r
        assert ["foo", "bar", "foo", "hello >= 1.0", "world"] == conda_env_req.conda_package_specs

    with_directory_contents(
        {PROJECT_FILENAME: """
requirements:
  run:
    - foo
    - hello >= 1.0
    - world
    """,
         META_DIRECTORY + "/" + META_FILENAME: """
requirements:
  run:
    - foo
    - bar
"""}, check_get_packages)


def test_use_env_options_when_packages_also_specified():
    def check_use_env_options(dirname):
        project = Project(dirname)
        assert ["foo"] == project.requirements_run

        # find CondaEnvRequirement
        conda_env_req = None
        for r in project.requirements:
            if hasattr(r, 'conda_package_specs'):
                assert conda_env_req is None  # only one
                conda_env_req = r
        assert ["foo"] == conda_env_req.conda_package_specs
        assert dict(project_scoped=False) == conda_env_req.options

    with_directory_contents(
        {PROJECT_FILENAME: """
runtime:
  CONDA_DEFAULT_ENV : { project_scoped: false }

requirements:
  run:
    - foo
"""}, check_use_env_options)


def test_get_package_requirements_from_empty_project_and_meta_files():
    def check_get_packages(dirname):
        project = Project(dirname)
        assert [] == project.requirements_run

    with_directory_contents({PROJECT_FILENAME: "", META_DIRECTORY + "/" + META_FILENAME: ""}, check_get_packages)


def test_complain_about_broken_package_requirements():
    def check_get_packages(dirname):
        project = Project(dirname)
        assert 2 == len(project.problems)
        "should be a list of strings not 'CommentedMap" in project.problems[0]
        "should be a string not '42'" in project.problems[1]

    with_directory_contents(
        {PROJECT_FILENAME: """
requirements:
  run:
    foo: bar
    """,
         META_DIRECTORY + "/" + META_FILENAME: """
requirements:
  run:
    - 42
    - bar
"""}, check_get_packages)


def test_load_list_of_runtime_requirements():
    def check_file(dirname):
        filename = os.path.join(dirname, PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = Project(dirname)
        assert [] == project.problems
        requirements = project.requirements
        assert 2 == len(requirements)
        assert isinstance(requirements[0], EnvVarRequirement)
        assert 'FOO' == requirements[0].env_var
        assert isinstance(requirements[1], EnvVarRequirement)
        assert 'BAR' == requirements[1].env_var
        assert len(project.problems) == 0

    with_directory_contents({PROJECT_FILENAME: "runtime:\n  - FOO\n  - BAR\n"}, check_file)


def test_load_dict_of_runtime_requirements():
    def check_file(dirname):
        filename = os.path.join(dirname, PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = Project(dirname)
        assert [] == project.problems
        requirements = project.requirements
        assert 2 == len(requirements)
        assert isinstance(requirements[0], EnvVarRequirement)
        assert 'FOO' == requirements[0].env_var
        assert dict(a=1) == requirements[0].options
        assert isinstance(requirements[1], EnvVarRequirement)
        assert 'BAR' == requirements[1].env_var
        assert dict(b=2) == requirements[1].options
        assert len(project.problems) == 0

    with_directory_contents({PROJECT_FILENAME: "runtime:\n  FOO: { a: 1 }\n  BAR: { b: 2 }\n"}, check_file)


def test_non_string_runtime_requirements():
    def check_file(dirname):
        filename = os.path.join(dirname, PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = Project(dirname)
        assert 2 == len(project.problems)
        assert 0 == len(project.requirements)
        assert "42 is not a string" in project.problems[0]
        assert "43 is not a string" in project.problems[1]

    with_directory_contents({PROJECT_FILENAME: "runtime:\n  - 42\n  - 43\n"}, check_file)


def test_bad_runtime_requirements_options():
    def check_file(dirname):
        filename = os.path.join(dirname, PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = Project(dirname)
        assert 2 == len(project.problems)
        assert 0 == len(project.requirements)
        assert "key FOO with value 42; the value must be a dict" in project.problems[0]
        assert "key BAR with value baz; the value must be a dict" in project.problems[1]

    with_directory_contents({PROJECT_FILENAME: "runtime:\n  FOO: 42\n  BAR: baz\n"}, check_file)


def test_runtime_requirements_not_a_collection():
    def check_file(dirname):
        filename = os.path.join(dirname, PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = Project(dirname)
        assert 1 == len(project.problems)
        assert 0 == len(project.requirements)
        assert "runtime section contains wrong value type 42" in project.problems[0]

    with_directory_contents({PROJECT_FILENAME: "runtime:\n  42\n"}, check_file)


def test_corrupted_project_file_and_meta_file():
    def check_problem(dirname):
        project = Project(dirname)
        assert 0 == len(project.requirements)
        assert 2 == len(project.problems)
        assert 'project.yml has a syntax error that needs to be fixed by hand' in project.problems[0]
        assert 'meta.yaml has a syntax error that needs to be fixed by hand' in project.problems[1]

    with_directory_contents(
        {PROJECT_FILENAME: """
^
runtime:
  FOO
""",
         META_DIRECTORY + "/" + META_FILENAME: """
^
package:
  name: foo
  version: 1.2.3
"""}, check_problem)


def test_non_string_in_app_entry():
    def check_app_entry(dirname):
        project = Project(dirname)
        assert 1 == len(project.problems)
        assert "should be a string not '42'" in project.problems[0]

    with_directory_contents({PROJECT_FILENAME: "app:\n entry: 42\n"}, check_app_entry)


def test_launch_argv_from_project_file():
    def check_launch_argv(dirname):
        project = Project(dirname)
        assert project.launch_argv == ('foo', 'bar', '${PREFIX}')

    with_directory_contents({PROJECT_FILENAME: """
app:
  entry: foo bar ${PREFIX}
"""}, check_launch_argv)


def test_launch_argv_from_meta_file():
    def check_launch_argv(dirname):
        project = Project(dirname)
        assert project.launch_argv == ('foo', 'bar', '${PREFIX}')

    with_directory_contents(
        {META_DIRECTORY + "/" + META_FILENAME: """
app:
  entry: foo bar ${PREFIX}
"""}, check_launch_argv)


def _launch_argv_for_environment(environ, expected_output):
    def check_echo_output(dirname):
        if 'CONDA_DEFAULT_ENV' not in environ:
            environ['CONDA_DEFAULT_ENV'] = 'root'
        if 'PROJECT_DIR' not in environ:
            environ['PROJECT_DIR'] = dirname
        if 'PATH' not in environ:
            environ['PATH'] = os.environ['PATH']
        os.chmod(os.path.join(dirname, "echo.py"), stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        project = Project(dirname)
        argv = project.launch_argv_for_environment(environ)
        output = subprocess.check_output(argv).decode()
        assert output == expected_output.format(dirname=dirname)

    with_directory_contents(
        {
            PROJECT_FILENAME: """
app:
  entry: echo.py ${PREFIX}/blah foo bar
""",
            "echo.py": """#!/usr/bin/env python
from __future__ import print_function
import sys
print(repr(sys.argv))
"""
        }, check_echo_output)


def test_launch_command_in_project_dir():
    import project.internal.conda_api as conda_api
    prefix = conda_api.resolve_env_to_prefix('root')
    _launch_argv_for_environment(dict(), "['{dirname}/echo.py', '%s/blah', 'foo', 'bar']\n" % prefix)


def test_launch_command_in_project_dir_with_conda_env():
    _launch_argv_for_environment(
        dict(CONDA_DEFAULT_ENV='/someplace'),
        "['{dirname}/echo.py', '/someplace/blah', 'foo', 'bar']\n")


def test_launch_command_is_on_system_path():
    def check_python_version_output(dirname):
        environ = dict(CONDA_DEFAULT_ENV='root', PATH=os.environ['PATH'], PROJECT_DIR=dirname)
        project = Project(dirname)
        argv = project.launch_argv_for_environment(environ)
        output = subprocess.check_output(argv, stderr=subprocess.STDOUT).decode()
        assert output.startswith("Python")

    with_directory_contents({PROJECT_FILENAME: """
app:
  entry: python --version
"""}, check_python_version_output)


def test_launch_command_stuff_missing_from_environment():
    def check_launch_with_stuff_missing(dirname):
        project = Project(dirname)
        environ = dict(CONDA_DEFAULT_ENV='root', PATH=os.environ['PATH'], PROJECT_DIR=dirname)
        for key in environ:
            environ_copy = deepcopy(environ)
            del environ_copy[key]
            with pytest.raises(ValueError) as excinfo:
                project.launch_argv_for_environment(environ_copy)
            assert ('%s must be set' % key) in repr(excinfo.value)

    with_directory_contents({PROJECT_FILENAME: """
app:
  entry: foo
"""}, check_launch_with_stuff_missing)
