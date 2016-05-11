# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import codecs
import os
from tornado import gen
import pytest

from anaconda_project import project_ops
from anaconda_project.conda_manager import (CondaManager, CondaEnvironmentDeviations, CondaManagerError,
                                            push_conda_manager_class, pop_conda_manager_class)
from anaconda_project.project import Project
import anaconda_project.prepare as prepare
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.local_state_file import LocalStateFile
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME, ProjectFile
from anaconda_project.test.project_utils import project_no_dedicated_env
from anaconda_project.internal.test.test_conda_api import monkeypatch_conda_not_to_use_links


def test_create(monkeypatch):
    def check_create(dirname):
        subdir = os.path.join(dirname, 'foo')

        # dir doesn't exist
        project = project_ops.create(subdir, make_directory=False)
        assert [("Project directory '%s' does not exist." % subdir)] == project.problems

        # failing to create the dir
        def mock_failed_makedirs(path):
            raise IOError("nope")

        monkeypatch.setattr('os.makedirs', mock_failed_makedirs)
        project = project_ops.create(subdir, make_directory=True)
        assert [("Project directory '%s' does not exist." % subdir)] == project.problems
        monkeypatch.undo()

        # create the dir and project.yml successfully
        project = project_ops.create(subdir, make_directory=True)
        assert [] == project.problems
        assert os.path.isfile(os.path.join(subdir, DEFAULT_PROJECT_FILENAME))

    with_directory_contents(dict(), check_create)


def test_create_with_name_and_icon():
    def check_create(dirname):
        project = project_ops.create(dirname, make_directory=False, name='hello', icon='something.png')
        assert [] == project.problems
        assert os.path.isfile(os.path.join(dirname, DEFAULT_PROJECT_FILENAME))
        assert project.name == 'hello'
        assert project.icon == os.path.join(dirname, 'something.png')

    with_directory_contents({'something.png': 'not a real png'}, check_create)


def test_set_name_and_icon():
    def check(dirname):
        project = project_ops.create(dirname, make_directory=False)
        assert [] == project.problems
        assert os.path.isfile(os.path.join(dirname, DEFAULT_PROJECT_FILENAME))

        assert project.name == os.path.basename(dirname)
        assert project.icon is None

        result = project_ops.set_properties(project, name='hello', icon='something.png')
        assert result

        assert project.name == 'hello'
        assert project.icon == os.path.join(dirname, 'something.png')

    with_directory_contents({'something.png': 'not a real png'}, check)


def test_set_properties_with_project_file_problems():
    def check(dirname):
        project = Project(dirname)
        status = project_ops.set_properties(project, name='foo')
        assert not status
        assert ["variables section contains wrong value type 42, should be dict or list of requirements"
                ] == status.errors

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_set_invalid_name():
    def check(dirname):
        project = project_ops.create(dirname, make_directory=False)
        assert [] == project.problems
        assert os.path.isfile(os.path.join(dirname, DEFAULT_PROJECT_FILENAME))

        assert project.name == os.path.basename(dirname)
        assert project.icon is None

        result = project_ops.set_properties(project, name=' ')
        print(repr(result))
        assert not result
        assert 'Failed to set project properties.' == result.status_description
        assert ["%s: name: field is an empty or all-whitespace string." %
                (os.path.join(dirname, DEFAULT_PROJECT_FILENAME))] == result.errors

        assert [] == project.problems
        assert project.name == os.path.basename(dirname)
        assert project.icon is None

    with_directory_contents(dict(), check)


def test_set_invalid_icon():
    def check(dirname):
        project = project_ops.create(dirname, make_directory=False)
        assert [] == project.problems
        assert os.path.isfile(os.path.join(dirname, DEFAULT_PROJECT_FILENAME))

        assert project.name == os.path.basename(dirname)
        assert project.icon is None

        result = project_ops.set_properties(project, icon='foobar')
        assert not result
        assert 'Failed to set project properties.' == result.status_description
        assert ["Icon file %s does not exist." % os.path.join(dirname, 'foobar')] == result.errors

        assert [] == project.problems
        assert project.name == os.path.basename(dirname)
        assert project.icon is None

    with_directory_contents(dict(), check)


def test_add_variables():
    def check_set_var(dirname):
        project = project_no_dedicated_env(dirname)
        project_ops.add_variables(project, [('foo', 'bar'), ('baz', 'qux')])
        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        assert dict(foo=None, baz=None, preset=None) == re_loaded.get_value(['variables'])
        local_state = LocalStateFile.load_for_directory(dirname)

        local_state.get_value(['variables', 'foo']) == 'bar'
        local_state.get_value(['variables', 'baz']) == 'qux'

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ('variables:\n' '  preset: null')}, check_set_var)


