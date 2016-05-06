# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import

from copy import deepcopy
import os
import platform
import pytest
import subprocess

from anaconda_project.test.environ_utils import minimal_environ, strip_environ
from anaconda_project.test.project_utils import project_no_dedicated_env
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.internal.crypto import decrypt_string
from anaconda_project.prepare import (prepare_without_interaction, prepare_with_browser_ui, unprepare,
                                      prepare_in_stages, PrepareSuccess, PrepareFailure, _after_stage_success,
                                      _FunctionPrepareStage)
from anaconda_project.project import Project
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME
from anaconda_project.local_state_file import LocalStateFile
from anaconda_project.plugins.requirement import EnvVarRequirement
from anaconda_project.conda_manager import (push_conda_manager_class, pop_conda_manager_class, CondaManager,
                                            CondaEnvironmentDeviations)


def test_prepare_empty_directory():
    def prepare_empty(dirname):
        project = project_no_dedicated_env(dirname)
        environ = minimal_environ()
        result = prepare_without_interaction(project, environ=environ)
        assert result
        assert dict(PROJECT_DIR=project.directory_path) == strip_environ(result.environ)
        assert dict() == strip_environ(environ)
        assert result.command_exec_info is None

    with_directory_contents(dict(), prepare_empty)


def test_prepare_bad_provide_mode():
    def prepare_bad_provide_mode(dirname):
        with pytest.raises(ValueError) as excinfo:
            project = project_no_dedicated_env(dirname)
            environ = minimal_environ()
            prepare_in_stages(project, mode="BAD_PROVIDE_MODE", environ=environ)
        assert "invalid provide mode" in repr(excinfo.value)

    with_directory_contents(dict(), prepare_bad_provide_mode)


def test_unprepare_empty_directory():
    def unprepare_empty(dirname):
        project = project_no_dedicated_env(dirname)
        environ = minimal_environ()
        result = prepare_without_interaction(project, environ=environ)
        assert result
        status = unprepare(project, result)
        assert status

    with_directory_contents(dict(), unprepare_empty)


def test_default_to_system_environ():
    def prepare_system_environ(dirname):
        project = project_no_dedicated_env(dirname)
        os_environ_copy = deepcopy(os.environ)
        result = prepare_without_interaction(project)
        assert project.directory_path == strip_environ(result.environ)['PROJECT_DIR']
        # os.environ wasn't modified
        assert os_environ_copy == os.environ
        # result.environ inherits everything in os.environ
        for key in os_environ_copy:
            assert result.environ[key] == os.environ[key]

    with_directory_contents(dict(), prepare_system_environ)


def test_prepare_some_env_var_already_set():
    def prepare_some_env_var(dirname):
        project = project_no_dedicated_env(dirname)
        environ = minimal_environ(FOO='bar')
        result = prepare_without_interaction(project, environ=environ)
        assert result
        assert dict(FOO='bar', PROJECT_DIR=project.directory_path) == strip_environ(result.environ)
        assert dict(FOO='bar') == strip_environ(environ)

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: {}
"""}, prepare_some_env_var)


def test_prepare_some_env_var_not_set():
    def prepare_some_env_var(dirname):
        project = project_no_dedicated_env(dirname)
        environ = minimal_environ(BAR='bar')
        result = prepare_without_interaction(project, environ=environ)
        assert not result
        assert dict(BAR='bar') == strip_environ(environ)

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: {}
"""}, prepare_some_env_var)


