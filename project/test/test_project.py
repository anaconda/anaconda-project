from __future__ import absolute_import, print_function

import os

from project.internal.test.tmpfile_utils import with_directory_contents
from project.plugins.requirement import RequirementRegistry
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

    with_directory_contents(dict(), check_properties)


def test_ignore_trailing_slash_on_dirname():
    def check_properties(dirname):
        project = Project(dirname + "/")
        assert dirname == project.directory_path
        assert dirname == os.path.dirname(project.project_file.filename)
        assert dirname == os.path.dirname(os.path.dirname(project.conda_meta_file.filename))
        assert project.name == os.path.basename(dirname)
        assert project.version == "unknown"

    with_directory_contents(dict(), check_properties)


def test_single_env_var_requirement():
    def check_some_env_var(dirname):
        project = Project(dirname)
        assert 1 == len(project.requirements)
        assert "FOO" == project.requirements[0].env_var

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
        assert project.project_file.requirement_registry is requirement_registry

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
