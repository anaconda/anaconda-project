# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import

import os
import platform

import conda_kapsel.internal.conda_api as conda_api
import conda_kapsel.internal.pip_api as pip_api
from conda_kapsel.test.environ_utils import (minimal_environ, minimal_environ_no_conda_env,
                                             strip_environ_keeping_conda_env)
from conda_kapsel.internal.test.http_utils import http_get_async, http_post_async
from conda_kapsel.internal.test.tmpfile_utils import with_directory_contents_completing_project_file
from conda_kapsel.internal.test.test_conda_api import monkeypatch_conda_not_to_use_links
from conda_kapsel.prepare import (prepare_without_interaction, prepare_with_browser_ui, unprepare)
from conda_kapsel.project_file import DEFAULT_PROJECT_FILENAME
from conda_kapsel.project import Project
from conda_kapsel import provide
from conda_kapsel.plugins.registry import PluginRegistry
from conda_kapsel.plugins.providers.conda_env import CondaEnvProvider

from tornado import gen

if platform.system() == 'Windows':
    script_dir = "Scripts"
else:
    script_dir = "bin"

conda_env_var = conda_api.conda_prefix_variable()


def test_find_by_class_name_conda_env():
    registry = PluginRegistry()
    found = registry.find_provider_by_class_name(class_name="CondaEnvProvider")
    assert found is not None
    assert isinstance(found, CondaEnvProvider)


def test_prepare_and_unprepare_project_scoped_env(monkeypatch):
    monkeypatch_conda_not_to_use_links(monkeypatch)

    def prepare_project_scoped_env(dirname):
        project = Project(dirname)
        fake_old_path = "foo" + os.pathsep + "bar"
        environ = dict(PROJECT_DIR=dirname, PATH=fake_old_path)
        result = prepare_without_interaction(project, environ=environ)
        assert result
        expected_env = os.path.join(dirname, "envs", "default")
        if platform.system() == 'Windows':
            expected_new_path = expected_env + os.pathsep + os.path.join(
                expected_env, script_dir) + os.pathsep + os.path.join(expected_env, "Library",
                                                                      "bin") + os.pathsep + "foo" + os.pathsep + "bar"
        else:
            expected_new_path = os.path.join(expected_env, script_dir) + os.pathsep + "foo" + os.pathsep + "bar"
        expected = dict(PROJECT_DIR=project.directory_path, PATH=expected_new_path)
        conda_api.environ_set_prefix(expected, expected_env)

        expected == result.environ
        assert os.path.exists(os.path.join(expected_env, "conda-meta"))
        conda_meta_mtime = os.path.getmtime(os.path.join(expected_env, "conda-meta"))

        # bare minimum default env shouldn't include these
        # (contrast with the test later where we list them in
        # requirements)
        installed = conda_api.installed(expected_env)
        assert 'ipython' not in installed
        assert 'numpy' not in installed

        # Prepare it again should no-op (use the already-existing environment)
        environ = dict(PROJECT_DIR=dirname, PATH=fake_old_path)
        result = prepare_without_interaction(project, environ=environ)
        assert result
        expected = dict(PROJECT_DIR=project.directory_path, PATH=expected_new_path)
        conda_api.environ_set_prefix(expected, expected_env)
        assert expected == result.environ
        assert conda_meta_mtime == os.path.getmtime(os.path.join(expected_env, "conda-meta"))

        # Now unprepare
        status = unprepare(project, result)
        assert status
        assert status.status_description == ('Deleted environment files in %s.' % (expected_env))
        assert status.errors == []
        assert not os.path.exists(expected_env)

    with_directory_contents_completing_project_file(dict(), prepare_project_scoped_env)


def test_prepare_project_scoped_env_conda_create_fails(monkeypatch):
    def mock_create(prefix, pkgs, channels):
        raise conda_api.CondaError("error_from_conda_create")

    monkeypatch.setattr('conda_kapsel.internal.conda_api.create', mock_create)

    def prepare_project_scoped_env_fails(dirname):
        project = Project(dirname)
        environ = minimal_environ(PROJECT_DIR=dirname)
        result = prepare_without_interaction(project, environ=environ)
        assert not result

        assert 'CONDA_DEFAULT_ENV' not in result.environ
        assert 'CONDA_ENV_PATH' not in result.environ

        # unprepare should not have anything to do
        status = unprepare(project, result)
        assert status
        assert status.errors == []
        assert status.status_description == "Nothing to clean up for environment 'default'."

    with_directory_contents_completing_project_file(dict(), prepare_project_scoped_env_fails)