def test_prepare_some_env_var_not_set_keep_going():
    def prepare_some_env_var_keep_going(dirname):
        project = project_no_dedicated_env(dirname)
        environ = minimal_environ(BAR='bar')
        stage = prepare_in_stages(project, environ=environ, keep_going_until_success=True)
        for i in range(1, 10):
            next_stage = stage.execute()
            assert next_stage is not None
            assert stage.failed
            stage = next_stage
        assert dict(BAR='bar') == strip_environ(environ)

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: {}
"""}, prepare_some_env_var_keep_going)


def test_prepare_with_app_entry():
    def prepare_with_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        environ = minimal_environ(FOO='bar')
        env_path = environ.get('CONDA_ENV_PATH', environ.get('CONDA_DEFAULT_ENV', None))
        result = prepare_without_interaction(project, environ=environ)
        assert result

        command = result.command_exec_info
        assert 'FOO' in command.env
        assert command.cwd == project.directory_path
        if platform.system() == 'Windows':
            commandpath = os.path.join(env_path, "python.exe")
        else:
            commandpath = os.path.join(env_path, "bin", "python")
        assert command.args == [commandpath, 'echo.py', env_path, 'foo', 'bar']
        p = command.popen(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, err) = p.communicate()
        # strip is to pull off the platform-specific newline
        assert out.decode().strip() == ("['echo.py', '%s', 'foo', 'bar']" % (env_path.replace("\\", "\\\\")))
        assert err.decode() == ""

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: {}

commands:
  default:
    conda_app_entry: python echo.py ${PREFIX} foo bar
""",
         "echo.py": """
from __future__ import print_function
import sys
print(repr(sys.argv))
"""}, prepare_with_app_entry)


def test_prepare_choose_command():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        environ = minimal_environ()
        result = prepare_without_interaction(project, environ=environ, command_name='foo')
        assert result
        assert result.command_exec_info.bokeh_app == 'foo.py'

        environ = minimal_environ()
        result = prepare_without_interaction(project, environ=environ, command_name='bar')
        assert result
        assert result.command_exec_info.bokeh_app == 'bar.py'

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
commands:
    foo:
       bokeh_app: foo.py
    bar:
       bokeh_app: bar.py
""",
         "foo.py": "# foo",
         "bar.py": "# bar"}, check)


def _push_fake_env_creator():
    class HappyCondaManager(CondaManager):
        def find_environment_deviations(self, prefix, spec):
            return CondaEnvironmentDeviations(summary="all good", missing_packages=(), wrong_version_packages=())

        def fix_environment_deviations(self, prefix, spec, deviations=None):
            pass

        def remove_packages(self, prefix, packages):
            pass

    push_conda_manager_class(HappyCondaManager)


def _pop_fake_env_creator():
    pop_conda_manager_class()


def test_prepare_choose_environment():
    def check(dirname):
        if platform.system() == 'Windows':
            env_var = "CONDA_DEFAULT_ENV"
        else:
            env_var = "CONDA_ENV_PATH"

        try:
            _push_fake_env_creator()
            project = Project(dirname)
            environ = minimal_environ()
            result = prepare_without_interaction(project, environ=environ, conda_environment_name='foo')
            expected_path = project.conda_environments['foo'].path(project.directory_path)
            assert result.environ[env_var] == expected_path

            environ = minimal_environ()
            result = prepare_without_interaction(project, environ=environ, conda_environment_name='bar')
            assert result
            expected_path = project.conda_environments['bar'].path(project.directory_path)
            assert result.environ[env_var] == expected_path
        finally:
            _pop_fake_env_creator()

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
environments:
    foo: {}
    bar: {}
"""}, check)