def test_add_variables_existing_download():
    def check_set_var(dirname):
        project = project_no_dedicated_env(dirname)
        project_ops.add_variables(project, [('foo', 'bar'), ('baz', 'qux')])
        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        assert dict(foo=None, baz=None, preset=None) == re_loaded.get_value(['variables'])
        assert re_loaded.get_value(['downloads', 'datafile']) == 'http://localhost:8000/data.tgz'
        local_state = LocalStateFile.load_for_directory(dirname)

        local_state.get_value(['variables', 'foo']) == 'bar'
        local_state.get_value(['variables', 'baz']) == 'qux'
        local_state.get_value(['variables', 'datafile']) == 'http://localhost:8000/data.tgz'

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('variables:\n'
                                    '  preset: null\n'
                                    'downloads:\n'
                                    '  datafile: http://localhost:8000/data.tgz')}, check_set_var)


def test_add_variables_existing_options():
    def check_set_var(dirname):
        project = project_no_dedicated_env(dirname)
        project_ops.add_variables(project, [('foo', 'bar'), ('baz', 'qux')])
        re_loaded = ProjectFile.load_for_directory(project.directory_path)

        foo = re_loaded.get_value(['variables', 'foo'])
        assert isinstance(foo, dict)
        assert 'something' in foo
        assert foo['something'] == 42

        baz = re_loaded.get_value(['variables', 'baz'])
        assert isinstance(baz, dict)
        assert 'default' in baz
        assert baz['default'] == 'hello'

        woot = re_loaded.get_value(['variables', 'woot'])
        assert woot == 'world'

        assert re_loaded.get_value(['downloads', 'datafile']) == 'http://localhost:8000/data.tgz'

        local_state = LocalStateFile.load_for_directory(dirname)

        local_state.get_value(['variables', 'foo']) == 'bar'
        local_state.get_value(['variables', 'baz']) == 'qux'
        local_state.get_value(['variables', 'datafile']) == 'http://localhost:8000/data.tgz'

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('variables:\n'
                                    '  foo: { something: 42 }\n'
                                    '  baz: { default: "hello" }\n'
                                    '  woot: "world"\n'
                                    'downloads:\n'
                                    '  datafile: http://localhost:8000/data.tgz')}, check_set_var)


def test_remove_variables():
    def check_remove_var(dirname):
        project = project_no_dedicated_env(dirname)
        project_ops.remove_variables(project, ['foo', 'bar'])
        re_loaded = project.project_file.load_for_directory(project.directory_path)
        assert dict() == re_loaded.get_value(['variables'])
        assert re_loaded.get_value(['variables', 'foo']) is None
        assert re_loaded.get_value(['variables', 'bar']) is None
        local_state = LocalStateFile.load_for_directory(dirname)

        local_state.get_value(['variables', 'foo']) is None
        local_state.get_value(['variables', 'bar']) is None

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ('variables:\n' '  foo: baz\n  bar: qux')}, check_remove_var)


def _test_add_command_line(command_type):
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        result = project_ops.add_command(project, 'default', command_type, 'echo "test"')
        assert result

        re_loaded = project.project_file.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'default'])
        assert command[command_type] == 'echo "test"'

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    %s: echo "pass"\n') % command_type}, check_add_command)


def test_add_command_shell():
    _test_add_command_line("shell")


def test_add_command_windows():
    _test_add_command_line("windows")


def _test_add_command_windows_to_shell(command_type):
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        result = project_ops.add_command(project, 'default', 'windows', 'echo "test"')
        assert result

        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'default'])
        assert command['windows'] == 'echo "test"'
        assert command['shell'] == 'echo "pass"'

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    shell: echo "pass"\n') % command_type}, check_add_command)


def test_add_command_bokeh():
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        result = project_ops.add_command(project, 'bokeh_test', 'bokeh_app', 'file.py')
        assert result

        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'bokeh_test'])
        assert len(command.keys()) == 1
        assert command['bokeh_app'] == 'file.py'

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ""}, check_add_command)


def test_add_command_bokeh_overwrites():
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        result = project_ops.add_command(project, 'bokeh_test', 'bokeh_app', 'file.py')
        assert result

        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'bokeh_test'])
        assert len(command.keys()) == 1
        assert command['bokeh_app'] == 'file.py'

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  bokeh_test:\n'
                                    '    bokeh_app: replaced.py\n')}, check_add_command)


def test_add_command_invalid_type():
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        with pytest.raises(ValueError) as excinfo:
            project_ops.add_command(project, 'default', 'foo', 'echo "test"')
        assert 'Invalid command type foo' in str(excinfo.value)

    with_directory_contents(dict(), check_add_command)