def test_unprepare_gets_error_on_delete(monkeypatch):
    def mock_create(prefix, pkgs, channels):
        os.makedirs(os.path.join(prefix, "conda-meta"))

    monkeypatch.setattr('conda_kapsel.internal.conda_api.create', mock_create)

    def prepare_project_scoped_env(dirname):
        project = Project(dirname)
        environ = minimal_environ(PROJECT_DIR=dirname)
        result = prepare_without_interaction(project, environ=environ)
        assert result
        expected_env = os.path.join(dirname, "envs", "default")

        # Now unprepare

        def mock_rmtree(path):
            raise IOError("I will never rm the tree!")

        monkeypatch.setattr('shutil.rmtree', mock_rmtree)

        status = unprepare(project, result)
        assert status.status_description == ('Failed to remove environment files in %s: I will never rm the tree!.' %
                                             (expected_env))
        assert not status

        assert os.path.exists(expected_env)

        # so we can rmtree our tmp directory
        monkeypatch.undo()

    with_directory_contents_completing_project_file(dict(), prepare_project_scoped_env)


def test_prepare_project_scoped_env_not_attempted_in_check_mode(monkeypatch):
    def mock_create(prefix, pkgs, channels):
        raise Exception("Should not have attempted to create env")

    monkeypatch.setattr('conda_kapsel.internal.conda_api.create', mock_create)

    def prepare_project_scoped_env_not_attempted(dirname):
        project = Project(dirname)
        environ = minimal_environ(PROJECT_DIR=dirname)
        result = prepare_without_interaction(project, environ=environ, mode=provide.PROVIDE_MODE_CHECK)
        assert not result
        expected_env_path = os.path.join(dirname, "envs", "default")
        assert [
            ('missing requirement to run this project: ' +
             'The project needs a Conda environment containing all required packages.'),
            "  '%s' doesn't look like it contains a Conda environment yet." % expected_env_path
        ] == result.errors

        # unprepare should not have anything to do
        status = unprepare(project, result)
        assert status
        assert status.errors == []
        assert status.status_description == ("Nothing to clean up for environment 'default'.")

    with_directory_contents_completing_project_file(dict(), prepare_project_scoped_env_not_attempted)


def test_prepare_project_scoped_env_with_packages(monkeypatch):
    monkeypatch_conda_not_to_use_links(monkeypatch)

    def prepare_project_scoped_env_with_packages(dirname):
        project = Project(dirname)
        environ = minimal_environ(PROJECT_DIR=dirname)
        result = prepare_without_interaction(project, environ=environ)
        assert result

        prefix = result.environ[conda_env_var]
        installed = conda_api.installed(prefix)

        assert 'ipython' in installed
        assert 'numpy' in installed
        assert 'bokeh' not in installed

        # Preparing it again with new packages added should add those
        deps = project.project_file.get_value('packages')
        project.project_file.set_value('packages', deps + ['bokeh'])
        project.project_file.save()
        environ = minimal_environ(PROJECT_DIR=dirname)
        result = prepare_without_interaction(project, environ=environ)
        result.print_output()
        assert result

        prefix = result.environ[conda_env_var]
        installed = conda_api.installed(prefix)

        assert 'ipython' in installed
        assert 'numpy' in installed
        assert 'bokeh' in installed

        installed_pip = pip_api.installed(prefix)
        assert 'flake8' in installed_pip

        # Preparing it again with a bogus package should fail
        deps = project.project_file.get_value('packages')
        project.project_file.set_value(['packages'], deps + ['boguspackage'])
        project.project_file.save()
        environ = minimal_environ(PROJECT_DIR=dirname)
        result = prepare_without_interaction(project, environ=environ)
        assert not result

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
packages:
    - ipython
    - numpy
    - pip:
      - flake8
