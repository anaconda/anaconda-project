from __future__ import absolute_import

import os

from project.test.project_utils import project_no_dedicated_env
from project.internal.test.tmpfile_utils import with_directory_contents
from project.test.environ_utils import minimal_environ, strip_environ
from project.internal.test.http_utils import http_get_async, http_post_async
from project.local_state_file import DEFAULT_RELATIVE_LOCAL_STATE_PATH
from project.local_state_file import LocalStateFile
from project.plugins.registry import PluginRegistry
from project.plugins.provider import ProviderConfigContext
from project.plugins.providers.download import DownloadProvider
from project.plugins.requirements.download import DownloadRequirement
from project.prepare import prepare, UI_MODE_BROWSER
from project.project_file import DEFAULT_PROJECT_FILENAME

from tornado import gen

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


def test_prepare_download(monkeypatch):
    def provide_download(dirname):
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
            return None

        monkeypatch.setattr("project.internal.http_client.FileDownloader.run", mock_downloader_run)
        monkeypatch.setattr("project.plugins.requirements.download.DownloadRequirement._checksum_error_or_none",
                            mock_checksum)
        project = project_no_dedicated_env(dirname)
        result = prepare(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert hasattr(result, 'environ')
        assert 'DATAFILE' in result.environ

    with_directory_contents({DEFAULT_PROJECT_FILENAME: DATAFILE_CONTENT}, provide_download)


def test_prepare_download_exception(monkeypatch):
    def provide_download(dirname):
        @gen.coroutine
        def mock_downloader_run(self, loop):
            raise Exception('error')

        monkeypatch.setattr("project.internal.http_client.FileDownloader.run", mock_downloader_run)
        project = project_no_dedicated_env(dirname)
        result = prepare(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert not result
        assert ('missing requirement to run this project: '
                'A downloaded file which is referenced by DATAFILE') in result.errors

    with_directory_contents({DEFAULT_PROJECT_FILENAME: DATAFILE_CONTENT}, provide_download)


def test_provide_minimal(monkeypatch):
    MIN_DATAFILE_CONTENT = ("downloads:\n" "    DATAFILE: http://localhost/data.zip\n")

    def provide_download(dirname):
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
            return None

        monkeypatch.setattr("project.internal.http_client.FileDownloader.run", mock_downloader_run)
        monkeypatch.setattr("project.plugins.requirements.download.DownloadRequirement._checksum_error_or_none",
                            mock_checksum)
        project = project_no_dedicated_env(dirname)
        result = prepare(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert hasattr(result, 'environ')
        assert 'DATAFILE' in result.environ

    with_directory_contents({DEFAULT_PROJECT_FILENAME: MIN_DATAFILE_CONTENT}, provide_download)


def test_provide_missing_url(monkeypatch):
    ERR_DATAFILE_CONTENT = ("downloads:\n" "    DATAFILE:\n" "       filename: data.zip\n")

    def provide_download(dirname):
        project = project_no_dedicated_env(dirname)
        prepare(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert "Download item DATAFILE doesn't contain a 'url' field." in project.problems

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ERR_DATAFILE_CONTENT}, provide_download)


def test_provide_empty_url(monkeypatch):
    ERR_DATAFILE_CONTENT = ("downloads:\n" "    DATAFILE:\n" "       url: \"\"\n")

    def provide_download(dirname):
        project = project_no_dedicated_env(dirname)
        prepare(project, environ=minimal_environ(PROJECT_DIR=dirname))
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
        prepare(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert "Multiple checksums for download DATAFILE: md5 and sha1." in project.problems

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ERR_DATAFILE_CONTENT}, provide_download)


def test_provide_wrong_form(monkeypatch):
    ERR_DATAFILE_CONTENT = ("downloads:\n" "    - http://localhost/data.zip\n")

    def provide_download(dirname):
        project = project_no_dedicated_env(dirname)
        prepare(project, environ=minimal_environ(PROJECT_DIR=dirname))
        assert "'downloads:' section should be a dictionary, found ['http://localhost/data.zip']" in project.problems

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ERR_DATAFILE_CONTENT}, provide_download)