def test_add_command_conflicting_type():
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        result = project_ops.add_command(project, 'default', 'bokeh_app', 'myapp.py')
        assert [("%s: command 'default' has conflicting statements, 'bokeh_app' must stand alone" %
                 project.project_file.filename)] == result.errors

        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'default'])
        assert command['shell'] == 'echo "pass"'
        assert 'bokeh_app' not in command

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    shell: echo "pass"\n')}, check_add_command)


def test_update_command_with_project_file_problems():
    def check(dirname):
        project = Project(dirname)
        status = project_ops.update_command(project, 'foo', 'shell', 'echo hello')

        assert not status
        assert ["variables section contains wrong value type 42, should be dict or list of requirements"
                ] == status.errors

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_update_command_invalid_type():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        with pytest.raises(ValueError) as excinfo:
            project_ops.update_command(project, 'default', 'foo', 'echo "test"')
        assert 'Invalid command type foo' in str(excinfo.value)

    with_directory_contents(dict(), check)


def test_update_command_no_command():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        with pytest.raises(ValueError) as excinfo:
            project_ops.update_command(project, 'default', 'bokeh_app')
        assert 'must also specify the command' in str(excinfo.value)

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    shell: echo "pass"\n')}, check)


def test_update_command_does_not_exist():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        result = project_ops.update_command(project, 'myapp', 'bokeh_app', 'myapp.py')
        assert not result

        assert ["No command 'myapp' found."] == result.errors

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    shell: echo "pass"\n')}, check)


def test_update_command_autogenerated():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        result = project_ops.update_command(project, 'foo.ipynb', 'bokeh_app', 'myapp.py')
        assert not result

        assert ["Autogenerated command 'foo.ipynb' can't be modified."] == result.errors

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    shell: echo "pass"\n'),
         "foo.ipynb": "stuff"}, check)


def test_update_command_conflicting_type():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.bokeh_app is None
        assert command.unix_shell_commandline == 'echo "pass"'

        result = project_ops.update_command(project, 'default', 'bokeh_app', 'myapp.py')
        assert result

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.bokeh_app == 'myapp.py'

        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'default'])
        assert command['bokeh_app'] == 'myapp.py'

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    shell: echo "pass"\n')}, check)


def test_update_command_same_type():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.unix_shell_commandline == 'echo "pass"'

        result = project_ops.update_command(project, 'default', 'shell', 'echo "blah"')
        assert result

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.unix_shell_commandline == 'echo "blah"'

        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'default'])
        assert command['shell'] == 'echo "blah"'

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    shell: echo "pass"\n')}, check)


def test_update_command_add_windows_alongside_shell():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.unix_shell_commandline == 'echo "pass"'

        result = project_ops.update_command(project, 'default', 'windows', 'echo "blah"')
        assert result

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.unix_shell_commandline == 'echo "pass"'
        assert command.windows_cmd_commandline == 'echo "blah"'

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    shell: echo "pass"\n')}, check)


def test_update_command_add_shell_alongside_windows():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.windows_cmd_commandline == 'echo "blah"'

        result = project_ops.update_command(project, 'default', 'shell', 'echo "pass"')
        assert result

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.unix_shell_commandline == 'echo "pass"'
        assert command.windows_cmd_commandline == 'echo "blah"'

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    windows: echo "blah"\n')}, check)


def test_update_command_empty_update():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.unix_shell_commandline == 'echo "pass"'

        result = project_ops.update_command(project, 'default')
        assert result

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.unix_shell_commandline == 'echo "pass"'

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    shell: echo "pass"\n')}, check)


def test_update_command_to_non_string_value():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.bokeh_app is None
        assert command.unix_shell_commandline == 'echo "pass"'

        result = project_ops.update_command(project, 'default', 'notebook', 42)
        assert not result
        assert [("%s: command 'default' attribute 'notebook' should be a string not '42'" %
                 project.project_file.filename)] == result.errors

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.unix_shell_commandline == 'echo "pass"'

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    shell: echo "pass"\n')}, check)


def _monkeypatch_download_file(monkeypatch, dirname, filename='MYDATA', checksum=None):
    @gen.coroutine
    def mock_downloader_run(self, loop):
        class Res:
            pass

        res = Res()
        res.code = 200
        with open(os.path.join(dirname, filename), 'w') as out:
            out.write('data')
        if checksum:
            self._hash = checksum
        raise gen.Return(res)

    monkeypatch.setattr("anaconda_project.internal.http_client.FileDownloader.run", mock_downloader_run)


def _monkeypatch_download_file_fails(monkeypatch, dirname):
    @gen.coroutine
    def mock_downloader_run(self, loop):
        class Res:
            pass

        res = Res()
        res.code = 404
        raise gen.Return(res)

    monkeypatch.setattr("anaconda_project.internal.http_client.FileDownloader.run", mock_downloader_run)


