import codecs
import os

from project.internal.test.tmpfile_utils import with_directory_contents
from project.project_file import ProjectFile, DEFAULT_PROJECT_FILENAME, possible_project_file_names


def test_create_missing_project_file():
    def create_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert not os.path.exists(filename)
        project_file = ProjectFile.load_for_directory(dirname)
        assert project_file is not None
        assert not os.path.exists(filename)
        project_file.save()
        assert os.path.exists(filename)
        with codecs.open(filename, 'r', 'utf-8') as file:
            contents = file.read()
            # this is sort of annoying that the default empty file
            # has {} in it, but in our real usage we should only
            # save the file if we set something in it probably.
            assert "# Anaconda project file\n{}\n" == contents

    with_directory_contents(dict(), create_file)


def _use_existing_project_file(relative_name):
    def check_file(dirname):
        filename = os.path.join(dirname, relative_name)
        assert os.path.exists(filename)
        project_file = ProjectFile.load_for_directory(dirname)
        value = project_file.get_value(["a", "b"])
        assert "c" == value

    with_directory_contents({relative_name: "a:\n  b: c"}, check_file)


def test_use_existing_project_file_default_name():
    _use_existing_project_file(DEFAULT_PROJECT_FILENAME)


def test_use_existing_project_file_all_names():
    for name in possible_project_file_names:
        _use_existing_project_file(name)


def test_load_directory_without_project_file():
    def read_missing_file(dirname):
        filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert not os.path.exists(filename)
        project_file = ProjectFile.load_for_directory(dirname)
        assert project_file is not None
        assert not os.path.exists(filename)
        assert project_file.get_value(["a", "b"]) is None

    with_directory_contents(dict(), read_missing_file)
