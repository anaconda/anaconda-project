# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import

import inspect

from anaconda_project import api
from anaconda_project import provide


def _verify_args_match(function1, function2, ignored=('self', )):
    f1spec = inspect.getargspec(function1)
    f2spec = inspect.getargspec(function2)
    args1 = list(f1spec.args)
    args2 = list(f2spec.args)
    for param in ignored:
        if param in args1:
            args1.remove(param)
        if param in args2:
            args2.remove(param)
    assert args1 == args2


def test_create_project(monkeypatch):
    params = dict(args=(), kwargs=dict())

    def mock_create_project(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        return 42

    monkeypatch.setattr('anaconda_project.project_ops.create', mock_create_project)

    p = api.AnacondaProject()
    kwargs = dict(directory_path=1, make_directory=2, name='foo', icon='bar')
    result = p.create_project(**kwargs)
    assert 42 == result
    assert kwargs == params['kwargs']


def test_load_project(monkeypatch):
    from anaconda_project.project import Project
    _verify_args_match(api.AnacondaProject.load_project, Project.__init__, ignored=['self', 'plugin_registry'])

    class MockProject(object):
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr('anaconda_project.project.Project', MockProject)
    p = api.AnacondaProject()
    kwargs = dict(directory_path='foo')
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
    from anaconda_project.prepare import prepare_without_interaction
    _verify_args_match(
        getattr(api.AnacondaProject, api_method),
        prepare_without_interaction,
        ignored=['self', 'mode', 'provide_whitelist'])

    params = _monkeypatch_prepare_without_interaction(monkeypatch)
    p = api.AnacondaProject()
    kwargs = dict(project=43,
                  environ=57,
                  conda_environment_name='someenv',
                  command_name='foo',
                  extra_command_args=['1', '2'])
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
    from anaconda_project.prepare import prepare_with_browser_ui
    _verify_args_match(api.AnacondaProject.prepare_project_browser,
                       prepare_with_browser_ui,
                       ignored=['self', 'keep_going_until_success'])

    params = dict(args=(), kwargs=dict())

    def mock_prepare_with_browser_ui(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        return 42

    monkeypatch.setattr('anaconda_project.prepare.prepare_with_browser_ui', mock_prepare_with_browser_ui)
    p = api.AnacondaProject()
    kwargs = dict(project=43,
                  environ=57,
                  conda_environment_name='someenv',
                  command_name='foo',
                  extra_command_args=['1', '2'],
                  io_loop=156,
                  show_url=8909)
    result = p.prepare_project_browser(**kwargs)
    assert 42 == result
    assert kwargs == params['kwargs']


def test_set_properties(monkeypatch):
    import anaconda_project.project_ops as project_ops
    _verify_args_match(api.AnacondaProject.set_properties, project_ops.set_properties)

    params = dict(args=(), kwargs=dict())

    def mock_set_properties(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        return 42

    monkeypatch.setattr('anaconda_project.project_ops.set_properties', mock_set_properties)

    p = api.AnacondaProject()
    kwargs = dict(project=43, name='foo', icon='bar')
    result = p.set_properties(**kwargs)
    assert 42 == result
    assert kwargs == params['kwargs']


def test_add_variables(monkeypatch):
    import anaconda_project.project_ops as project_ops
    _verify_args_match(api.AnacondaProject.add_variables, project_ops.add_variables)

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
    import anaconda_project.project_ops as project_ops
    _verify_args_match(api.AnacondaProject.remove_variables, project_ops.remove_variables)

    params = dict(args=(), kwargs=dict())

    def mock_remove_variables(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        return 42

    monkeypatch.setattr('anaconda_project.project_ops.remove_variables', mock_remove_variables)

    p = api.AnacondaProject()
    kwargs = dict(project=43, vars_to_remove=45)
    result = p.remove_variables(**kwargs)
    assert 42 == result
    assert kwargs == params['kwargs']


def test_add_download(monkeypatch):
    import anaconda_project.project_ops as project_ops
    _verify_args_match(api.AnacondaProject.add_download, project_ops.add_download)

    params = dict(args=(), kwargs=dict())

    def mock_add_download(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        return 42

    monkeypatch.setattr('anaconda_project.project_ops.add_download', mock_add_download)

    p = api.AnacondaProject()
    kwargs = dict(project=43, env_var='boo', url='baz', filename="fname")
    result = p.add_download(**kwargs)
    assert 42 == result
    assert kwargs == params['kwargs']


def test_remove_download(monkeypatch):
    import anaconda_project.project_ops as project_ops
    _verify_args_match(api.AnacondaProject.remove_download, project_ops.remove_download)

    params = dict(args=(), kwargs=dict())

    def mock_remove_download(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        return 42

    monkeypatch.setattr('anaconda_project.project_ops.remove_download', mock_remove_download)

    p = api.AnacondaProject()
    kwargs = dict(project=43, env_var='boo')
    result = p.remove_download(**kwargs)
    assert 42 == result
    assert kwargs == params['kwargs']


def test_add_environment(monkeypatch):
    import anaconda_project.project_ops as project_ops
    _verify_args_match(api.AnacondaProject.add_environment, project_ops.add_environment)

    params = dict(args=(), kwargs=dict())

    def mock_add_environment(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        return 42

    monkeypatch.setattr('anaconda_project.project_ops.add_environment', mock_add_environment)

    p = api.AnacondaProject()
    kwargs = dict(project=43, name='foo', packages=['a'], channels=['b'])
    result = p.add_environment(**kwargs)
    assert 42 == result
    assert kwargs == params['kwargs']


def test_remove_environment(monkeypatch):
    import anaconda_project.project_ops as project_ops
    _verify_args_match(api.AnacondaProject.remove_environment, project_ops.remove_environment)

    params = dict(args=(), kwargs=dict())

    def mock_remove_environment(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        return 42

    monkeypatch.setattr('anaconda_project.project_ops.remove_environment', mock_remove_environment)

    p = api.AnacondaProject()
    kwargs = dict(project=43, name='foo')
    result = p.remove_environment(**kwargs)
    assert 42 == result
    assert kwargs == params['kwargs']


def test_add_dependencies(monkeypatch):
    import anaconda_project.project_ops as project_ops
    _verify_args_match(api.AnacondaProject.add_dependencies, project_ops.add_dependencies)

    params = dict(args=(), kwargs=dict())

    def mock_add_dependencies(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        return 42

    monkeypatch.setattr('anaconda_project.project_ops.add_dependencies', mock_add_dependencies)

    p = api.AnacondaProject()
    kwargs = dict(project=43, environment='foo', packages=['a'], channels=['b'])
    result = p.add_dependencies(**kwargs)
    assert 42 == result
    assert kwargs == params['kwargs']


def test_remove_dependencies(monkeypatch):
    import anaconda_project.project_ops as project_ops
    _verify_args_match(api.AnacondaProject.remove_dependencies, project_ops.remove_dependencies)

    params = dict(args=(), kwargs=dict())

    def mock_remove_dependencies(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        return 42

    monkeypatch.setattr('anaconda_project.project_ops.remove_dependencies', mock_remove_dependencies)

    p = api.AnacondaProject()
    kwargs = dict(project=43, environment='foo', packages=['a'])
    result = p.remove_dependencies(**kwargs)
    assert 42 == result
    assert kwargs == params['kwargs']


def test_add_command(monkeypatch):
    import anaconda_project.project_ops as project_ops
    _verify_args_match(api.AnacondaProject.add_command, project_ops.add_command)

    params = dict(args=(), kwargs=dict())

    def mock_add_command(*args, **kwargs):
        print(args, kwargs)
        params['args'] = args
        params['kwargs'] = kwargs
        return 42

    monkeypatch.setattr('anaconda_project.project_ops.add_command', mock_add_command)

    p = api.AnacondaProject()

    kwargs = dict(project=43, command_type='bokeh_app', name='name', command='file.py')
    result = p.add_command(**kwargs)
    assert 42 == result
    assert kwargs == params['kwargs']


def test_update_command(monkeypatch):
    import anaconda_project.project_ops as project_ops
    _verify_args_match(api.AnacondaProject.update_command, project_ops.update_command)

    params = dict(args=(), kwargs=dict())

    def mock_update_command(*args, **kwargs):
        print(args, kwargs)
        params['args'] = args
        params['kwargs'] = kwargs
        return 42

    monkeypatch.setattr('anaconda_project.project_ops.update_command', mock_update_command)

    p = api.AnacondaProject()

    kwargs = dict(project=43, command_type='bokeh_app', name='name', command='file.py', new_name='foo')
    result = p.update_command(**kwargs)
    assert 42 == result
    assert kwargs == params['kwargs']


def test_remove_command(monkeypatch):
    import anaconda_project.project_ops as project_ops
    _verify_args_match(api.AnacondaProject.remove_command, project_ops.remove_command)

    params = dict(args=(), kwargs=dict())

    def mock_remove_command(*args, **kwargs):
        print(args, kwargs)
        params['args'] = args
        params['kwargs'] = kwargs
        return 42

    monkeypatch.setattr('anaconda_project.project_ops.remove_command', mock_remove_command)

    p = api.AnacondaProject()

    kwargs = dict(project=43, name='name')
    result = p.remove_command(**kwargs)
    assert 42 == result
    assert kwargs == params['kwargs']


def test_add_service(monkeypatch):
    import anaconda_project.project_ops as project_ops
    _verify_args_match(api.AnacondaProject.add_service, project_ops.add_service)

    params = dict(args=(), kwargs=dict())

    def mock_add_service(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        return 42

    monkeypatch.setattr('anaconda_project.project_ops.add_service', mock_add_service)

    p = api.AnacondaProject()
    kwargs = dict(project=43, service_type='abc', variable_name='xyz')
    result = p.add_service(**kwargs)
    assert 42 == result
    assert kwargs == params['kwargs']


def test_remove_service(monkeypatch):
    import anaconda_project.project_ops as project_ops
    _verify_args_match(api.AnacondaProject.remove_service, project_ops.remove_service)

    params = dict(args=(), kwargs=dict())

    def mock_remove_service(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs
        return 42

    monkeypatch.setattr('anaconda_project.project_ops.remove_service', mock_remove_service)

    p = api.AnacondaProject()
    kwargs = dict(project=43, variable_name='xyz')
    result = p.remove_service(**kwargs)
    assert 42 == result
    assert kwargs == params['kwargs']