def _monkeypatch_download_file_fails_to_get_http_response(monkeypatch, dirname):
    @gen.coroutine
    def mock_downloader_run(self, loop):
        self._errors.append("Nope nope nope")
        raise gen.Return(None)

    monkeypatch.setattr("anaconda_project.internal.http_client.FileDownloader.run", mock_downloader_run)


def test_add_download(monkeypatch):
    def check(dirname):
        _monkeypatch_download_file(monkeypatch, dirname)

        project = Project(dirname)
        status = project_ops.add_download(project, 'MYDATA', 'http://localhost:123456')

        assert os.path.isfile(os.path.join(dirname, "MYDATA"))
        assert status
        assert isinstance(status.logs, list)
        assert [] == status.errors

        # be sure download was added to the file and saved
        project2 = Project(dirname)
        assert {"url": 'http://localhost:123456'} == project2.project_file.get_value(['downloads', 'MYDATA'])

    with_directory_contents(dict(), check)


def test_add_download_with_filename(monkeypatch):
    def check(dirname):
        FILENAME = 'TEST_FILENAME'
        _monkeypatch_download_file(monkeypatch, dirname, FILENAME)

        project = Project(dirname)
        status = project_ops.add_download(project, 'MYDATA', 'http://localhost:123456', FILENAME)

        assert os.path.isfile(os.path.join(dirname, FILENAME))
        assert status
        assert isinstance(status.logs, list)
        assert [] == status.errors

        # be sure download was added to the file and saved
        project2 = Project(dirname)
        requirement = project2.project_file.get_value(['downloads', 'MYDATA'])
        assert requirement['url'] == 'http://localhost:123456'
        assert requirement['filename'] == FILENAME

    with_directory_contents(dict(), check)


def test_add_download_with_checksum(monkeypatch):
    def check(dirname):
        FILENAME = 'MYDATA'
        _monkeypatch_download_file(monkeypatch, dirname, checksum='DIGEST')

        project = Project(dirname)
        status = project_ops.add_download(project,
                                          'MYDATA',
                                          'http://localhost:123456',
                                          hash_algorithm='md5',
                                          hash_value='DIGEST')
        assert os.path.isfile(os.path.join(dirname, FILENAME))
        assert status
        assert isinstance(status.logs, list)
        assert [] == status.errors

        # be sure download was added to the file and saved
        project2 = Project(dirname)
        requirement = project2.project_file.get_value(['downloads', 'MYDATA'])
        assert requirement['url'] == 'http://localhost:123456'
        assert requirement['md5'] == 'DIGEST'

    with_directory_contents(dict(), check)


def test_add_download_which_already_exists(monkeypatch):
    def check(dirname):
        _monkeypatch_download_file(monkeypatch, dirname, filename='foobar')

        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        assert dict(url='http://localhost:56789',
                    filename='foobar') == dict(project.project_file.get_value(['downloads', 'MYDATA']))

        status = project_ops.add_download(project, 'MYDATA', 'http://localhost:123456')

        assert os.path.isfile(os.path.join(dirname, "foobar"))
        assert status
        assert isinstance(status.logs, list)
        assert [] == status.errors

        # be sure download was added to the file and saved, and
        # the filename attribute was kept
        project2 = project_no_dedicated_env(dirname)
        assert dict(url='http://localhost:123456',
                    filename='foobar') == dict(project2.project_file.get_value(['downloads', 'MYDATA']))

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: 'downloads:\n    MYDATA: { url: "http://localhost:56789", filename: foobar }'},
        check)


def test_add_download_which_already_exists_with_fname(monkeypatch):
    def check(dirname):
        _monkeypatch_download_file(monkeypatch, dirname, filename='bazqux')

        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        assert dict(url='http://localhost:56789',
                    filename='foobar') == dict(project.project_file.get_value(['downloads', 'MYDATA']))

        status = project_ops.add_download(project, 'MYDATA', 'http://localhost:123456', filename="bazqux")

        assert os.path.isfile(os.path.join(dirname, "bazqux"))
        assert status
        assert isinstance(status.logs, list)
        assert [] == status.errors

        # be sure download was added to the file and saved, and
        # the filename attribute was kept
        project2 = project_no_dedicated_env(dirname)
        assert dict(url='http://localhost:123456',
                    filename='bazqux') == dict(project2.project_file.get_value(['downloads', 'MYDATA']))

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: 'downloads:\n    MYDATA: { url: "http://localhost:56789", filename: foobar }'},
        check)


