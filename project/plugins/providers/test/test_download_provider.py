from __future__ import absolute_import
import os

from project.test.project_utils import project_no_dedicated_env
from project.internal.test.tmpfile_utils import with_directory_contents
from project.test.environ_utils import minimal_environ
from project.local_state_file import DEFAULT_RELATIVE_LOCAL_STATE_PATH
from project.local_state_file import LocalStateFile
from project.plugins.registry import PluginRegistry
from project.plugins.provider import ProviderConfigContext
from project.plugins.providers.download import DownloadProvider
from project.plugins.requirements.download import DownloadRequirement
from project.prepare import prepare
from project.project_file import DEFAULT_PROJECT_FILENAME

DATAFILE_CONTENT = ("downloads:\n"
                    "    DATAFILE:\n"
                    "        url: http://localhost/data.zip\n"
                    "        md5: 12345abcdef\n"
                    "        filename: data.zip\n")


def _download_requirement():
    return DownloadRequirement(registry=PluginRegistry(),
                               env_var="DATAFILE",
                               url='http://localhost/data.zip',
                               filename='data.zip')


def test_reading_valid_config():
    def read_config(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        requirement = _download_requirement()
        provider = DownloadProvider()
        config = provider.read_config(ProviderConfigContext(dict(), local_state, requirement))
        assert config['url'] == 'http://localhost/data.zip'
        assert config['hash_value'] == '12345abcdef'
        assert config['hash_algorithm'] == 'md5'
        assert config['filename'] == 'data.zip'

    with_directory_contents({DEFAULT_RELATIVE_LOCAL_STATE_PATH: DATAFILE_CONTENT}, read_config)


def test_reading_explicit_hash():
    def read_config(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        requirement = _download_requirement()
        provider = DownloadProvider()
        config = provider.read_config(ProviderConfigContext(dict(), local_state, requirement))
        assert config['url'] == 'http://localhost/data.zip'
        assert config['hash_value'] == '12345abcdef'
        assert config['hash_algorithm'] == 'md5'
        assert config['filename'] == 'data.zip'

    DATAFILE_CONTENT = ("downloads:\n"
                        "    DATAFILE:\n"
                        "        url: http://localhost/data.zip\n"
                        "        hash_value: 12345abcdef\n"
                        "        hash_algorithm: md5\n"
                        "        filename: data.zip\n")

    with_directory_contents({DEFAULT_RELATIVE_LOCAL_STATE_PATH: DATAFILE_CONTENT}, read_config)


def test_set_config_values_as_strings():
    def set_config(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        requirement = _download_requirement()
        provider = DownloadProvider()
        config = {
            'url': 'http://localhost/data.zip',
            'hash_value': '12345abcdef',
            'hash_algorithm': 'md5',
            'filename': 'data.zip'
        }
        provider.set_config_values_as_strings(ProviderConfigContext(dict(), local_state, requirement), config)
        config = provider.read_config(ProviderConfigContext(dict(), local_state, requirement))
        assert config['url'] == 'http://localhost/data.zip'
        assert config['hash_value'] == '12345abcdef'
        assert config['hash_algorithm'] == 'md5'
        assert config['filename'] == 'data.zip'

    with_directory_contents(dict(), set_config)


def test_prepare_download(monkeypatch):
    def provide_download(dirname):
        from tornado import gen

        @gen.coroutine
        def mock_downloader_run(self, loop):
            class Res:
                pass

            res = Res()
            res.code = 200
            with open(os.path.join(dirname, 'data.zip'), 'w') as out:
                out.write('data')
            raise gen.Return(res)

        def mock_checksum(self, fp):
            return True

        monkeypatch.setattr("project.internal.http_client.FileDownloader.run", mock_downloader_run)
        monkeypatch.setattr("project.plugins.requirements.download.DownloadRequirement._checksum", mock_checksum)
        project = project_no_dedicated_env(dirname)
        result = prepare(project, environ=minimal_environ())
        assert hasattr(result, 'environ')
        assert 'DATAFILE' in result.environ

    with_directory_contents({DEFAULT_PROJECT_FILENAME: DATAFILE_CONTENT}, provide_download)


def test_prepare_download_exception(monkeypatch):
    def provide_download(dirname):
        from tornado import gen

        @gen.coroutine
        def mock_downloader_run(self, loop):
            raise Exception('error')

        monkeypatch.setattr("project.internal.http_client.FileDownloader.run", mock_downloader_run)
        project = project_no_dedicated_env(dirname)
        result = prepare(project, environ=minimal_environ())
        assert not result
        assert ('missing requirement to run this project: '
                'A downloaded file which is referenced by DATAFILE') in result.errors

    with_directory_contents({DEFAULT_PROJECT_FILENAME: DATAFILE_CONTENT}, provide_download)


def test_provide_minimal(monkeypatch):
    MIN_DATAFILE_CONTENT = ("downloads:\n" "    DATAFILE: http://localhost/data.zip\n")

    def provide_download(dirname):
        from tornado import gen

        @gen.coroutine
        def mock_downloader_run(self, loop):
            class Res:
                pass

            res = Res()
            res.code = 200
            with open(os.path.join(dirname, 'data.zip'), 'w') as out:
                out.write('data')
            raise gen.Return(res)

        def mock_checksum(self, fp):
            return True

        monkeypatch.setattr("project.internal.http_client.FileDownloader.run", mock_downloader_run)
        monkeypatch.setattr("project.plugins.requirements.download.DownloadRequirement._checksum", mock_checksum)
        project = project_no_dedicated_env(dirname)
        result = prepare(project, environ=minimal_environ())
        assert hasattr(result, 'environ')
        assert 'DATAFILE' in result.environ

    with_directory_contents({DEFAULT_PROJECT_FILENAME: MIN_DATAFILE_CONTENT}, provide_download)


def test_provide_missing_url(monkeypatch):
    ERR_DATAFILE_CONTENT = ("downloads:\n" "    DATAFILE:\n" "       filename: data.zip\n")

    def provide_download(dirname):
        project = project_no_dedicated_env(dirname)
        prepare(project, environ=minimal_environ())
        assert "Download item DATAFILE doesn't contain a 'url' field." in project.problems

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ERR_DATAFILE_CONTENT}, provide_download)


def test_provide_empty_url(monkeypatch):
    ERR_DATAFILE_CONTENT = ("downloads:\n" "    DATAFILE:\n" "       url: \"\"\n")

    def provide_download(dirname):
        project = project_no_dedicated_env(dirname)
        prepare(project, environ=minimal_environ())
        assert "Download item DATAFILE has an empty 'url' field." in project.problems

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ERR_DATAFILE_CONTENT}, provide_download)


