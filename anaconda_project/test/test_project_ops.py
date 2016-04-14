# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import os
from tornado import gen

from anaconda_project import project_ops
from anaconda_project.conda_manager import (CondaManager, CondaEnvironmentDeviations, push_conda_manager_class,
                                            pop_conda_manager_class)
from anaconda_project.project import Project
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.local_state_file import LocalStateFile
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME, ProjectFile
from anaconda_project.test.project_utils import project_no_dedicated_env


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


def _test_add_command_shell(command_type):
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        project_ops.add_command(project, command_type, 'default', 'echo "test"')

        re_loaded = project.project_file.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'default'])
        assert command['shell'] == 'echo "test"'
        assert command['windows'] == 'echo "test"'

        local_state = LocalStateFile.load_for_directory(dirname)
        command = local_state.get_value(['commands', 'default'])
        assert command['shell'] == 'echo "test"'
        assert command['windows'] == 'echo "test"'

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    shell: echo "pass"\n')}, check_add_command)


def test_add_command_shell():
    _test_add_command_shell("shell")


def test_add_command_windows():
    _test_add_command_shell("windows")


def test_add_command_bokeh():
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        project_ops.add_command(project, 'bokeh_app', 'bokeh_test', 'file.py')

        re_loaded = project.project_file.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'bokeh_test'])
        assert len(command.keys()) == 1
        assert command['bokeh_app'] == 'file.py'

        local_state = LocalStateFile.load_for_directory(dirname)
        command = local_state.get_value(['commands', 'bokeh_test'])
        assert len(command.keys()) == 1
        assert command['bokeh_app'] == 'file.py'

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    shell: echo "pass"\n')}, check_add_command)


def test_add_command_bokeh_overwrites():
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        project_ops.add_command(project, 'bokeh_app', 'bokeh_test', 'file.py')

        re_loaded = project.project_file.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'bokeh_test'])
        assert len(command.keys()) == 1
        assert command['bokeh_app'] == 'file.py'

        local_state = LocalStateFile.load_for_directory(dirname)
        command = local_state.get_value(['commands', 'bokeh_test'])
        assert len(command.keys()) == 1
        assert command['bokeh_app'] == 'file.py'

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  bokeh_test:\n'
                                    '    bokeh_app: replaced.py\n')}, check_add_command)


def _monkeypatch_download_file(monkeypatch, dirname, filename='MYDATA'):
    @gen.coroutine
    def mock_downloader_run(self, loop):
        class Res:
            pass

        res = Res()
        res.code = 200
        with open(os.path.join(dirname, filename), 'w') as out:
            out.write('data')
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
        assert 'http://localhost:123456' == project2.project_file.get_value(['downloads', 'MYDATA'])

    with_directory_contents(dict(), check)


def test_add_download_which_already_exists(monkeypatch):
    def check(dirname):
        _monkeypatch_download_file(monkeypatch, dirname, filename='foobar')

        project = Project(dirname)
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
        project2 = Project(dirname)
        assert dict(url='http://localhost:123456',
                    filename='foobar') == dict(project2.project_file.get_value(['downloads', 'MYDATA']))

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
downloads:
    MYDATA: { url: "http://localhost:56789", filename: foobar }
"""}, check)


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
        assert status is None

        # be sure download was NOT added to the file
        project2 = Project(dirname)
        assert project2.project_file.get_value(['downloads', 'MYDATA']) is None
        # should have been dropped from the original project object also
        assert project.project_file.get_value(['downloads', 'MYDATA']) is None

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


# the other add_environment tests use a mock CondaManager, but we want to have
# one test that does the real thing to be sure it works.
def test_add_environment_with_real_conda_manager():
    def check(dirname):
        project = Project(dirname)
        status = project_ops.add_environment(project, name='foo', packages=['bokeh'], channels=['asmeurer'])
        assert status

        # be sure it was really done
        project2 = Project(dirname)
        env_commented_map = project2.project_file.get_value(['environments', 'foo'])
        assert dict(dependencies=['bokeh'], channels=['asmeurer']) == dict(env_commented_map)
        assert os.path.isdir(os.path.join(dirname, 'envs', 'foo', 'conda-meta'))

    with_directory_contents(dict(), check)


def _push_conda_test(fix_works, missing_packages, wrong_version_packages):
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

    push_conda_manager_class(TestCondaManager)


def _pop_conda_test():
    pop_conda_manager_class()


def _with_conda_test(f, fix_works=True, missing_packages=(), wrong_version_packages=()):
    try:
        _push_conda_test(fix_works, missing_packages, wrong_version_packages)
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