def test_failed_download(monkeypatch):
    def provide_download(dirname):
        @gen.coroutine
        def mock_downloader_run(self, loop):
            class Res:
                pass

            res = Res()
            res.code = 400
            raise gen.Return(res)

        monkeypatch.setattr("project.internal.http_client.FileDownloader.run", mock_downloader_run)
        project = project_no_dedicated_env(dirname)
        result = prepare(project, environ=minimal_environ(PROJECT_DIR=dirname))
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
            return None

        monkeypatch.setattr("project.plugins.requirements.download.DownloadRequirement._checksum_error_or_none",
                            mock_checksum)
        result = prepare(project, environ=minimal_environ(PROJECT_DIR=dirname))
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
        status = requirement.check_status(minimal_environ(PROJECT_DIR=dirname), local_state_file)
        config_context = ProviderConfigContext(minimal_environ(PROJECT_DIR=dirname), local_state_file, requirement)
        provider = DownloadProvider()
        html = provider.config_html(config_context, status)
        assert 'Download {} to {}'.format(requirement.url, requirement.filename) in html

        with open(FILENAME, 'w') as f:
            f.write('boo')

        env = minimal_environ(PROJECT_DIR=dirname)
        status = requirement.check_status(env, local_state_file)
        config_context = ProviderConfigContext(env, local_state_file, requirement)
        html = provider.config_html(config_context, status)
        expected_choice = 'Use already-downloaded file {}'.format(FILENAME)
        assert expected_choice in html

    with_directory_contents({DEFAULT_RELATIVE_LOCAL_STATE_PATH: DATAFILE_CONTENT}, config_html)