"""}, prepare_project_scoped_env_with_packages)


def _run_browser_ui_test(monkeypatch,
                         directory_contents,
                         initial_environ,
                         http_actions,
                         final_result_check,
                         conda_environment_override=None):
    from tornado.ioloop import IOLoop
    io_loop = IOLoop()

    def mock_conda_create(prefix, pkgs, channels):
        from conda_kapsel.internal.makedirs import makedirs_ok_if_exists
        metadir = os.path.join(prefix, "conda-meta")
        makedirs_ok_if_exists(metadir)
        for p in pkgs:
            pkgmeta = os.path.join(metadir, "%s-0.1-pyNN.json" % p)
            open(pkgmeta, 'a').close()

    monkeypatch.setattr('conda_kapsel.internal.conda_api.create', mock_conda_create)

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

        io_loop.add_callback(do_http)

    monkeypatch.setattr('webbrowser.open_new_tab', mock_open_new_tab)

    def do_browser_ui_test(dirname):
        project = Project(dirname)
        assert [] == project.problems
        if not isinstance(initial_environ, dict):
            environ = initial_environ(dirname)
        else:
            environ = initial_environ
        result = prepare_with_browser_ui(project,
                                         environ=environ,
                                         io_loop=io_loop,
                                         keep_going_until_success=True,
                                         env_spec_name=conda_environment_override)

        # finish up the last http action if prepare_ui.py stopped the loop before we did
        while 'done' not in http_done:
            io_loop.call_later(0.01, lambda: io_loop.stop())
            io_loop.start()

        if 'exception' in http_done:
            raise http_done['exception']

        final_result_check(dirname, result)

    with_directory_contents_completing_project_file(directory_contents, do_browser_ui_test)


def _extract_radio_items(response):
    from conda_kapsel.internal.plugin_html import _BEAUTIFUL_SOUP_BACKEND
    from bs4 import BeautifulSoup

    if response.code != 200:
        raise Exception("got a bad http response " + repr(response))

    soup = BeautifulSoup(response.body, _BEAUTIFUL_SOUP_BACKEND)
    radios = soup.find_all("input", attrs={'type': 'radio'})
    return radios


def _form_names(response):
    from conda_kapsel.internal.plugin_html import _BEAUTIFUL_SOUP_BACKEND
    from bs4 import BeautifulSoup

    if response.code != 200:
        raise Exception("got a bad http response " + repr(response))

    soup = BeautifulSoup(response.body, _BEAUTIFUL_SOUP_BACKEND)
    named_elements = soup.find_all(attrs={'name': True})
    names = set()
    for element in named_elements:
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


def test_browser_ui_with_default_env_and_no_env_var_set(monkeypatch):
    directory_contents = {DEFAULT_PROJECT_FILENAME: ""}
    initial_environ = minimal_environ_no_conda_env()

    @gen.coroutine
    def get_initial(url):
        response = yield http_get_async(url)
        assert response.code == 200
        body = response.body.decode('utf-8')
        # print("BODY: " + body.encode("ascii", 'ignore').decode('ascii'))
        assert "default' doesn't look like it contains a Conda environment yet." in body
        _verify_choices(response,
                        (
                            # by default, use one of the project-defined named envs
                            ('project', True),
                            # allow typing in a manual value
                            ('variables', False)))

    @gen.coroutine
    def post_empty_form(url):
        response = yield http_post_async(url, body='')
        assert response.code == 200
        body = response.body.decode('utf-8')
        assert "Done!" in body
        assert "Using Conda environment" in body
        assert "default" in body
        _verify_choices(response, ())

    def final_result_check(dirname, result):
        assert result
        expected_env_path = os.path.join(dirname, 'envs', 'default')
        expected = dict(PROJECT_DIR=dirname)
        conda_api.environ_set_prefix(expected, expected_env_path)
        assert expected == strip_environ_keeping_conda_env(result.environ)
        bindir = os.path.join(expected_env_path, script_dir)
        assert bindir in result.environ.get("PATH")

    _run_browser_ui_test(monkeypatch=monkeypatch,
                         directory_contents=directory_contents,
                         initial_environ=initial_environ,
                         http_actions=[get_initial, post_empty_form],
                         final_result_check=final_result_check)


def test_browser_ui_with_default_env_and_env_var_set(monkeypatch):
    directory_contents = {DEFAULT_PROJECT_FILENAME: ""}
    envprefix = os.path.join("not", "a", "real", "environment")
    initial_environ = minimal_environ(**{conda_env_var: envprefix})

    stuff = dict()

    @gen.coroutine
    def get_initial(url):
        response = yield http_get_async(url)
        assert response.code == 200
        body = response.body.decode('utf-8')
        assert "default' doesn't look like it contains a Conda environment yet." in body
        stuff['form_names'] = _form_names(response)
        _verify_choices(response,
                        (
                            # by default, use one of the project-defined named envs
                            ('project', True),
                            # offer choice to keep the environment setting
                            ('inherited', False),
                            # allow typing in a manual value
                            ('variables', False)))

    @gen.coroutine
    def post_choosing_default(url):
        form = _prefix_form(stuff['form_names'], {'source': 'project', 'env_name': 'default'})
        response = yield http_post_async(url, form=form)
        assert response.code == 200
        body = response.body.decode('utf-8')
        assert "Done!" in body
        assert "Using Conda environment" in body
        assert "default" in body
        _verify_choices(response, ())

    def final_result_check(dirname, result):
        assert result
        expected_env_path = os.path.join(dirname, 'envs', 'default')
        expected = dict(PROJECT_DIR=dirname)
        conda_api.environ_set_prefix(expected, expected_env_path)
        assert expected == strip_environ_keeping_conda_env(result.environ)
        bindir = os.path.join(expected_env_path, script_dir)
        assert bindir in result.environ.get("PATH")

    _run_browser_ui_test(monkeypatch=monkeypatch,
                         directory_contents=directory_contents,
                         initial_environ=initial_environ,
                         http_actions=[get_initial, post_choosing_default],
                         final_result_check=final_result_check)


def test_browser_ui_with_default_env_and_env_var_set_to_default_already(monkeypatch):
    directory_contents = {DEFAULT_PROJECT_FILENAME: ""}

    def initial_environ(dirname):
        default_env_path = os.path.join(dirname, "envs", "default")
        return minimal_environ(**{conda_env_var: default_env_path})

    stuff = dict()

    @gen.coroutine
    def get_initial(url):
        response = yield http_get_async(url)
        assert response.code == 200
        body = response.body.decode('utf-8')
        assert "default' doesn't look like it contains a Conda environment yet." in body
        stuff['form_names'] = _form_names(response)
        _verify_choices(response,
                        (
                            # by default, use one of the project-defined named envs
                            ('project', True),
                            # allow toggling on use inherited active env mode
                            ('inherited', False),
                            # allow typing in a manual value
                            ('variables', False)))

    @gen.coroutine
    def post_choosing_default(url):
        form = _prefix_form(stuff['form_names'], {'source': 'project', 'env_name': 'default'})
        response = yield http_post_async(url, form=form)
        assert response.code == 200
        body = response.body.decode('utf-8')
        assert "Done!" in body
        assert "Using Conda environment" in body
        assert "default" in body
        _verify_choices(response, ())

    def final_result_check(dirname, result):
        assert result
        expected_env_path = os.path.join(dirname, 'envs', 'default')
        expected = dict(PROJECT_DIR=dirname)
        conda_api.environ_set_prefix(expected, expected_env_path)
        assert expected == strip_environ_keeping_conda_env(result.environ)
        bindir = os.path.join(expected_env_path, script_dir)
        assert bindir in result.environ.get("PATH")

    _run_browser_ui_test(monkeypatch=monkeypatch,
                         directory_contents=directory_contents,
                         initial_environ=initial_environ,
                         http_actions=[get_initial, post_choosing_default],
                         final_result_check=final_result_check)


def test_browser_ui_using_inherited_then_back_to_default(monkeypatch):
    directory_contents = {DEFAULT_PROJECT_FILENAME: ""}
    envprefix = os.path.join("not", "a", "real", "environment")
    initial_environ = minimal_environ(**{conda_env_var: envprefix})

    stuff = dict()

    @gen.coroutine
    def get_initial(url):
        response = yield http_get_async(url)
        assert response.code == 200
        body = response.body.decode('utf-8')
        assert "default' doesn't look like it contains a Conda environment yet." in body
        stuff['form_names'] = _form_names(response)
        _verify_choices(response,
                        (
                            # by default, use one of the project-defined named envs
                            ('project', True),
                            # offer choice to inherit the active environment
                            ('inherited', False),
                            # allow typing in a manual value
                            ('variables', False)))

    @gen.coroutine
    def post_choosing_use_inherited(url):
        form = _prefix_form(stuff['form_names'], {'source': 'inherited'})
        response = yield http_post_async(url, form=form)
        assert response.code == 200
        # print("POST BODY: " + body)
        body = response.body.decode('utf-8')
        assert "Done!" not in body
        # error message should be about the environ thing we chose
        assert envprefix + "' doesn't look like it contains a Conda environment yet." in body
        _verify_choices(response,
                        (('project', False),
                         # the thing we chose should still be chosen
                         ('inherited', True),
                         ('variables', False)))

    @gen.coroutine
    def post_back_to_default_environ(url):
        form = _prefix_form(stuff['form_names'], {'source': 'project', 'env_name': 'default'})
        response = yield http_post_async(url, form=form)
        assert response.code == 200
        # print("POST BODY: " + body)
        body = response.body.decode('utf-8')
        assert "Done!" in body
        _verify_choices(response, ())

    def final_result_check(dirname, result):
        assert result
        expected_env_path = os.path.join(dirname, 'envs', 'default')
        conda_api.environ_get_prefix(result.environ) == expected_env_path
        assert result.environ['PROJECT_DIR'] == dirname

    _run_browser_ui_test(monkeypatch=monkeypatch,
                         directory_contents=directory_contents,
                         initial_environ=initial_environ,
                         # we choose keep environment twice, should be idempotent
                         http_actions=[get_initial, post_choosing_use_inherited, post_choosing_use_inherited,
                                       post_back_to_default_environ],
                         final_result_check=final_result_check)


def test_browser_ui_changing_to_new_prefix(monkeypatch):
    directory_contents = {DEFAULT_PROJECT_FILENAME: ""}
    envprefix = os.path.join("not", "a", "real", "environment")
    envprefix2 = os.path.join("another", "non", "real", "environment")
    initial_environ = minimal_environ(**{conda_env_var: envprefix})

    stuff = dict()

    @gen.coroutine
    def get_initial(url):
        response = yield http_get_async(url)
        assert response.code == 200
        body = response.body.decode('utf-8')
        assert "default' doesn't look like it contains a Conda environment yet." in body
        stuff['form_names'] = _form_names(response)
        _verify_choices(response,
                        (
                            # by default, use one of the project-defined named envs
                            ('project', True),
                            # offer choice to always use activated env
                            ('inherited', False),
                            # allow typing in a manual value
                            ('variables', False)))

    @gen.coroutine
    def post_choosing_inherited(url):
        form = _prefix_form(stuff['form_names'], {'source': 'inherited'})
        response = yield http_post_async(url, form=form)
        assert response.code == 200
        # print("POST BODY: " + body)
        body = response.body.decode('utf-8')
        assert "Done!" not in body
        # error message should be about the environ thing we chose
        assert envprefix + "' doesn't look like it contains a Conda environment yet." in body
        _verify_choices(response, (('project', False), ('inherited', True), ('variables', False)))

    @gen.coroutine
    def post_choosing_new_environ(url):
        form = _prefix_form(stuff['form_names'], {'source': 'variables', 'value': envprefix2})
        response = yield http_post_async(url, form=form)
        assert response.code == 200
        # print("POST BODY: " + body)
        body = response.body.decode('utf-8')
        assert "Done!" not in body
        # error message should be about the environ thing we chose
        assert envprefix2 + "' doesn't look like it contains a Conda environment yet." in body
        _verify_choices(response, (('project', False), ('inherited', False), ('variables', True)))

    def final_result_check(dirname, result):
        assert not result
        assert ['Browser UI main loop was stopped.'] == result.errors

    _run_browser_ui_test(monkeypatch=monkeypatch,
                         directory_contents=directory_contents,
                         initial_environ=initial_environ,
                         http_actions=[get_initial, post_choosing_inherited, post_choosing_new_environ],
                         final_result_check=final_result_check)


def test_browser_ui_three_envs_defaulting_to_first(monkeypatch):
    directory_contents = {DEFAULT_PROJECT_FILENAME: """
