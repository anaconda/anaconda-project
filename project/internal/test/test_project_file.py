from project.internal.project_file import ProjectFile, YamlFile, PROJECT_FILENAME
from project.internal.test.tmpfile_utils import with_file_contents, with_directory_contents
from project.plugins.requirement import RequirementRegistry, EnvVarRequirement

import codecs
import errno
import os
import pytest


def test_read_yaml_file_and_get_value():
    def check_abc(filename):
        yaml = YamlFile(filename)
        value = yaml.get_value("a", "b")
        assert "c" == value

    with_file_contents("""
a:
  b: c
""", check_abc)


def test_read_yaml_file_and_get_default():
    def check_abc(filename):
        yaml = YamlFile(filename)
        value = yaml.get_value("a", "z", "default")
        assert "default" == value

    with_file_contents("""
a:
  b: c
""", check_abc)


def test_read_yaml_file_and_get_list_valued_section():
    def get_list_value(filename):
        yaml = YamlFile(filename)
        value = yaml.get_value("a")
        assert [1, 2, 3] == value

    with_file_contents("""
a: [1,2,3]
""", get_list_value)


def test_read_yaml_file_and_get_default_due_to_missing_section():
    def check_abc(filename):
        yaml = YamlFile(filename)
        value = yaml.get_value("z", "b", "default")
        assert "default" == value

    with_file_contents("""
a:
  b: c
""", check_abc)


def test_read_missing_yaml_file_and_get_default_due_to_missing_section():
    def check_missing(dirname):
        yaml = YamlFile(os.path.join(dirname, "nope.yaml"))
        value = yaml.get_value("z", "b", "default")
        assert "default" == value

    with_directory_contents(dict(), check_missing)


def test_read_yaml_file_that_is_a_directory():
    def check_read_directory(dirname):
        filename = os.path.join(dirname, "dir.yaml")
        os.makedirs(filename)
        with pytest.raises(IOError) as excinfo:
            YamlFile(filename)
        assert errno.EISDIR == excinfo.value.errno

    with_directory_contents(dict(), check_read_directory)


def test_read_yaml_file_and_change_value():
    # ruamel.yaml does reformat yaml files a little bit,
    # for example it picks its own indentation, even
    # as it tries to keep comments and stuff. So
    # this test cheats by using input that happens
    # to be in the format ruamel.yaml will generate.
    # Oh well.
    template = """
# this is a comment 1
a:
  # this is a comment 2
  b: %s
"""

    template = template[1:]  # chop leading newline

    original_value = "c"
    original_content = template % (original_value)
    changed_value = 42
    changed_content = template % (changed_value)

    def change_abc(filename):
        yaml = YamlFile(filename)
        value = yaml.get_value("a", "b")
        assert original_value == value
        yaml.set_value("a", "b", changed_value)
        yaml.save()

        import codecs
        with codecs.open(filename, 'r', 'utf-8') as file:
            changed = file.read()
            assert changed_content == changed

        yaml2 = YamlFile(filename)
        value2 = yaml2.get_value("a", "b")
        assert changed_value == value2

    with_file_contents(original_content, change_abc)


def test_read_missing_yaml_file_and_set_value():
    def set_abc(dirname):
        filename = os.path.join(dirname, "foo.yaml")
        assert not os.path.exists(filename)
        yaml = YamlFile(filename)
        value = yaml.get_value("a", "b")
        assert value is None
        yaml.set_value("a", "b", 42)
        yaml.save()
        assert os.path.exists(filename)

        import codecs
        with codecs.open(filename, 'r', 'utf-8') as file:
            changed = file.read()
            expected = """
# Anaconda project file
a:
  b: 42
""" [1:]

            assert expected == changed

        yaml2 = YamlFile(filename)
        value2 = yaml2.get_value("a", "b")
        assert 42 == value2

    with_directory_contents(dict(), set_abc)


def test_read_yaml_file_and_add_section():
    original_content = """
a:
  b: c
"""

    def add_section(filename):
        yaml = YamlFile(filename)
        value = yaml.get_value("a", "b")
        assert "c" == value
        yaml.set_values("x.y", dict(z=42, q="rs"))
        yaml.save()

        yaml2 = YamlFile(filename)
        value2 = yaml2.get_value("a", "b")
        assert "c" == value2

        added_value = yaml2.get_value("x.y", "z")
        assert 42 == added_value

        added_value_2 = yaml2.get_value("x.y", "q")
        assert "rs" == added_value_2

        print(open(filename, 'r').read())

    with_file_contents(original_content, add_section)


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