def _run_browser_ui_test(monkeypatch, directory_contents, initial_environ, http_actions, final_result_check):
    @gen.coroutine
    def mock_downloader_run(self, loop):
        class Res:
            pass

        res = Res()
        if self._url.endswith("?error=true"):
            res.code = 400
        else:
            with open(self._filename, 'w') as f:
                f.write("boo")

            res.code = 200
        raise gen.Return(res)

    monkeypatch.setattr("project.internal.http_client.FileDownloader.run", mock_downloader_run)

    replaced = dict()
    for key, value in directory_contents.items():
        replaced[key] = value.format(url="http://example.com/bar", error_url="http://example.com/bar?error=true")
    directory_contents = replaced

    from tornado.ioloop import IOLoop
    io_loop = IOLoop(make_current=False)

    http_done = dict()

    def mock_open_new_tab(url):
        @gen.coroutine
        def do_http():
            try:
                for action in http_actions:
                    yield action(url)
            except Exception as e:
                http_done['exception'] = e

            http_done['done'] = True

            io_loop.stop()
            io_loop.close()

        io_loop.add_callback(do_http)

    monkeypatch.setattr('webbrowser.open_new_tab', mock_open_new_tab)

    def do_browser_ui_test(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        if not isinstance(initial_environ, dict):
            environ = initial_environ(dirname)
        else:
            environ = initial_environ
        result = prepare(project,
                         environ=environ,
                         io_loop=io_loop,
                         ui_mode=UI_MODE_BROWSER,
                         keep_going_until_success=True)

        # finish up the last http action if prepare_ui.py stopped the loop before we did
        while 'done' not in http_done:
            io_loop.call_later(0.01, lambda: io_loop.stop())
            io_loop.start()

        if 'exception' in http_done:
            raise http_done['exception']

        final_result_check(dirname, result)

    with_directory_contents(directory_contents, do_browser_ui_test)


def _extract_radio_items(response):
    from project.internal.plugin_html import _BEAUTIFUL_SOUP_BACKEND
    from bs4 import BeautifulSoup

    if response.code != 200:
        raise Exception("got a bad http response " + repr(response))

    soup = BeautifulSoup(response.body, _BEAUTIFUL_SOUP_BACKEND)
    radios = soup.find_all("input", attrs={'type': 'radio'})
    return [r for r in radios if ('DownloadProvider' in r['name'])]


def _form_names(response):
    from project.internal.plugin_html import _BEAUTIFUL_SOUP_BACKEND
    from bs4 import BeautifulSoup

    if response.code != 200:
        raise Exception("got a bad http response " + repr(response))

    soup = BeautifulSoup(response.body, _BEAUTIFUL_SOUP_BACKEND)
    named_elements = soup.find_all(attrs={'name': True})
    names = set()
    for element in named_elements:
        if 'DownloadProvider' in element['name']:
            names.add(element['name'])
    return names


def _prefix_form(form_names, form):
    prefixed = dict()
    for (key, value) in form.items():
        found = False
        for name in form_names:
            if name.endswith("." + key):
                prefixed[name] = value
                found = True
                break
        if not found:
            raise RuntimeError("Form field %s in %r could not be prefixed from %r" % (name, form, form_names))
    return prefixed


def _verify_choices(response, expected):
    name = None
    radios = _extract_radio_items(response)
    actual = []
    for r in radios:
        actual.append((r['value'], 'checked' in r.attrs))
    assert expected == tuple(actual)
    return name


def test_browser_ui_with_no_env_var_set(monkeypatch):
    directory_contents = {DEFAULT_PROJECT_FILENAME: """
downloads:
  MYDOWNLOAD:
    url: {url}
    """}
    initial_environ = minimal_environ()

    @gen.coroutine
    def get_initial(url):
        response = yield http_get_async(url)
        assert response.code == 200
        body = response.body.decode('utf-8')
        assert "Download {} to {}".format('http://example.com/bar', 'bar') in body
        _verify_choices(response,
                        (
                            # by default, perform the download
                            ('download', True),
                            # allow typing in a manual value
                            ('variables', False)))

    @gen.coroutine
    def post_empty_form(url):
        response = yield http_post_async(url, body='')
        assert response.code == 200
        body = response.body.decode('utf-8')
        assert "Done!" in body
        assert "File downloaded to " in body
        _verify_choices(response, ())

    def final_result_check(dirname, result):
        assert result
        expected = dict(MYDOWNLOAD=os.path.join(dirname, 'bar'), PROJECT_DIR=dirname)
        assert expected == strip_environ(result.environ)

    _run_browser_ui_test(monkeypatch=monkeypatch,
                         directory_contents=directory_contents,
                         initial_environ=initial_environ,
                         http_actions=[get_initial, post_empty_form],
                         final_result_check=final_result_check)


def test_browser_ui_with_env_var_already_set(monkeypatch):
    directory_contents = {DEFAULT_PROJECT_FILENAME: """
downloads:
  MYDOWNLOAD:
    url: {url}
    """,
                          'existing_data': 'boo'}

    def initial_environ(dirname):
        return minimal_environ(MYDOWNLOAD=os.path.join(dirname, 'existing_data'))

    @gen.coroutine
    def get_initial(url):
        response = yield http_get_async(url)
        assert response.code == 200
        body = response.body.decode('utf-8')
        assert "Download {} to {}".format('http://example.com/bar', 'bar') in body
        _verify_choices(response,
                        (
                            # by default, do not perform the download
                            ('download', False),
                            # by default, keep existing value
                            ('environ', True),
                            # allow typing in a manual value
                            ('variables', False)))

    @gen.coroutine
    def post_empty_form(url):
        response = yield http_post_async(url, body='')
        assert response.code == 200
        body = response.body.decode('utf-8')
        assert "Done!" in body
        assert "File downloaded to " in body
        _verify_choices(response, ())

    def final_result_check(dirname, result):
        assert result
        expected = dict(MYDOWNLOAD=os.path.join(dirname, 'existing_data'), PROJECT_DIR=dirname)
        assert expected == strip_environ(result.environ)

    _run_browser_ui_test(monkeypatch=monkeypatch,
                         directory_contents=directory_contents,
                         initial_environ=initial_environ,
                         http_actions=[get_initial, post_empty_form],
                         final_result_check=final_result_check)


def test_browser_ui_shows_download_error(monkeypatch):
    directory_contents = {DEFAULT_PROJECT_FILENAME: """
downloads:
  MYDOWNLOAD:
    url: {error_url}
    """}
    initial_environ = minimal_environ()

    @gen.coroutine
    def get_initial(url):
        response = yield http_get_async(url)
        assert response.code == 200
        body = response.body.decode('utf-8')
        assert "Download {} to {}".format('http://example.com/bar?error=true', 'bar') in body
        _verify_choices(response,
                        (
                            # by default, perform the download
                            ('download', True),
                            # allow typing in a manual value
                            ('variables', False)))

    @gen.coroutine
    def post_empty_form(url):
        response = yield http_post_async(url, body='')
        assert response.code == 200
        body = response.body.decode('utf-8')
        # TODO: we are not currently showing the error, but the fix is over in UIServer
        # and not related to DownloadProvider per se, so for now this test checks for
        # what happens (you just see the option to try again) instead of what should happen
        # (it should also display the error message)
        assert "Download {} to {}".format('http://example.com/bar?error=true', 'bar') in body
        _verify_choices(response,
                        (
                            # by default, perform the download
                            ('download', True),
                            # allow typing in a manual value
                            ('variables', False)))

    def final_result_check(dirname, result):
        assert not result

    _run_browser_ui_test(monkeypatch=monkeypatch,
                         directory_contents=directory_contents,
                         initial_environ=initial_environ,
                         http_actions=[get_initial, post_empty_form],
                         final_result_check=final_result_check)


def test_browser_ui_choose_download_then_manual_override(monkeypatch):
    directory_contents = {DEFAULT_PROJECT_FILENAME: """
runtime:
  # this keeps the prepare from ever ending
  - FOO

downloads:
  MYDOWNLOAD:
    url: {url}
    """,
                          'existing_data': 'boo'}
    capture_dirname = dict()

    def initial_environ(dirname):
        capture_dirname['value'] = dirname
        return minimal_environ(MYDOWNLOAD=os.path.join(dirname, 'existing_data'))

    stuff = dict()

    @gen.coroutine
    def get_initial(url):
        response = yield http_get_async(url)
        assert response.code == 200
        body = response.body.decode('utf-8')
        stuff['form_names'] = _form_names(response)
        assert "Download {} to {}".format('http://example.com/bar', 'bar') in body
        _verify_choices(response,
                        (
                            # offer to perform the download but by default use the preset env var
                            ('download', False),
                            # by default, keep env var
                            ('environ', True),
                            # allow typing in a manual value
                            ('variables', False)))

    @gen.coroutine
    def post_do_download(url):
        form = _prefix_form(stuff['form_names'], {'source': 'download'})
        response = yield http_post_async(url, form=form)
        assert response.code == 200
        body = response.body.decode('utf-8')
        assert 'Keep value' in body
        stuff['form_names'] = _form_names(response)
        _verify_choices(response,
                        (
                            # the download caused env var to be set, offer to keep it
                            ('environ', True),
                            # allow typing in a manual value
                            ('variables', False)))

    @gen.coroutine
    def post_use_env(url):
        dirname = capture_dirname['value']
        form = _prefix_form(stuff['form_names'], {'source': 'variables',
                                                  'value': os.path.join(dirname, 'existing_data')})
        response = yield http_post_async(url, form=form)
        assert response.code == 200
        body = response.body.decode('utf-8')
        assert 'Use this' in body
        _verify_choices(response,
                        (('download', False),
                         ('environ', False),
                         # we've switched to the override value
                         ('variables', True)))

    def final_result_check(dirname, result):
        assert not result  # because 'FOO' isn't set

    _run_browser_ui_test(monkeypatch=monkeypatch,
                         directory_contents=directory_contents,
                         initial_environ=initial_environ,
                         http_actions=[get_initial, post_do_download, post_use_env],
                         final_result_check=final_result_check)
