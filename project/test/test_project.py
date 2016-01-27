from project.internal.test.tmpfile_utils import with_directory_contents
from project.internal.project_file import PROJECT_FILENAME
from project.plugins.requirement import RequirementRegistry
from project.project import Project


def test_single_env_var_requirement():
    def check_some_env_var(dirname):
        requirement_registry = RequirementRegistry()
        project = Project(dirname, requirement_registry)
        assert 1 == len(project.requirements)
        assert "FOO" == project.requirements[0].env_var

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  FOO: {}
"""}, check_some_env_var)


def test_problem_in_project_file():
    def check_problem(dirname):
        requirement_registry = RequirementRegistry()
        project = Project(dirname, requirement_registry)
        assert 0 == len(project.requirements)
        assert 1 == len(project.problems)

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  42
"""}, check_problem)


def test_single_env_var_requirement_with_options():
    def check_some_env_var(dirname):
        requirement_registry = RequirementRegistry()
        project = Project(dirname, requirement_registry)
        assert 1 == len(project.requirements)
        assert "FOO" == project.requirements[0].env_var
        assert dict(default="hello") == project.requirements[0].options

    with_directory_contents({PROJECT_FILENAME: """
runtime:
    FOO: { default: "hello" }
"""}, check_some_env_var)
