from __future__ import absolute_import, print_function

import os

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
        assert ["foo", "hello >= 1.0", "world", "foo", "bar"] == project.requirements_run

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