def test_add_download_fails(monkeypatch):
    def check(dirname):
        _monkeypatch_download_file_fails(monkeypatch, dirname)

        project = Project(dirname)
        status = project_ops.add_download(project, 'MYDATA', 'http://localhost:123456')

        assert not os.path.isfile(os.path.join(dirname, "MYDATA"))
        assert not status
        assert isinstance(status.logs, list)
        assert ['Error downloading http://localhost:123456: response code 404'] == status.errors

        # be sure download was NOT added to the file
        project2 = Project(dirname)
        assert project2.project_file.get_value(['downloads', 'MYDATA']) is None
        # should have been dropped from the original project object also
        assert project.project_file.get_value(['downloads', 'MYDATA']) is None

    with_directory_contents(dict(), check)


def test_add_download_fails_to_get_http_response(monkeypatch):
    def check(dirname):
        _monkeypatch_download_file_fails_to_get_http_response(monkeypatch, dirname)

        project = Project(dirname)
        status = project_ops.add_download(project, 'MYDATA', 'http://localhost:123456')

        assert not os.path.isfile(os.path.join(dirname, "MYDATA"))
        assert not status
        assert ['Nope nope nope'] == status.errors

        # be sure download was NOT added to the file
        project2 = Project(dirname)
        assert project2.project_file.get_value(['downloads', 'MYDATA']) is None
        # should have been dropped from the original project object also
        assert project.project_file.get_value(['downloads', 'MYDATA']) is None

    with_directory_contents(dict(), check)


def test_add_download_with_project_file_problems():
    def check(dirname):
        project = Project(dirname)
        status = project_ops.add_download(project, 'MYDATA', 'http://localhost:123456')

        assert not os.path.isfile(os.path.join(dirname, "MYDATA"))
        assert not status
        assert ["variables section contains wrong value type 42, should be dict or list of requirements"
                ] == status.errors

        # be sure download was NOT added to the file
        project2 = Project(dirname)
        assert project2.project_file.get_value(['downloads', 'MYDATA']) is None
        # should have been dropped from the original project object also
        assert project.project_file.get_value(['downloads', 'MYDATA']) is None

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


# the other add_environment tests use a mock CondaManager, but we want to have
# one test that does the real thing to be sure it works.
def test_add_environment_with_real_conda_manager(monkeypatch):
    monkeypatch_conda_not_to_use_links(monkeypatch)

    def check(dirname):
        project = Project(dirname)
        status = project_ops.add_environment(project, name='foo', packages=['numpy'], channels=[])
        if not status:
            print(status.status_description)
            print(repr(status.errors))
        assert status

        # be sure it was really done
        project2 = Project(dirname)
        env_commented_map = project2.project_file.get_value(['environments', 'foo'])
        assert dict(dependencies=['numpy'], channels=[]) == dict(env_commented_map)
        assert os.path.isdir(os.path.join(dirname, 'envs', 'foo', 'conda-meta'))

    with_directory_contents(dict(), check)


def _push_conda_test(fix_works, missing_packages, wrong_version_packages, remove_error):
    class TestCondaManager(CondaManager):
        def __init__(self):
            self.fix_works = fix_works
            self.fixed = False
            self.deviations = CondaEnvironmentDeviations(summary="test",
                                                         missing_packages=missing_packages,
                                                         wrong_version_packages=wrong_version_packages)

        def find_environment_deviations(self, prefix, spec):
            if self.fixed:
                return CondaEnvironmentDeviations(summary="fixed", missing_packages=(), wrong_version_packages=())
            else:
                return self.deviations

        def fix_environment_deviations(self, prefix, spec, deviations=None):
            if self.fix_works:
                self.fixed = True

        def remove_packages(self, prefix, packages):
            if remove_error is not None:
                raise CondaManagerError(remove_error)

    push_conda_manager_class(TestCondaManager)


def _pop_conda_test():
    pop_conda_manager_class()


def _with_conda_test(f, fix_works=True, missing_packages=(), wrong_version_packages=(), remove_error=None):
    try:
        _push_conda_test(fix_works, missing_packages, wrong_version_packages, remove_error)
        f()
    finally:
        _pop_conda_test()


def test_add_environment():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            status = project_ops.add_environment(project, name='foo', packages=[], channels=[])
            assert status
            # with "None" for the args
            status = project_ops.add_environment(project, name='bar', packages=None, channels=None)
            assert status

        _with_conda_test(attempt)

        # be sure we really made the config changes
        project2 = Project(dirname)
        assert dict(dependencies=[], channels=[]) == dict(project2.project_file.get_value(['environments', 'foo']))
        assert dict(dependencies=[], channels=[]) == dict(project2.project_file.get_value(['environments', 'bar']))

    with_directory_contents(dict(), check)