def test_provide_multiple_checksums(monkeypatch):
    ERR_DATAFILE_CONTENT = ("downloads:\n"
                            "    DATAFILE:\n"
                            "       url: http://localhost/\n"
                            "       md5: abcdefg\n"
                            "       sha1: abcdefg\n")

    def provide_download(dirname):
        project = project_no_dedicated_env(dirname)
        prepare(project, environ=minimal_environ())
        assert "Multiple checksums for download DATAFILE: md5 and sha1." in project.problems

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ERR_DATAFILE_CONTENT}, provide_download)


def test_provide_wrong_form(monkeypatch):
    ERR_DATAFILE_CONTENT = ("downloads:\n" "    - http://localhost/data.zip\n")

    def provide_download(dirname):
        project = project_no_dedicated_env(dirname)
        prepare(project, environ=minimal_environ())
        assert "'downloads:' section should be a dictionary, found ['http://localhost/data.zip']" in project.problems

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ERR_DATAFILE_CONTENT}, provide_download)


def test_failed_download(monkeypatch):
    def provide_download(dirname):
        from tornado import gen

        @gen.coroutine
        def mock_downloader_run(self, loop):
            class Res:
                pass

            res = Res()
            res.code = 400
            raise gen.Return(res)

        monkeypatch.setattr("project.internal.http_client.FileDownloader.run", mock_downloader_run)
        project = project_no_dedicated_env(dirname)
        result = prepare(project, environ=minimal_environ())
        assert not result
        assert ('missing requirement to run this project: '
                'A downloaded file which is referenced by DATAFILE') in result.errors

    with_directory_contents({DEFAULT_PROJECT_FILENAME: DATAFILE_CONTENT}, provide_download)


def test_file_exists(monkeypatch):
    def provide_download(dirname):
        FILENAME = os.path.join(dirname, 'data.zip')
        requirement = _download_requirement()
        local_state_file = LocalStateFile.load_for_directory(dirname)
        local_state_file.set_service_run_state(requirement.env_var, {'filename': FILENAME})
        local_state_file.save()
        with open(FILENAME, 'w') as out:
            out.write('data')
        project = project_no_dedicated_env(dirname)

        def mock_checksum(self, fp):
            return True

        monkeypatch.setattr("project.plugins.requirements.download.DownloadRequirement._checksum", mock_checksum)
        result = prepare(project, environ=minimal_environ())
        assert hasattr(result, 'environ')
        assert 'DATAFILE' in result.environ

    LOCAL_STATE = ("DATAFILE:\n" "  filename: data.zip")

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME: DATAFILE_CONTENT,
            DEFAULT_RELATIVE_LOCAL_STATE_PATH: LOCAL_STATE
        }, provide_download)


def test_config_html(monkeypatch):
    def config_html(dirname):
        FILENAME = os.path.join(dirname, 'data.zip')
        local_state_file = LocalStateFile.load_for_directory(dirname)
        requirement = _download_requirement()
        status = requirement.check_status(minimal_environ(), local_state_file)
        config_context = ProviderConfigContext(minimal_environ(), local_state_file, requirement)
        provider = DownloadProvider()
        html = provider.config_html(config_context, status)
        assert 'name="url"' in html
        assert 'name="filename"' in html
        assert 'name="hash_algorithm"' in html
        assert 'name="hash_value"' in html

        def mock_why_not_provided(self, env):
            return

        def mock_previous_file_state(self, fs):
            return FILENAME

        monkeypatch.setattr("project.plugins.requirements.download.DownloadRequirement._why_not_provided",
                            mock_why_not_provided)
        monkeypatch.setattr("project.plugins.providers.download.DownloadProvider._previous_file_state",
                            mock_previous_file_state)
        local_state_file.set_service_run_state(requirement.env_var, {'filename': FILENAME})
        local_state_file.save()
        env = minimal_environ()
        env['DATAFILE'] = FILENAME
        status = requirement.check_status(env, local_state_file)
        config_context = ProviderConfigContext(env, local_state_file, requirement)
        html = provider.config_html(config_context, status)
        assert '<form>Previously downloaded file located at {}</form>'.format(FILENAME) in html

    with_directory_contents({DEFAULT_RELATIVE_LOCAL_STATE_PATH: DATAFILE_CONTENT}, config_html)
