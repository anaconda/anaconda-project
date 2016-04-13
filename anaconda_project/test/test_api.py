# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import

from anaconda_project import api
from anaconda_project import provide


def test_create_project(monkeypatch):
    params = dict(args=(), kwargs=dict())

    def mock_create_project(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        return 42

    monkeypatch.setattr('anaconda_project.project_ops.create', mock_create_project)

    p = api.AnacondaProject()
    kwargs = dict(directory_path=1, make_directory=2)
    result = p.create_project(**kwargs)
    assert 42 == result
    assert kwargs == params['kwargs']


def test_load_project(monkeypatch):
    class MockProject(object):
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr('anaconda_project.project.Project', MockProject)
    p = api.AnacondaProject()
    kwargs = dict(directory_path='foo', default_conda_environment='bar', default_command='baz')
    project = p.load_project(**kwargs)
    assert kwargs == project.kwargs


def _monkeypatch_prepare_without_interaction(monkeypatch):
    params = dict(args=(), kwargs=dict())

    def mock_prepare_without_interaction(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        return 42

    monkeypatch.setattr('anaconda_project.prepare.prepare_without_interaction', mock_prepare_without_interaction)
    return params


def _test_prepare_without_interaction(monkeypatch, api_method, provide_mode):
    params = _monkeypatch_prepare_without_interaction(monkeypatch)
    p = api.AnacondaProject()
    kwargs = dict(project=43, environ=57, extra_command_args=['1', '2'])
    result = getattr(p, api_method)(**kwargs)
    assert 42 == result
    assert params['kwargs']['mode'] == provide_mode
    del params['kwargs']['mode']
    assert kwargs == params['kwargs']


def test_prepare_project_locally(monkeypatch):
    _test_prepare_without_interaction(monkeypatch, 'prepare_project_locally', provide.PROVIDE_MODE_DEVELOPMENT)


def test_prepare_project_production(monkeypatch):
    _test_prepare_without_interaction(monkeypatch, 'prepare_project_production', provide.PROVIDE_MODE_PRODUCTION)


def test_prepare_project_check(monkeypatch):
    _test_prepare_without_interaction(monkeypatch, 'prepare_project_check', provide.PROVIDE_MODE_CHECK)


def test_prepare_project_browser(monkeypatch):
    params = dict(args=(), kwargs=dict())

    def mock_prepare_with_browser_ui(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        return 42

    monkeypatch.setattr('anaconda_project.prepare.prepare_with_browser_ui', mock_prepare_with_browser_ui)
    p = api.AnacondaProject()
    kwargs = dict(project=43, environ=57, extra_command_args=['1', '2'], io_loop=156, show_url=8909)
    result = p.prepare_project_browser(**kwargs)
    assert 42 == result
    assert kwargs == params['kwargs']


def test_add_variables(monkeypatch):
    params = dict(args=(), kwargs=dict())

    def mock_add_variables(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        return 42

    monkeypatch.setattr('anaconda_project.project_ops.add_variables', mock_add_variables)

    p = api.AnacondaProject()
    kwargs = dict(project=43, vars_to_add=45)
    result = p.add_variables(**kwargs)
    assert 42 == result
    assert kwargs == params['kwargs']


def test_remove_variables(monkeypatch):
    params = dict(args=(), kwargs=dict())

    def mock_add_variables(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        return 42

    monkeypatch.setattr('anaconda_project.project_ops.add_variables', mock_add_variables)

    p = api.AnacondaProject()
    kwargs = dict(project=43, vars_to_set=45)
    result = p.add_variables(**kwargs)
    assert 42 == result
    assert kwargs == params['kwargs']