def test_add_environment_with_packages_and_channels():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            status = project_ops.add_environment(project,
                                                 name='foo',
                                                 packages=['a', 'b', 'c'],
                                                 channels=['c1', 'c2', 'c3'])
            assert status

        _with_conda_test(attempt)

        # be sure download was added to the file and saved
        project2 = Project(dirname)
        assert dict(dependencies=['a', 'b', 'c'],
                    channels=['c1', 'c2', 'c3']) == dict(project2.project_file.get_value(['environments', 'foo']))

    with_directory_contents(dict(), check)


def test_add_environment_extending_existing_lists():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            status = project_ops.add_environment(project,
                                                 name='foo',
                                                 packages=['a', 'b', 'c'],
                                                 channels=['c1', 'c2', 'c3'])
            assert status

        _with_conda_test(attempt)

        # be sure download was added to the file and saved
        project2 = Project(dirname)
        assert dict(dependencies=['b', 'a', 'c'],
                    channels=['c3', 'c1', 'c2']) == dict(project2.project_file.get_value(['environments', 'foo']))

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
environments:
  foo:
    dependencies: [ 'b' ]
    channels: [ 'c3']
"""}, check)


def test_add_dependencies_to_all_environments():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            status = project_ops.add_dependencies(project,
                                                  environment=None,
                                                  packages=['foo', 'bar'],
                                                  channels=['hello', 'world'])
            assert status
            assert [] == status.errors

        _with_conda_test(attempt)

        # be sure we really made the config changes
        project2 = Project(dirname)
        assert ['foo', 'bar'] == list(project2.project_file.get_value('dependencies'))
        assert ['hello', 'world'] == list(project2.project_file.get_value('channels'))

    with_directory_contents(dict(), check)


def test_add_dependencies_nonexistent_environment():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            status = project_ops.add_dependencies(project,
                                                  environment="not_an_env",
                                                  packages=['foo', 'bar'],
                                                  channels=['hello', 'world'])
            assert not status
            assert [] == status.errors

        _with_conda_test(attempt)

    with_directory_contents(dict(), check)


def test_remove_dependencies_from_all_environments():
    def check(dirname):
        def attempt():
            os.makedirs(os.path.join(dirname, 'envs', 'hello'))  # forces us to really run remove_packages
            project = Project(dirname)
            assert ['foo', 'bar', 'baz'] == list(project.project_file.get_value('dependencies'))
            assert ['foo', 'woot'] == list(project.project_file.get_value(
                ['environments', 'hello', 'dependencies'], []))
            status = project_ops.remove_dependencies(project, environment=None, packages=['foo', 'bar'])
            assert status
            assert [] == status.errors

        _with_conda_test(attempt, remove_error="Removal fail")

        # be sure we really made the config changes
        project2 = Project(dirname)
        assert ['baz'] == list(project2.project_file.get_value('dependencies'))
        assert ['woot'] == list(project2.project_file.get_value(['environments', 'hello', 'dependencies']))

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
dependencies:
  - foo
  - bar
  - baz
environments:
  hello:
    dependencies:
     - foo
     - woot
"""}, check)


def test_remove_dependencies_from_one_environment():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            assert ['qbert', 'foo', 'bar'] == list(project.project_file.get_value('dependencies'))
            assert ['foo'] == list(project.project_file.get_value(['environments', 'hello', 'dependencies'], []))
            status = project_ops.remove_dependencies(project, environment='hello', packages=['foo', 'bar'])
            assert status
            assert [] == status.errors

        _with_conda_test(attempt)

        # be sure we really made the config changes
        project2 = Project(dirname)
        # note that hello will still inherit the deps from the global dependencies,
        # and that's fine
        assert ['qbert'] == list(project2.project_file.get_value('dependencies'))
        assert [] == list(project2.project_file.get_value(['environments', 'hello', 'dependencies'], []))

        # be sure we didn't delete comments from global dependencies section
        content = codecs.open(project2.project_file.filename, 'r', 'utf-8').read()
        assert '# this is a pre comment' in content
        assert '# this is a post comment' in content

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
dependencies:
  # this is a pre comment
  - qbert # this is a post comment
  - foo
  - bar
environments:
  hello:
    dependencies:
     - foo
