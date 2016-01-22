from project.internal.project_file import YamlFile
from project.internal.test.tmpfile_utils import with_file_contents


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


def test_read_yaml_file_and_get_default_due_to_missing_section():
    def check_abc(filename):
        yaml = YamlFile(filename)
        value = yaml.get_value("z", "b", "default")
        assert "default" == value

    with_file_contents("""
a:
  b: c
""", check_abc)


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