env_specs:
  default: {} # this is auto-created anyway, but here for clarity
  first_env: {}
  second_env:
    packages:
      - python
"""}
    initial_environ = minimal_environ_no_conda_env()

    @gen.coroutine
    def get_initial(url):
        response = yield http_get_async(url)
        assert response.code == 200
        body = response.body.decode('utf-8')
        # print("BODY: " + body)
        assert "default' doesn't look like it contains a Conda environment yet." in body
        _verify_choices(response,
                        (
                            # by default, use one of the project-defined named envs
                            ('project', True),
                            # allow typing in a manual value
                            ('variables', False)))

    @gen.coroutine
    def post_empty_form(url):
        response = yield http_post_async(url, body='')
        assert response.code == 200
        body = response.body.decode('utf-8')
        assert "Done!" in body
        assert "Using Conda environment" in body
        assert "default" in body
        _verify_choices(response, ())

    def final_result_check(dirname, result):
        assert result
        expected_env_path = os.path.join(dirname, 'envs', 'default')
        expected = dict(PROJECT_DIR=dirname)
        conda_api.environ_set_prefix(expected, expected_env_path)
        assert expected == strip_environ_keeping_conda_env(result.environ)
        bindir = os.path.join(expected_env_path, script_dir)
        assert bindir in result.environ.get("PATH")

    _run_browser_ui_test(monkeypatch=monkeypatch,
                         directory_contents=directory_contents,
                         initial_environ=initial_environ,
                         http_actions=[get_initial, post_empty_form],
                         final_result_check=final_result_check)


def test_browser_ui_three_envs_choosing_second(monkeypatch):
    directory_contents = {DEFAULT_PROJECT_FILENAME: """