"""}, check)


def test_remove_dependencies_from_one_environment_leaving_others_unaffected():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            assert ['qbert', 'foo', 'bar'] == list(project.project_file.get_value('dependencies'))
            assert ['foo'] == list(project.project_file.get_value(['environments', 'hello', 'dependencies'], []))
            status = project_ops.remove_dependencies(project, environment='hello', packages=['foo', 'bar'])
            assert status
            assert [] == status.errors

        _with_conda_test(attempt)

        # be sure we really made the config changes
        project2 = Project(dirname)
        assert ['qbert'] == list(project2.project_file.get_value('dependencies'))
        assert [] == list(project2.project_file.get_value(['environments', 'hello', 'dependencies'], []))
        assert set(['baz', 'foo', 'bar']) == set(project2.project_file.get_value(
            ['environments', 'another', 'dependencies'], []))
        assert project2.conda_environments['another'].conda_package_names_set == set(['qbert', 'foo', 'bar', 'baz'])
        assert project2.conda_environments['hello'].conda_package_names_set == set(['qbert'])

        # be sure we didn't delete comments from the env
        content = codecs.open(project2.project_file.filename, 'r', 'utf-8').read()
        assert '# this is a pre comment' in content
        assert '# this is a post comment' in content

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
dependencies:
  - qbert
  - foo
  - bar
environments:
  hello:
    dependencies:
     - foo
  another:
    dependencies:
     # this is a pre comment
     - baz # this is a post comment
"""}, check)


def test_remove_dependencies_from_nonexistent_environment():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            assert ['foo', 'bar'] == list(project.project_file.get_value('dependencies'))
            status = project_ops.remove_dependencies(project, environment='not_an_environment', packages=['foo', 'bar'])
            assert not status
            assert [] == status.errors
            assert "Environment not_an_environment doesn't exist." == status.status_description

        _with_conda_test(attempt)

        # be sure we didn't make the config changes
        project2 = Project(dirname)
        assert ['foo', 'bar'] == list(project2.project_file.get_value('dependencies'))

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
dependencies:
  - foo
  - bar
"""}, check)


def test_remove_dependencies_with_project_file_problems():
    def check(dirname):
        project = Project(dirname)
        status = project_ops.remove_dependencies(project, environment=None, packages=['foo'])

        assert not status
        assert ["variables section contains wrong value type 42, should be dict or list of requirements"
                ] == status.errors

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def _monkeypatch_can_connect_to_socket_on_standard_redis_port(monkeypatch):
    from anaconda_project.plugins.network_util import can_connect_to_socket as real_can_connect_to_socket

    can_connect_args_list = []

    def mock_can_connect_to_socket(host, port, timeout_seconds=0.5):
        can_connect_args = dict()
        can_connect_args['host'] = host
        can_connect_args['port'] = port
        can_connect_args['timeout_seconds'] = timeout_seconds
        can_connect_args_list.append(can_connect_args)
        if port == 6379:
            return True
        else:
            return real_can_connect_to_socket(host, port, timeout_seconds)

    monkeypatch.setattr("anaconda_project.plugins.network_util.can_connect_to_socket", mock_can_connect_to_socket)

    return can_connect_args_list


def test_add_service(monkeypatch):
    def check(dirname):
        _monkeypatch_can_connect_to_socket_on_standard_redis_port(monkeypatch)

        project = Project(dirname)
        status = project_ops.add_service(project, service_type='redis')

        assert status
        assert isinstance(status.logs, list)
        assert [] == status.errors

        # be sure service was added to the file and saved
        project2 = Project(dirname)
        assert 'redis' == project2.project_file.get_value(['services', 'REDIS_URL'])

    with_directory_contents(dict(), check)


def test_add_service_nondefault_variable_name(monkeypatch):
    def check(dirname):
        _monkeypatch_can_connect_to_socket_on_standard_redis_port(monkeypatch)

        project = Project(dirname)
        status = project_ops.add_service(project, service_type='redis', variable_name='MY_SPECIAL_REDIS')

        assert status
        assert isinstance(status.logs, list)
        assert [] == status.errors

        # be sure service was added to the file and saved
        project2 = Project(dirname)
        assert 'redis' == project2.project_file.get_value(['services', 'MY_SPECIAL_REDIS'])

    with_directory_contents(dict(), check)


def test_add_service_with_project_file_problems():
    def check(dirname):
        project = Project(dirname)
        status = project_ops.add_service(project, service_type='redis')

        assert not status
        assert ["variables section contains wrong value type 42, should be dict or list of requirements"
                ] == status.errors

        # be sure service was NOT added to the file
        project2 = Project(dirname)
        assert project2.project_file.get_value(['services', 'REDIS_URL']) is None
        # should have been dropped from the original project object also
        assert project.project_file.get_value(['services', 'REDIS_URL']) is None

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_add_service_already_exists(monkeypatch):
    def check(dirname):
        _monkeypatch_can_connect_to_socket_on_standard_redis_port(monkeypatch)

        project = Project(dirname)
        status = project_ops.add_service(project, service_type='redis')

        assert status
        assert isinstance(status.logs, list)
        assert [] == status.errors

        # be sure service was added to the file and saved
        project2 = Project(dirname)
        assert 'redis' == project2.project_file.get_value(['services', 'REDIS_URL'])

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, check)


def test_add_service_already_exists_with_different_type(monkeypatch):
    def check(dirname):
        _monkeypatch_can_connect_to_socket_on_standard_redis_port(monkeypatch)

        project = Project(dirname)
        status = project_ops.add_service(project, service_type='redis')

        assert not status
        # Once we have >1 known service types, we should change this test
        # to use the one other than redis and then this error will change.
        assert ["Service REDIS_URL has an unknown type 'foo'."] == status.errors

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: foo
"""}, check)


