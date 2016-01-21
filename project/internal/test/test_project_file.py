from project.internal.project_file import YamlFile
from project.internal.test.tmpfile_utils import with_file_contents


def test_read_yaml_file():
    def check_abc(filename):
        yaml = YamlFile(filename)
        value = yaml.get_value("a", "b")
        assert "c" == value

    with_file_contents("""
a:
    b: c
    """, check_abc)