env_specs:
  default: {} # this is auto-created anyway, but here for clarity
  first_env:
    packages:
      - python
  second_env: {}
"""}
    initial_environ = minimal_environ_no_conda_env()

    stuff = dict()

    @gen.coroutine
    def get_initial(url):
        response = yield http_get_async(url)
        assert response.code == 200
        body = response.body.decode('utf-8')
        stuff['form_names'] = _form_names(response)
        # print("BODY: " + body)
        assert "default' doesn't look like it contains a Conda environment yet." in body
        _verify_choices(response,
                        (
                            # by default, use one of the project-defined named envs
                            ('project', True),
                            # allow typing in a manual value
                            ('variables', False)))

    @gen.coroutine
    def post_choosing_second(url):
        form = _prefix_form(stuff['form_names'], {'source': 'project', 'env_name': 'second_env'})
        response = yield http_post_async(url, form=form)
        assert response.code == 200
        body = response.body.decode('utf-8')
        assert "Done!" in body
        assert "Using Conda environment" in body
        assert "second_env" in body
        _verify_choices(response, ())

    def final_result_check(dirname, result):
        assert result
        expected_env_path = os.path.join(dirname, 'envs', 'second_env')
        expected = dict(PROJECT_DIR=dirname)
        conda_api.environ_set_prefix(expected, expected_env_path)
        assert expected == strip_environ_keeping_conda_env(result.environ)
        bindir = os.path.join(expected_env_path, script_dir)
        assert bindir in result.environ.get("PATH")

    _run_browser_ui_test(monkeypatch=monkeypatch,
                         directory_contents=directory_contents,
                         initial_environ=initial_environ,
                         http_actions=[get_initial, post_choosing_second],
                         final_result_check=final_result_check)


def test_browser_ui_two_envs_user_override(monkeypatch):
    directory_contents = {DEFAULT_PROJECT_FILENAME: """
