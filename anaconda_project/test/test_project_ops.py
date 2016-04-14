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
        assert dict(foo=None, baz=None, preset=None) == re_loaded.get_value(['runtime'])
        local_state = LocalStateFile.load_for_directory(dirname)

        local_state.get_value(['runtime', 'foo']) == 'bar'
        local_state.get_value(['runtime', 'baz']) == 'qux'

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ('runtime:\n' '  preset: null')}, check_set_var)


def test_add_variables_existing_download():
    def check_set_var(dirname):
        project = project_no_dedicated_env(dirname)
        project_ops.add_variables(project, [('foo', 'bar'), ('baz', 'qux')])
        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        assert dict(foo=None, baz=None, preset=None) == re_loaded.get_value(['runtime'])
        assert re_loaded.get_value(['downloads', 'datafile']) == 'http://localhost:8000/data.tgz'
        local_state = LocalStateFile.load_for_directory(dirname)

        local_state.get_value(['variables', 'foo']) == 'bar'
        local_state.get_value(['variables', 'baz']) == 'qux'
        local_state.get_value(['variables', 'datafile']) == 'http://localhost:8000/data.tgz'

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('runtime:\n'
                                    '  preset: null\n'
                                    'downloads:\n'
                                    '  datafile: http://localhost:8000/data.tgz')}, check_set_var)

def test_add_variables_existing_options():
    def check_set_var(dirname):
        project = project_no_dedicated_env(dirname)
        project_ops.add_variables(project, [('foo', 'bar'), ('baz', 'qux')])
        re_loaded = ProjectFile.load_for_directory(project.directory_path)

        foo = re_loaded.get_value(['runtime', 'foo'])
        assert isinstance(foo, dict)
        assert 'something' in foo
        assert foo['something'] == 42

        baz = re_loaded.get_value(['runtime', 'baz'])
        assert isinstance(baz, dict)
        assert 'default' in baz
        assert baz['default'] == 'hello'

        woot = re_loaded.get_value(['runtime', 'woot'])
        assert woot == 'world'

        assert re_loaded.get_value(['downloads', 'datafile']) == 'http://localhost:8000/data.tgz'

        local_state = LocalStateFile.load_for_directory(dirname)

        local_state.get_value(['variables', 'foo']) == 'bar'
        local_state.get_value(['variables', 'baz']) == 'qux'
        local_state.get_value(['variables', 'datafile']) == 'http://localhost:8000/data.tgz'

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('runtime:\n'
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
        assert dict() == re_loaded.get_value(['runtime'])
        assert re_loaded.get_value(['runtime', 'foo']) is None
        assert re_loaded.get_value(['runtime', 'bar']) is None
        local_state = LocalStateFile.load_for_directory(dirname)

        local_state.get_value(['runtime', 'foo']) is None
        local_state.get_value(['runtime', 'bar']) is None

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ('runtime:\n' '  foo: baz\n  bar: qux')}, check_remove_var)


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

    with_directory_contents({DEFAULT_PROJECT_FILENAME: "runtime:\n  42"}, check)
