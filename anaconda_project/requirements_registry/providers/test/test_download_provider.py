# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import

import codecs
import os
import shutil
import zipfile

from anaconda_project.test.project_utils import project_no_dedicated_env
from anaconda_project.internal.test.tmpfile_utils import (with_directory_contents,
                                                          with_directory_contents_completing_project_file,
                                                          with_tmp_zipfile, complete_project_file_content)
from anaconda_project.test.environ_utils import minimal_environ
from anaconda_project.local_state_file import DEFAULT_LOCAL_STATE_FILENAME
from anaconda_project.local_state_file import LocalStateFile
from anaconda_project.requirements_registry.registry import RequirementsRegistry
from anaconda_project.requirements_registry.requirements.download import DownloadRequirement
from anaconda_project.prepare import (prepare_without_interaction, unprepare, prepare_in_stages)
from anaconda_project import provide
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME

from tornado import gen

DATAFILE_CONTENT = ("downloads:\n"
                    "    DATAFILE:\n"
                    "        url: http://localhost/data.csv\n"
                    "        md5: 12345abcdef\n"
                    "        filename: data.csv\n")

ZIPPED_DATAFILE_CONTENT = ("downloads:\n"
                           "    DATAFILE:\n"
                           "        url: http://localhost/data.zip\n"
                           "        filename: data\n")

ZIPPED_DATAFILE_CONTENT_CHECKSUM = (ZIPPED_DATAFILE_CONTENT + "        md5: 12345abcdef\n")

ZIPPED_DATAFILE_CONTENT_NO_UNZIP = (ZIPPED_DATAFILE_CONTENT + "        unzip: false\n")

# have to specify unzip:true manually here
ZIPPED_DATAFILE_CONTENT_NO_ZIP_SUFFIX = ("downloads:\n"
                                         "    DATAFILE:\n"
                                         "        url: http://localhost/data\n"
                                         "        unzip: true\n"
                                         "        filename: data\n")


def _download_requirement():
    return DownloadRequirement(registry=RequirementsRegistry(),
                               env_var="DATAFILE",
                               url='http://localhost/data.csv',
                               filename='data.csv')


def test_prepare_and_unprepare_download(monkeypatch):
    def provide_download(dirname):
        @gen.coroutine
        def mock_downloader_run(self):
            class Res:
                pass

            res = Res()
            res.code = 200
            with open(os.path.join(dirname, 'data.csv'), 'w') as out:
                out.write('data')
            self._hash = '12345abcdef'
            raise gen.Return(res)

        monkeypatch.setattr("anaconda_project.internal.http_client.FileDownloader.run", mock_downloader_run)
        project = project_no_dedicated_env(dirname)
        result = prepare_without_interaction(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert hasattr(result, 'environ')
        assert 'DATAFILE' in result.environ
        filename = os.path.join(dirname, 'data.csv')
        assert os.path.exists(filename)

        project.frontend.reset()
        status = unprepare(project, result)
        assert project.frontend.logs == [
            "Removed downloaded file %s." % filename,
            ("Current environment is not in %s, no need to delete it." % dirname)
        ]
        assert status.status_description == 'Success.'
        assert status
        assert not os.path.exists(filename)

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: DATAFILE_CONTENT}, provide_download)


def test_prepare_download_mismatched_checksum_after_download(monkeypatch):
    def provide_download(dirname):
        @gen.coroutine
        def mock_downloader_run(self):
            class Res:
                pass

            res = Res()
            res.code = 200
            with open(os.path.join(dirname, 'data.csv'), 'w') as out:
                out.write('data')
            self._hash = 'mismatched'
            raise gen.Return(res)

        monkeypatch.setattr("anaconda_project.internal.http_client.FileDownloader.run", mock_downloader_run)

        project = project_no_dedicated_env(dirname)
        result = prepare_without_interaction(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert not result
        assert ('Error downloading http://localhost/data.csv: mismatched hashes. '
                'Expected: 12345abcdef, calculated: mismatched') in result.errors

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: DATAFILE_CONTENT}, provide_download)