env_specs:
  first_env: {}
  second_env:
    packages:
      - python
"""}
    initial_environ = minimal_environ_no_conda_env()

    @gen.coroutine
    def get_initial(url):
        response = yield http_get_async(url)
        assert response.code == 200
        body = response.body.decode('utf-8')
        # print("BODY: " + body)
        assert "second_env' doesn't look like it contains a Conda environment yet." in body
        _verify_choices(response,
                        (
                            # by default, use the user override specifying a project-defined named env
                            ('project', True),
                            # allow typing in a manual value
                            ('variables', False)))

    @gen.coroutine
    def post_empty_form(url):
        response = yield http_post_async(url, body='')
        assert response.code == 200
        body = response.body.decode('utf-8')
        print(repr(body))
        assert "Done!" in body
        assert "Using Conda environment" in body
        assert "second_env" in body
        _verify_choices(response, ())

    def final_result_check(dirname, result):
        assert result
        expected_env_path = os.path.join(dirname, 'envs', 'second_env')
        expected = dict(PROJECT_DIR=dirname)
        conda_api.environ_set_prefix(expected, expected_env_path)
        assert expected == strip_environ_keeping_conda_env(result.environ)
        bindir = os.path.join(expected_env_path, script_dir)
        assert bindir in result.environ.get("PATH")

    _run_browser_ui_test(monkeypatch=monkeypatch,
                         directory_contents=directory_contents,
                         initial_environ=initial_environ,
                         http_actions=[get_initial, post_empty_form],
                         final_result_check=final_result_check,
                         conda_environment_override='second_env')