def test_add_service_already_exists_as_non_service(monkeypatch):
    def check(dirname):
        _monkeypatch_can_connect_to_socket_on_standard_redis_port(monkeypatch)

        project = Project(dirname)
        status = project_ops.add_service(project, service_type='redis')

        assert not status
        assert ['Variable REDIS_URL is already in use.'] == status.errors

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
variables:
  REDIS_URL: something
"""}, check)


def test_add_service_bad_service_type(monkeypatch):
    def check(dirname):
        _monkeypatch_can_connect_to_socket_on_standard_redis_port(monkeypatch)

        project = Project(dirname)
        status = project_ops.add_service(project, service_type='not_a_service')

        assert not status
        assert ["Unknown service type 'not_a_service', we know about: redis"] == status.errors

    with_directory_contents(dict(), check)


def test_clean(monkeypatch):
    def mock_create(prefix, pkgs, channels):
        os.makedirs(os.path.join(prefix, "conda-meta"))

    monkeypatch.setattr('anaconda_project.internal.conda_api.create', mock_create)

    def check(dirname):
        project = Project(dirname)

        result = prepare.prepare_without_interaction(project, conda_environment_name='foo')

        assert result
        envs_dir = os.path.join(dirname, "envs")
        assert os.path.isdir(os.path.join(envs_dir, "foo"))

        # prepare again with 'bar' this time
        result = prepare.prepare_without_interaction(project, conda_environment_name='bar')
        assert result
        bar_dir = os.path.join(dirname, "envs", "bar")
        assert os.path.isdir(bar_dir)

        # we don't really have a service in the test project file because
        # redis-server doesn't work on Windows and it's good to run this
        # test on Windows. So create some fake junk in services dir.
        services_dir = os.path.join(dirname, "services")
        os.makedirs(os.path.join(services_dir, "leftover-debris"))

        status = project_ops.clean(project, result)
        assert status
        assert status.status_description == "Cleaned."
        assert status.logs == [("Deleted environment files in %s." % bar_dir), ("Removing %s." % services_dir),
                               ("Removing %s." % envs_dir)]
        assert status.errors == []

        assert not os.path.isdir(os.path.join(dirname, "envs"))
        assert not os.path.isdir(os.path.join(dirname, "services"))

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
environments:
   foo: {}
   bar: {}
"""}, check)


def test_clean_failed_delete(monkeypatch):
    def mock_create(prefix, pkgs, channels):
        os.makedirs(os.path.join(prefix, "conda-meta"))

    monkeypatch.setattr('anaconda_project.internal.conda_api.create', mock_create)

    def check(dirname):
        project = Project(dirname)

        result = prepare.prepare_without_interaction(project, conda_environment_name='foo')

        assert result
        envs_dir = os.path.join(dirname, "envs")
        assert os.path.isdir(os.path.join(envs_dir, "foo"))

        # prepare again with 'bar' this time
        result = prepare.prepare_without_interaction(project, conda_environment_name='bar')
        assert result
        bar_dir = os.path.join(dirname, "envs", "bar")
        assert os.path.isdir(bar_dir)

        # we don't really have a service in the test project file because
        # redis-server doesn't work on Windows and it's good to run this
        # test on Windows. So create some fake junk in services dir.
        services_dir = os.path.join(dirname, "services")
        os.makedirs(os.path.join(services_dir, "leftover-debris"))

        def mock_rmtree(path):
            raise IOError("No rmtree here")

        monkeypatch.setattr('shutil.rmtree', mock_rmtree)

        status = project_ops.clean(project, result)
        assert not status
        assert status.status_description == "Failed to clean everything up."
        assert status.logs == [("Removing %s." % services_dir), ("Removing %s." % envs_dir)]
        assert status.errors == [("Failed to remove environment files in %s: No rmtree here." % bar_dir),
                                 ("Error removing %s: No rmtree here." % services_dir),
                                 ("Error removing %s: No rmtree here." % envs_dir)]

        assert os.path.isdir(os.path.join(dirname, "envs"))
        assert os.path.isdir(os.path.join(dirname, "services"))

        # so with_directory_contents can remove our tmp dir
        monkeypatch.undo()

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
environments:
   foo: {}
   bar: {}
"""}, check)