def test_prepare_download_exception(monkeypatch):
    def provide_download(dirname):
        @gen.coroutine
        def mock_downloader_run(self):
            raise Exception('error')

        monkeypatch.setattr("anaconda_project.internal.http_client.FileDownloader.run", mock_downloader_run)
        project = project_no_dedicated_env(dirname)
        result = prepare_without_interaction(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert not result
        assert ('missing requirement to run this project: A downloaded file which is referenced by DATAFILE.'
                ) in result.errors

        project.frontend.reset()
        status = unprepare(project, result)
        filename = os.path.join(dirname, 'data.csv')
        assert project.frontend.logs == [
            "No need to remove %s which wasn't downloaded." % filename,
            ("Current environment is not in %s, no need to delete it." % dirname)
        ]
        assert status.status_description == 'Success.'

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: DATAFILE_CONTENT}, provide_download)


def test_unprepare_download_fails(monkeypatch):
    def provide_download(dirname):
        @gen.coroutine
        def mock_downloader_run(self):
            class Res:
                pass

            res = Res()
            res.code = 200
            with open(os.path.join(dirname, 'data.csv'), 'w') as out:
                out.write('data')
            self._hash = '12345abcdef'
            raise gen.Return(res)

        monkeypatch.setattr("anaconda_project.internal.http_client.FileDownloader.run", mock_downloader_run)
        project = project_no_dedicated_env(dirname)
        result = prepare_without_interaction(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert hasattr(result, 'environ')
        assert 'DATAFILE' in result.environ
        filename = os.path.join(dirname, 'data.csv')
        assert os.path.exists(filename)

        def mock_remove(path):
            raise IOError("Not gonna remove this")

        monkeypatch.setattr("os.remove", mock_remove)

        project.frontend.reset()
        status = unprepare(project, result)
        assert project.frontend.logs == []
        assert status.status_description == ('Failed to remove %s: Not gonna remove this.' % filename)
        assert status.errors == []
        assert not status
        assert os.path.exists(filename)

        monkeypatch.undo()  # so os.remove isn't broken during directory cleanup

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: DATAFILE_CONTENT}, provide_download)


def test_provide_minimal(monkeypatch):
    MIN_DATAFILE_CONTENT = ("downloads:\n" "    DATAFILE: http://localhost/data.csv\n")

    def provide_download(dirname):
        @gen.coroutine
        def mock_downloader_run(self):
            class Res:
                pass

            res = Res()
            res.code = 200
            with open(os.path.join(dirname, 'data.csv'), 'w') as out:
                out.write('data')
            raise gen.Return(res)

        monkeypatch.setattr("anaconda_project.internal.http_client.FileDownloader.run", mock_downloader_run)
        project = project_no_dedicated_env(dirname)
        result = prepare_without_interaction(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert hasattr(result, 'environ')
        assert 'DATAFILE' in result.environ

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: MIN_DATAFILE_CONTENT}, provide_download)


def test_provide_no_download_in_check_mode(monkeypatch):
    MIN_DATAFILE_CONTENT = ("downloads:\n" "    DATAFILE: http://localhost/data.csv\n")

    def provide_download(dirname):
        @gen.coroutine
        def mock_downloader_run(self):
            raise Exception("should not have tried to download in check mode")

        monkeypatch.setattr("anaconda_project.internal.http_client.FileDownloader.run", mock_downloader_run)

        project = project_no_dedicated_env(dirname)
        result = prepare_without_interaction(project,
                                             environ=minimal_environ(PROJECT_DIR=dirname),
                                             mode=provide.PROVIDE_MODE_CHECK)
        assert not result

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: MIN_DATAFILE_CONTENT}, provide_download)


def test_provide_missing_url(monkeypatch):
    ERR_DATAFILE_CONTENT = ("downloads:\n" "    DATAFILE:\n" "       filename: data.csv\n")

    def provide_download(dirname):
        project = project_no_dedicated_env(dirname)
        prepare_without_interaction(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert "Download item DATAFILE doesn't contain a 'url' field." in project.problems

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ERR_DATAFILE_CONTENT}, provide_download)