def test_update_environ():
    def prepare_then_update_environ(dirname):
        project = project_no_dedicated_env(dirname)
        environ = minimal_environ(FOO='bar')
        result = prepare_without_interaction(project, environ=environ)
        assert result

        other = minimal_environ(BAR='baz')
        result.update_environ(other)
        assert dict(FOO='bar', BAR='baz', PROJECT_DIR=dirname) == strip_environ(other)

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: {}
"""}, prepare_then_update_environ)


def test_attempt_to_grab_result_early():
    def early_result_grab(dirname):
        project = project_no_dedicated_env(dirname)
        first_stage = prepare_in_stages(project)
        with pytest.raises(RuntimeError) as excinfo:
            first_stage.result
        assert "result property isn't available" in repr(excinfo.value)

    with_directory_contents(dict(), early_result_grab)


def test_attempt_to_grab_statuses_early():
    def early_status_grab(dirname):
        project = project_no_dedicated_env(dirname)
        first_stage = prepare_in_stages(project)
        with pytest.raises(RuntimeError) as excinfo:
            first_stage.statuses_after_execute
        assert "statuses_after_execute isn't available" in repr(excinfo.value)

    with_directory_contents(dict(), early_status_grab)


def test_skip_after_success_function_when_second_stage_fails():
    state = {'state': 'start'}

    def do_first(stage):
        assert state['state'] == 'start'
        state['state'] = 'first'
        stage.set_result(PrepareSuccess(logs=[], statuses=(), command_exec_info=None, environ=dict()), [])

        def last(stage):
            assert state['state'] == 'first'
            state['state'] = 'second'
            stage.set_result(PrepareFailure(logs=[], statuses=(), errors=[]), [])
            return None

        return _FunctionPrepareStage("second", [], last)

    first_stage = _FunctionPrepareStage("first", [], do_first)

    def after(updated_statuses):
        raise RuntimeError("should not have been called")

    stage = _after_stage_success(first_stage, after)
    while stage is not None:
        next_stage = stage.execute()
        result = stage.result
        if result.failed:
            assert stage.failed
            break
        else:
            assert not stage.failed
        stage = next_stage
    assert result.failed
    assert state['state'] == 'second'


def test_run_after_success_function_when_second_stage_succeeds():
    state = {'state': 'start'}

    def do_first(stage):
        assert state['state'] == 'start'
        state['state'] = 'first'
        stage.set_result(PrepareSuccess(logs=[], statuses=(), command_exec_info=None, environ=dict()), [])

        def last(stage):
            assert state['state'] == 'first'
            state['state'] = 'second'
            stage.set_result(PrepareSuccess(logs=[], statuses=(), command_exec_info=None, environ=dict()), [])
            return None

        return _FunctionPrepareStage("second", [], last)

    first_stage = _FunctionPrepareStage("first", [], do_first)

    def after(updated_statuses):
        assert state['state'] == 'second'
        state['state'] = 'after'

    stage = _after_stage_success(first_stage, after)
    while stage is not None:
        next_stage = stage.execute()
        result = stage.result
        if result.failed:
            assert stage.failed
            break
        else:
            assert not stage.failed
        stage = next_stage
    assert not result.failed
    assert state['state'] == 'after'


def test_prepare_with_browser(monkeypatch):
    from tornado.ioloop import IOLoop
    io_loop = IOLoop()

    http_results = {}

    def mock_open_new_tab(url):
        from anaconda_project.internal.test.http_utils import http_get_async, http_post_async
        from tornado import gen

        @gen.coroutine
        def do_http():
            http_results['get'] = yield http_get_async(url)
            http_results['post'] = yield http_post_async(url, body="")

        io_loop.add_callback(do_http)

    monkeypatch.setattr('webbrowser.open_new_tab', mock_open_new_tab)

    def prepare_with_browser(dirname):
        project = project_no_dedicated_env(dirname)
        environ = minimal_environ(BAR='bar')
        result = prepare_with_browser_ui(project, environ=environ, keep_going_until_success=False, io_loop=io_loop)
        assert not result
        assert dict(BAR='bar') == strip_environ(environ)

        # wait for the results of the POST to come back,
        # awesome hack-tacular
        while 'post' not in http_results:
            io_loop.call_later(0.01, lambda: io_loop.stop())
            io_loop.start()

        assert 'get' in http_results
        assert 'post' in http_results

        assert 200 == http_results['get'].code
        assert 200 == http_results['post'].code

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: {}
"""}, prepare_with_browser)


