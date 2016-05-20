# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------

import os

import anaconda_project.project_ops as project_ops
from anaconda_project.client import _upload, _Client
from anaconda_project.test.fake_server import fake_server
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents


def test_username(monkeypatch):
    with fake_server(monkeypatch):
        client = _Client(site='unit_test')
        username = client._username()
        assert username == 'fake_username'


def test_upload(monkeypatch):
    def check(dirname):
        with fake_server(monkeypatch):
            project = project_ops.create(dirname)
            bundlefile = os.path.join(dirname, "foo.zip")
            project_ops.bundle(project, bundlefile)

            status = _upload(project, bundlefile, site='unit_test')
            assert status

    with_directory_contents(dict(), check)


def test_upload_failing_auth(monkeypatch):
    def check(dirname):
        with fake_server(monkeypatch, fail_these=('auth', )):
            project = project_ops.create(dirname)
            bundlefile = os.path.join(dirname, "foo.zip")
            project_ops.bundle(project, bundlefile)

            status = _upload(project, bundlefile, site='unit_test')
            assert not status
            assert ['Not logged in.'] == status.errors

    with_directory_contents(dict(), check)


def test_upload_missing_login(monkeypatch):
    def check(dirname):
        with fake_server(monkeypatch, fail_these=('missing_login', )):
            project = project_ops.create(dirname)
            bundlefile = os.path.join(dirname, "foo.zip")
            project_ops.bundle(project, bundlefile)

            status = _upload(project, bundlefile, site='unit_test')
            assert not status
            assert ['Not logged in.'] == status.errors

    with_directory_contents(dict(), check)


def test_upload_failing_create(monkeypatch):
    def check(dirname):
        with fake_server(monkeypatch, fail_these=('create', )):
            project = project_ops.create(dirname)
            bundlefile = os.path.join(dirname, "foo.zip")
            project_ops.bundle(project, bundlefile)

            status = _upload(project, bundlefile, site='unit_test')
            assert not status
            assert '501' in status.errors[0]

    with_directory_contents(dict(), check)


def test_upload_failing_stage(monkeypatch):
    def check(dirname):
        with fake_server(monkeypatch, fail_these=('stage', )):
            project = project_ops.create(dirname)
            bundlefile = os.path.join(dirname, "foo.zip")
            project_ops.bundle(project, bundlefile)

            status = _upload(project, bundlefile, site='unit_test')
            assert not status
            assert '501' in status.errors[0]

    with_directory_contents(dict(), check)


def test_upload_failing_s3_upload(monkeypatch):
    def check(dirname):
        with fake_server(monkeypatch, fail_these=('s3', )):
            project = project_ops.create(dirname)
            bundlefile = os.path.join(dirname, "foo.zip")
            project_ops.bundle(project, bundlefile)

            status = _upload(project, bundlefile, site='unit_test')
            assert not status
            assert '501' in status.errors[0]

    with_directory_contents(dict(), check)


def test_upload_failing_commit(monkeypatch):
    def check(dirname):
        with fake_server(monkeypatch, fail_these=('commit', )):
            project = project_ops.create(dirname)
            bundlefile = os.path.join(dirname, "foo.zip")
            project_ops.bundle(project, bundlefile)

            status = _upload(project, bundlefile, site='unit_test')
            assert not status
            assert '501' in status.errors[0]

    with_directory_contents(dict(), check)
