from project.internal.project_file import ProjectFile, PROJECT_FILENAME
from project.internal.test.tmpfile_utils import with_directory_contents
from project.plugins.requirement import RequirementRegistry, EnvVarRequirement

import codecs
import os


def test_create_missing_project_file():
    def create_file(dirname):
        filename = os.path.join(dirname, PROJECT_FILENAME)
        assert not os.path.exists(filename)
        project_file = ProjectFile.ensure_for_directory(dirname, RequirementRegistry())
        assert project_file is not None
        assert os.path.exists(filename)
        with codecs.open(filename, 'r', 'utf-8') as file:
            contents = file.read()
            # this is sort of annoying that the default empty file
            # has {} in it, but in our real usage we should only
            # save the file if we set something in it probably.
            assert "# Anaconda project file\n{}\n" == contents

    with_directory_contents(dict(), create_file)


def test_use_existing_project_file():
    def check_file(dirname):
        filename = os.path.join(dirname, PROJECT_FILENAME)
        assert os.path.exists(filename)
        project_file = ProjectFile.ensure_for_directory(dirname, RequirementRegistry())
        value = project_file.get_value("a", "b")
        assert "c" == value

    with_directory_contents({PROJECT_FILENAME: "a:\n  b: c"}, check_file)


def test_load_directory_without_project_file():
    def read_missing_file(dirname):
        filename = os.path.join(dirname, PROJECT_FILENAME)
        assert not os.path.exists(filename)
        project_file = ProjectFile.load_for_directory(dirname, RequirementRegistry())
        assert project_file is not None
        assert not os.path.exists(filename)
        assert project_file.get_value("a", "b") is None

    with_directory_contents(dict(), read_missing_file)


def test_load_list_of_runtime_requirements():
    def check_file(dirname):
        filename = os.path.join(dirname, PROJECT_FILENAME)
        assert os.path.exists(filename)
        project_file = ProjectFile.load_for_directory(dirname, RequirementRegistry())
        assert [] == project_file.problems
        requirements = project_file.requirements
        assert 2 == len(requirements)
        assert isinstance(requirements[0], EnvVarRequirement)
        assert 'FOO' == requirements[0].env_var
        assert isinstance(requirements[1], EnvVarRequirement)
        assert 'BAR' == requirements[1].env_var
        assert len(project_file.problems) == 0

    with_directory_contents({PROJECT_FILENAME: "runtime:\n  - FOO\n  - BAR\n"}, check_file)


def test_load_dict_of_runtime_requirements():
    def check_file(dirname):
        filename = os.path.join(dirname, PROJECT_FILENAME)
        assert os.path.exists(filename)
        project_file = ProjectFile.load_for_directory(dirname, RequirementRegistry())
        assert [] == project_file.problems
        requirements = project_file.requirements
        assert 2 == len(requirements)
        assert isinstance(requirements[0], EnvVarRequirement)
        assert 'FOO' == requirements[0].env_var
        assert dict(a=1) == requirements[0].options
        assert isinstance(requirements[1], EnvVarRequirement)
        assert 'BAR' == requirements[1].env_var
        assert dict(b=2) == requirements[1].options
        assert len(project_file.problems) == 0

    with_directory_contents({PROJECT_FILENAME: "runtime:\n  FOO: { a: 1 }\n  BAR: { b: 2 }\n"}, check_file)


def test_non_string_runtime_requirements():
    def check_file(dirname):
        filename = os.path.join(dirname, PROJECT_FILENAME)
        assert os.path.exists(filename)
        project_file = ProjectFile.load_for_directory(dirname, RequirementRegistry())
        assert 2 == len(project_file.problems)
        assert 0 == len(project_file.requirements)
        assert "42 is not a string" in project_file.problems[0]
        assert "43 is not a string" in project_file.problems[1]

    with_directory_contents({PROJECT_FILENAME: "runtime:\n  - 42\n  - 43\n"}, check_file)


def test_bad_runtime_requirements_options():
    def check_file(dirname):
        filename = os.path.join(dirname, PROJECT_FILENAME)
        assert os.path.exists(filename)
        project_file = ProjectFile.load_for_directory(dirname, RequirementRegistry())
        assert 2 == len(project_file.problems)
        assert 0 == len(project_file.requirements)
        assert "key FOO with value 42; the value must be a dict" in project_file.problems[0]
        assert "key BAR with value baz; the value must be a dict" in project_file.problems[1]

    with_directory_contents({PROJECT_FILENAME: "runtime:\n  FOO: 42\n  BAR: baz\n"}, check_file)


def test_runtime_requirements_not_a_collection():
    def check_file(dirname):
        filename = os.path.join(dirname, PROJECT_FILENAME)
        assert os.path.exists(filename)
        project_file = ProjectFile.load_for_directory(dirname, RequirementRegistry())
        assert 1 == len(project_file.problems)
        assert 0 == len(project_file.requirements)
        assert "runtime section contains wrong value type 42" in project_file.problems[0]

    with_directory_contents({PROJECT_FILENAME: "runtime:\n  42\n"}, check_file)
