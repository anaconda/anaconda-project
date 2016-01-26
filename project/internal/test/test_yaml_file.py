from project.internal.yaml_file import YamlFile
from project.internal.test.tmpfile_utils import with_file_contents, with_directory_contents

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


def test_read_empty_yaml_file_and_get_default():
    def check_empty(filename):
        yaml = YamlFile(filename)
        value = yaml.get_value("a", "z", "default")
        assert "default" == value

    with_file_contents("", check_empty)


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
# yaml file
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


def test_multiple_saves_ignored_if_not_dirty():
    def check_dirty_handling(dirname):
        filename = os.path.join(dirname, "foo.yaml")
        assert not os.path.exists(filename)
        yaml = YamlFile(filename)
        yaml.set_value("a", "b", 42)
        yaml.save()
        assert os.path.exists(filename)
        time1 = os.path.getmtime(filename)

        yaml.save()
        assert time1 == os.path.getmtime(filename)
        yaml.save()
        assert time1 == os.path.getmtime(filename)

        yaml.set_value("a", "b", 43)
        assert time1 == os.path.getmtime(filename)
        yaml.save()
        # OS mtime resolution might leave these equal
        assert time1 <= os.path.getmtime(filename)

    with_directory_contents(dict(), check_dirty_handling)


def test_save_ignored_if_not_dirty_after_load():
    def check_dirty_handling(dirname):
        filename = os.path.join(dirname, "foo.yaml")
        assert not os.path.exists(filename)
        yaml = YamlFile(filename)
        yaml.set_value("a", "b", 42)
        yaml.save()
        assert os.path.exists(filename)
        time1 = os.path.getmtime(filename)

        yaml2 = YamlFile(filename)
        assert time1 == os.path.getmtime(filename)
        yaml2.save()
        assert time1 == os.path.getmtime(filename)

    with_directory_contents(dict(), check_dirty_handling)


def test_throw_if_cannot_create_directory(monkeypatch):
    def mock_makedirs(path, mode=0):
        raise IOError("this is not EEXIST")

    monkeypatch.setattr("os.makedirs", mock_makedirs)

    def check_throw_if_cannot_create(dirname):
        subdir = "bar"
        filename = os.path.join(dirname, subdir, "foo.yaml")

        yaml = YamlFile(filename)
        yaml.set_value("a", "b", 42)
        with pytest.raises(IOError) as excinfo:
            yaml.save()
        assert "this is not EEXIST" in repr(excinfo.value)

    with_directory_contents(dict(), check_throw_if_cannot_create)
