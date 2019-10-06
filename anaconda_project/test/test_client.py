# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import os

import anaconda_project.project_ops as project_ops
from anaconda_project.client import _upload, _Client, _download
from anaconda_project.test.fake_server import fake_server
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents


def test_username(monkeypatch):
    with fake_server(monkeypatch):
        client = _Client(site='unit_test')
        username = client._username()
        assert username == 'fake_username'


def test_username_override(monkeypatch):
    with fake_server(monkeypatch):
        client = _Client(site='unit_test', username='foobar')
        username = client._username()
        assert username == 'foobar'


def test_specify_token_and_log_level(monkeypatch):
    import logging
    client = _Client(token='134', log_level=logging.ERROR)
    assert client._api.token == '134'


def test_upload(monkeypatch):
    def check(dirname):
        with fake_server(monkeypatch, expected_basename='foo.zip'):
            project = project_ops.create(dirname)
            archivefile = os.path.join(dirname, "tmp.zip")
            project_ops.archive(project, archivefile)

            status = _upload(project, archivefile, "foo.zip", site='unit_test')
            assert status

    with_directory_contents(dict(), check)


def test_upload_failing_auth(monkeypatch):
    def check(dirname):
        with fake_server(monkeypatch, expected_basename='foo.zip', fail_these=('auth', )):
            project = project_ops.create(dirname)
            archivefile = os.path.join(dirname, "tmp.zip")
            project_ops.archive(project, archivefile)

            status = _upload(project, archivefile, "foo.zip", site='unit_test')
            assert not status
            assert ['Not logged in.'] == status.errors

    with_directory_contents(dict(), check)


def test_upload_missing_login(monkeypatch):
    def check(dirname):
        with fake_server(monkeypatch, expected_basename='foo.zip', fail_these=('missing_login', )):
            project = project_ops.create(dirname)
            archivefile = os.path.join(dirname, "tmp.zip")
            project_ops.archive(project, archivefile)

            status = _upload(project, archivefile, "foo.zip", site='unit_test')
            assert not status
            assert ['Not logged in.'] == status.errors

    with_directory_contents(dict(), check)


def test_upload_failing_create(monkeypatch):
    def check(dirname):
        with fake_server(monkeypatch, expected_basename='foo.zip', fail_these=('create', )):
            project = project_ops.create(dirname)
            archivefile = os.path.join(dirname, "tmp.zip")
            project_ops.archive(project, archivefile)

            status = _upload(project, archivefile, "foo.zip", site='unit_test')
            assert not status
            assert '501' in status.errors[0]

    with_directory_contents(dict(), check)


def test_upload_failing_stage(monkeypatch):
    def check(dirname):
        with fake_server(monkeypatch, expected_basename='foo.zip', fail_these=('stage', )):
            project = project_ops.create(dirname)
            archivefile = os.path.join(dirname, "tmp.zip")
            project_ops.archive(project, archivefile)

            status = _upload(project, archivefile, "foo.zip", site='unit_test')
            assert not status
            assert '501' in status.errors[0]

    with_directory_contents(dict(), check)


def test_upload_failing_s3_upload(monkeypatch):
    def check(dirname):
        with fake_server(monkeypatch, expected_basename='foo.zip', fail_these=('s3', )):
            project = project_ops.create(dirname)
            archivefile = os.path.join(dirname, "tmp.zip")
            project_ops.archive(project, archivefile)

            status = _upload(project, archivefile, "foo.zip", site='unit_test')
            assert not status
            assert '501' in status.errors[0]

    with_directory_contents(dict(), check)


def test_upload_failing_commit(monkeypatch):
    def check(dirname):
        with fake_server(monkeypatch, expected_basename='foo.zip', fail_these=('commit', )):
            project = project_ops.create(dirname)
            archivefile = os.path.join(dirname, "tmp.zip")
            project_ops.archive(project, archivefile)

            status = _upload(project, archivefile, "foo.zip", site='unit_test')
            assert not status
            assert '501' in status.errors[0]

    with_directory_contents(dict(), check)


def test_download(monkeypatch):
    def check(dirname):
        with fake_server(monkeypatch, expected_basename='fake_project.zip'):
            status = _download('fake_username/fake_project', site='unit_test')
            assert status

    with_directory_contents(dict(), check)


def test_download_no_username(monkeypatch):
    def check(dirname):
        with fake_server(monkeypatch, expected_basename='fake_project.zip'):
            status = _download('fake_project', site='unit_test')
            assert status

    with_directory_contents(dict(), check)


def test_download_missing(monkeypatch):
    def check(dirname):
        with fake_server(monkeypatch, expected_basename='fake_project.zip'):
            status = _download('fake_username/missing_project', site='unit_test')
            assert '404' in status.errors[0]

    with_directory_contents(dict(), check)


def test_download_missing_no_username(monkeypatch):
    def check(dirname):
        with fake_server(monkeypatch, expected_basename='fake_project.zip'):
            status = _download('missing_project', site='unit_test')
            assert '404' in status.errors[0]

    with_directory_contents(dict(), check)