def test_provide_empty_url(monkeypatch):
    ERR_DATAFILE_CONTENT = ("downloads:\n" "    DATAFILE:\n" "       url: \"\"\n")

    def provide_download(dirname):
        project = project_no_dedicated_env(dirname)
        prepare_without_interaction(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert "Download item DATAFILE has an empty 'url' field." in project.problems

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ERR_DATAFILE_CONTENT}, provide_download)


def test_provide_multiple_checksums(monkeypatch):
    ERR_DATAFILE_CONTENT = ("downloads:\n"
                            "    DATAFILE:\n"
                            "       url: http://localhost/\n"
                            "       md5: abcdefg\n"
                            "       sha1: abcdefg\n")

    def provide_download(dirname):
        project = project_no_dedicated_env(dirname)
        prepare_without_interaction(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert "Multiple checksums for download DATAFILE: md5 and sha1." in project.problems

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ERR_DATAFILE_CONTENT}, provide_download)


def test_provide_wrong_form(monkeypatch):
    ERR_DATAFILE_CONTENT = ("downloads:\n" "    - http://localhost/data.csv\n")

    def provide_download(dirname):
        project = project_no_dedicated_env(dirname)
        prepare_without_interaction(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert ("%s: 'downloads:' section should be a dictionary, found ['http://localhost/data.csv']" %
                DEFAULT_PROJECT_FILENAME) in project.problems

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ERR_DATAFILE_CONTENT}, provide_download)


def test_failed_download(monkeypatch):
    def provide_download(dirname):
        @gen.coroutine
        def mock_downloader_run(self):
            class Res:
                pass

            res = Res()
            res.code = 400
            raise gen.Return(res)

        monkeypatch.setattr("anaconda_project.internal.http_client.FileDownloader.run", mock_downloader_run)
        project = project_no_dedicated_env(dirname)
        result = prepare_without_interaction(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert not result
        assert ('missing requirement to run this project: A downloaded file which is referenced by DATAFILE.'
                ) in result.errors

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: DATAFILE_CONTENT}, provide_download)


def test_failed_download_before_connect(monkeypatch):
    def provide_download(dirname):
        @gen.coroutine
        def mock_downloader_run(self):
            # if we don't even get an HTTP response, the errors are handled this way,
            # e.g. if the URL is bad.
            self._errors = ['This went horribly wrong']
            raise gen.Return(None)

        monkeypatch.setattr("anaconda_project.internal.http_client.FileDownloader.run", mock_downloader_run)
        project = project_no_dedicated_env(dirname)
        result = prepare_without_interaction(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert not result
        assert ('missing requirement to run this project: A downloaded file which is referenced by DATAFILE.'
                ) in result.errors

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: DATAFILE_CONTENT}, provide_download)


def test_file_exists(monkeypatch):
    def provide_download(dirname):
        FILENAME = os.path.join(dirname, 'data.csv')
        requirement = _download_requirement()
        local_state_file = LocalStateFile.load_for_directory(dirname)
        local_state_file.set_service_run_state(requirement.env_var, {'filename': FILENAME})
        local_state_file.save()
        with open(FILENAME, 'w') as out:
            out.write('data')
        project = project_no_dedicated_env(dirname)

        result = prepare_without_interaction(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert hasattr(result, 'environ')
        assert 'DATAFILE' in result.environ

    LOCAL_STATE = ("DATAFILE:\n" "  filename: data.csv")

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: DATAFILE_CONTENT,
            DEFAULT_LOCAL_STATE_FILENAME: LOCAL_STATE
        }, provide_download)