def test_prepare_asking_for_password_with_browser(monkeypatch):
    # In this scenario, the master password is already in
    # the environment and we need to ask for another password
    # that we'd store using the master password.
    from tornado.ioloop import IOLoop
    io_loop = IOLoop()

    http_results = {}

    def click_submit(url):
        from anaconda_project.internal.test.http_utils import http_get_async, http_post_async
        from tornado import gen

        @gen.coroutine
        def do_http():
            http_results['get_click_submit'] = get_response = yield http_get_async(url)

            if get_response.code != 200:
                raise Exception("got a bad http response " + repr(get_response))

            http_results['post_click_submit'] = post_response = yield http_post_async(url, body="")

            assert 200 == post_response.code
            assert '</form>' in str(post_response.body)
            assert 'FOO_PASSWORD' in str(post_response.body)

            fill_in_password(url, post_response)

        io_loop.add_callback(do_http)

    def fill_in_password(url, first_response):
        from anaconda_project.internal.test.http_utils import http_post_async
        from anaconda_project.internal.plugin_html import _BEAUTIFUL_SOUP_BACKEND
        from tornado import gen
        from bs4 import BeautifulSoup

        if first_response.code != 200:
            raise Exception("got a bad http response " + repr(first_response))

        # set the FOO_PASSWORD field
        soup = BeautifulSoup(first_response.body, _BEAUTIFUL_SOUP_BACKEND)
        password_fields = soup.find_all("input", attrs={'type': 'password'})
        if len(password_fields) == 0:
            print("No password fields in " + repr(soup))
            raise Exception("password field not found")
        else:
            field = password_fields[0]

        assert 'name' in field.attrs

        @gen.coroutine
        def do_http():
            http_results['post_fill_in_password'] = yield http_post_async(url, form={field['name']: 'bloop'})

        io_loop.add_callback(do_http)

    def mock_open_new_tab(url):
        return click_submit(url)

    monkeypatch.setattr('webbrowser.open_new_tab', mock_open_new_tab)

    def prepare_with_browser(dirname):
        project = project_no_dedicated_env(dirname)
        environ = minimal_environ(ANACONDA_MASTER_PASSWORD='bar')
        result = prepare_with_browser_ui(project, environ=environ, keep_going_until_success=False, io_loop=io_loop)
        assert result
        assert dict(ANACONDA_MASTER_PASSWORD='bar',
                    FOO_PASSWORD='bloop',
                    PROJECT_DIR=project.directory_path) == strip_environ(result.environ)
        assert dict(ANACONDA_MASTER_PASSWORD='bar') == strip_environ(environ)

        # wait for the results of the POST to come back,
        # awesome hack-tacular
        while 'post_fill_in_password' not in http_results:
            io_loop.call_later(0.01, lambda: io_loop.stop())
            io_loop.start()

        assert 'get_click_submit' in http_results
        assert 'post_click_submit' in http_results
        assert 'post_fill_in_password' in http_results

        assert 200 == http_results['get_click_submit'].code
        assert 200 == http_results['post_click_submit'].code
        assert 200 == http_results['post_fill_in_password'].code

        final_done_html = str(http_results['post_fill_in_password'].body)
        assert "Done!" in final_done_html
        assert "Environment variable FOO_PASSWORD is set." in final_done_html

        local_state_file = LocalStateFile.load_for_directory(project.directory_path)
        foo_password = local_state_file.get_value(['variables', 'FOO_PASSWORD'])
        assert isinstance(foo_password, dict)
        assert foo_password['key'] == 'ANACONDA_MASTER_PASSWORD'
        assert 'encrypted' in foo_password
        encrypted = foo_password['encrypted']
        decrypted = decrypt_string(encrypted, 'bar')
        assert 'bloop' == decrypted

        # now a no-browser prepare() should read password from the
        # local state file

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
variables:
  FOO_PASSWORD: {}
"""}, prepare_with_browser)


def test_prepare_problem_project_with_browser(monkeypatch):
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        environ = minimal_environ(BAR='bar')
        result = prepare_with_browser_ui(project, environ=environ, keep_going_until_success=False)
        assert not result
        assert dict(BAR='bar') == strip_environ(environ)

        assert [('Icon file %s does not exist.' % os.path.join(dirname, 'foo.png')), 'Unable to load the project.'
                ] == result.errors

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
icon: foo.png
"""}, check)


def test_prepare_success_properties():
    result = PrepareSuccess(logs=["a"], statuses=(), command_exec_info=None, environ=dict())
    assert result.statuses == ()
    assert result.status_for('FOO') is None
    assert result.status_for(EnvVarRequirement) is None