def test_prepare_download_of_zip_file(monkeypatch):
    def provide_download_of_zip(zipname, dirname):
        with codecs.open(os.path.join(dirname, DEFAULT_PROJECT_FILENAME), 'w', 'utf-8') as f:
            f.write(complete_project_file_content(ZIPPED_DATAFILE_CONTENT))

        @gen.coroutine
        def mock_downloader_run(self):
            class Res:
                pass

            res = Res()
            res.code = 200
            assert self._url.endswith(".zip")
            assert self._filename.endswith(".zip")
            shutil.copyfile(zipname, self._filename)
            raise gen.Return(res)

        monkeypatch.setattr("anaconda_project.internal.http_client.FileDownloader.run", mock_downloader_run)

        project = project_no_dedicated_env(dirname)

        result = prepare_without_interaction(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert hasattr(result, 'environ')
        assert 'DATAFILE' in result.environ
        assert os.path.isdir(os.path.join(dirname, 'data'))
        assert os.path.isfile(os.path.join(dirname, 'data', 'foo'))
        assert codecs.open(os.path.join(dirname, 'data', 'foo')).read() == 'hello\n'

    with_tmp_zipfile(dict(foo='hello\n'), provide_download_of_zip)


def test_prepare_download_of_zip_file_checksum(monkeypatch):
    def provide_download_of_zip(zipname, dirname):
        with codecs.open(os.path.join(dirname, DEFAULT_PROJECT_FILENAME), 'w', 'utf-8') as f:
            f.write(complete_project_file_content(ZIPPED_DATAFILE_CONTENT_CHECKSUM))

        @gen.coroutine
        def mock_downloader_run(self):
            class Res:
                pass

            res = Res()
            res.code = 200
            assert self._url.endswith(".zip")
            assert self._filename.endswith(".zip")
            shutil.copyfile(zipname, self._filename)
            self._hash = '12345abcdef'
            raise gen.Return(res)

        monkeypatch.setattr("anaconda_project.internal.http_client.FileDownloader.run", mock_downloader_run)
        project = project_no_dedicated_env(dirname)

        result = prepare_without_interaction(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert hasattr(result, 'environ')
        assert 'DATAFILE' in result.environ
        assert os.path.isdir(os.path.join(dirname, 'data'))
        assert os.path.isfile(os.path.join(dirname, 'data', 'foo'))
        assert codecs.open(os.path.join(dirname, 'data', 'foo')).read() == 'hello\n'

        project.frontend.reset()
        status = unprepare(project, result)
        filename = os.path.join(dirname, 'data')
        assert project.frontend.logs == [
            "Removed downloaded file %s." % filename,
            ("Current environment is not in %s, no need to delete it." % dirname)
        ]
        assert status.status_description == "Success."

    with_tmp_zipfile(dict(foo='hello\n'), provide_download_of_zip)


def test_prepare_download_of_zip_file_no_unzip(monkeypatch):
    def provide_download_of_zip_no_unzip(zipname, dirname):
        with codecs.open(os.path.join(dirname, DEFAULT_PROJECT_FILENAME), 'w', 'utf-8') as f:
            f.write(complete_project_file_content(ZIPPED_DATAFILE_CONTENT_NO_UNZIP))

        @gen.coroutine
        def mock_downloader_run(self):
            class Res:
                pass

            res = Res()
            res.code = 200
            assert self._url.endswith(".zip")
            # we aren't going to unzip so we should be downloading straignt to
            # the specified filename 'data' without the .zip on it
            assert not self._filename.endswith(".zip")
            shutil.copyfile(zipname, self._filename)
            raise gen.Return(res)

        monkeypatch.setattr("anaconda_project.internal.http_client.FileDownloader.run", mock_downloader_run)

        project = project_no_dedicated_env(dirname)

        result = prepare_without_interaction(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert hasattr(result, 'environ')
        assert 'DATAFILE' in result.environ
        assert os.path.isfile(os.path.join(dirname, 'data'))
        with zipfile.ZipFile(os.path.join(dirname, 'data')) as zf:
            assert zf.namelist() == ['foo']

    with_tmp_zipfile(dict(foo='hello\n'), provide_download_of_zip_no_unzip)


def test_prepare_download_of_zip_file_no_zip_extension(monkeypatch):
    def provide_download_of_zip(zipname, dirname):
        with codecs.open(os.path.join(dirname, DEFAULT_PROJECT_FILENAME), 'w', 'utf-8') as f:
            f.write(complete_project_file_content(ZIPPED_DATAFILE_CONTENT_NO_ZIP_SUFFIX))

        @gen.coroutine
        def mock_downloader_run(self):
            class Res:
                pass

            res = Res()
            res.code = 200
            # we add .zip to the download filename, even though it wasn't in the URL
            assert not self._url.endswith(".zip")
            assert self._filename.endswith(".zip")
            shutil.copyfile(zipname, self._filename)
            raise gen.Return(res)

        monkeypatch.setattr("anaconda_project.internal.http_client.FileDownloader.run", mock_downloader_run)

        project = project_no_dedicated_env(dirname)

        result = prepare_without_interaction(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert hasattr(result, 'environ')
        assert 'DATAFILE' in result.environ
        assert os.path.isdir(os.path.join(dirname, 'data'))
        assert os.path.isfile(os.path.join(dirname, 'data', 'foo'))
        assert codecs.open(os.path.join(dirname, 'data', 'foo')).read() == 'hello\n'

    with_tmp_zipfile(dict(foo='hello\n'), provide_download_of_zip)


def test_prepare_download_of_broken_zip_file(monkeypatch):
    def provide_download_of_zip(dirname):
        with codecs.open(os.path.join(dirname, DEFAULT_PROJECT_FILENAME), 'w', 'utf-8') as f:
            f.write(complete_project_file_content(ZIPPED_DATAFILE_CONTENT))

        @gen.coroutine
        def mock_downloader_run(self):
            class Res:
                pass

            res = Res()
            res.code = 200
            assert self._url.endswith(".zip")
            assert self._filename.endswith(".zip")
            with codecs.open(self._filename, 'w', 'utf-8') as f:
                f.write("This is not a zip file.")
            raise gen.Return(res)

        monkeypatch.setattr("anaconda_project.internal.http_client.FileDownloader.run", mock_downloader_run)

        project = project_no_dedicated_env(dirname)

        result = prepare_without_interaction(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert not result
        assert [("Failed to unzip %s: File is not a zip file" % os.path.join(dirname, "data.zip")),
                "missing requirement to run this project: A downloaded file which is referenced by DATAFILE.",
                "  Environment variable DATAFILE is not set."] == result.errors

    with_directory_contents(dict(), provide_download_of_zip)


def _download_status(prepare_context):
    for status in prepare_context.statuses:
        if isinstance(status.requirement, DownloadRequirement):
            return status
    return None


def test_configure(monkeypatch):
    def check(dirname):
        @gen.coroutine
        def mock_downloader_run(self):
            class Res:
                pass

            res = Res()
            res.code = 200
            with open(os.path.join(dirname, 'data.csv'), 'w') as out:
                out.write('data')
            self._hash = '12345abcdef'
            raise gen.Return(res)

        monkeypatch.setattr("anaconda_project.internal.http_client.FileDownloader.run", mock_downloader_run)

        project = project_no_dedicated_env(dirname)
        environ = minimal_environ(PROJECT_DIR=dirname)
        stage = prepare_in_stages(project, environ=environ)
        status = None
        while status is None and stage is not None:
            prepare_context = stage.configure()
            status = _download_status(prepare_context)
            if status is None:
                stage = stage.execute()

        assert status is not None

        req = status.requirement
        provider = status.provider

        # check initial config

        config = provider.read_config(req, prepare_context.environ, prepare_context.local_state_file,
                                      prepare_context.default_env_spec_name, prepare_context.overrides)

        assert dict(source='download') == config

        config['source'] = 'environ'
        config['value'] = 'abc.txt'

        provider.set_config_values_as_strings(req, prepare_context.environ, prepare_context.local_state_file,
                                              prepare_context.default_env_spec_name, prepare_context.overrides, config)

        config = provider.read_config(req, prepare_context.environ, prepare_context.local_state_file,
                                      prepare_context.default_env_spec_name, prepare_context.overrides)

        assert dict(source='download', value='abc.txt') == config

        config['source'] = 'variables'
        config['value'] = 'qrs.txt'
        provider.set_config_values_as_strings(req, prepare_context.environ, prepare_context.local_state_file,
                                              prepare_context.default_env_spec_name, prepare_context.overrides, config)

        config = provider.read_config(req, prepare_context.environ, prepare_context.local_state_file,
                                      prepare_context.default_env_spec_name, prepare_context.overrides)

        assert dict(source='variables', value='qrs.txt') == config

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
downloads:
  FOO: http://example.com/data.csv
    """}, check)
