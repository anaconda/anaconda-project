# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import

from copy import deepcopy
import os
import platform
import pytest
import subprocess
import sys

from anaconda_project.test.environ_utils import minimal_environ, strip_environ
from anaconda_project.test.project_utils import project_no_dedicated_env
from anaconda_project.internal.test.tmpfile_utils import (with_directory_contents,
                                                          with_directory_contents_completing_project_file)
from anaconda_project.internal import conda_api
from anaconda_project.prepare import (prepare_without_interaction, unprepare, prepare_in_stages, PrepareSuccess,
                                      PrepareFailure, _after_stage_success, _FunctionPrepareStage)
from anaconda_project.project import Project
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME
from anaconda_project.project_commands import ProjectCommand
from anaconda_project.requirements_registry.requirement import UserConfigOverrides
from anaconda_project.conda_manager import (push_conda_manager_class, pop_conda_manager_class, CondaManager,
                                            CondaEnvironmentDeviations, CondaLockSet)


def _monkeypatch_reduced_environment(monkeypatch):
    def mock_env_packages():
        return ['python=3.7']

    monkeypatch.setattr('anaconda_project.env_spec._default_env_spec_packages', mock_env_packages)


@pytest.mark.slow
def test_prepare_empty_directory(monkeypatch):
    _monkeypatch_reduced_environment(monkeypatch)

    def prepare_empty(dirname):
        project = Project(dirname)
        environ = minimal_environ()
        result = prepare_without_interaction(project, environ=environ)
        assert result.errors == []
        assert result
        assert result.env_prefix is not None
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


@pytest.mark.slow
@pytest.mark.skipif(platform.system() == 'Windows'
                    and not (sys.version_info.major == 3 and sys.version_info.minor == 4),
                    reason="on Windows, can't delete env dir except on python 3.4, don't know why")
def test_unprepare_empty_directory(monkeypatch):
    _monkeypatch_reduced_environment(monkeypatch)

    def unprepare_empty(dirname):
        project = Project(dirname)
        environ = minimal_environ()
        result = prepare_without_interaction(project, environ=environ)
        assert result.errors == []
        assert result
        status = unprepare(project, result)
        assert status.errors == []
        assert status

    with_directory_contents(dict(), unprepare_empty)


def test_unprepare_problem_project():
    def unprepare_problems(dirname):
        project = project_no_dedicated_env(dirname)
        environ = minimal_environ()
        result = prepare_without_interaction(project, environ=environ)
        assert not result
        assert result.env_prefix is None
        status = unprepare(project, result)
        assert not status
        assert status.status_description == 'Unable to load the project.'
        assert status.errors == [
            ('%s: variables section contains wrong value type 42, ' + 'should be dict or list of requirements') %
            project.project_file.basename
        ]

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, unprepare_problems)


@pytest.mark.slow
def test_unprepare_nothing_to_do(monkeypatch):
    _monkeypatch_reduced_environment(monkeypatch)

    def unprepare_nothing(dirname):
        project = Project(dirname)
        environ = minimal_environ()
        result = prepare_without_interaction(project, environ=environ)
        assert result.errors == []
        assert result
        status = unprepare(project, result, whitelist=[])
        assert status.errors == []
        assert status
        assert status.status_description == 'Nothing to clean up.'

    with_directory_contents(dict(), unprepare_nothing)


def test_default_to_system_environ():
    def prepare_system_environ(dirname):
        project = project_no_dedicated_env(dirname)
        os_environ_copy = deepcopy(os.environ)
        result = prepare_without_interaction(project)
        assert result
        assert result.errors == []
        assert project.directory_path == strip_environ(result.environ)['PROJECT_DIR']
        # os.environ wasn't modified
        assert os_environ_copy == os.environ
        # result.environ inherits everything in os.environ
        for key, original in os_environ_copy.items():
            updated = result.environ.get(key)
            if updated != original:
                if original in ('root', 'base') and updated in ('root', 'base'):
                    print("we have a root/base environment name issue here")
                    continue
                if key == 'PATH' and platform.system() == 'Windows':
                    print("prepare changed PATH on Windows and ideally it would not.")
                    continue
                updated = updated.split(os.pathsep)
                original = original.split(os.pathsep)
                print("ORIGINAL {}: {}".format(key, repr(original)))
                print("UPDATED {}: {}".format(key, repr(updated)))
            assert updated == original

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
packages: []
        """}, prepare_system_environ)


def test_prepare_some_env_var_already_set():
    def prepare_some_env_var(dirname):
        project = project_no_dedicated_env(dirname)
        environ = minimal_environ(FOO='bar')
        result = prepare_without_interaction(project, environ=environ)
        assert result.errors == []
        assert result
        assert dict(FOO='bar', PROJECT_DIR=project.directory_path) == strip_environ(result.environ)
        assert dict(FOO='bar') == strip_environ(environ)

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: {}
"""}, prepare_some_env_var)


def test_prepare_some_env_var_not_set():
    def prepare_some_env_var(dirname):
        project = project_no_dedicated_env(dirname)
        environ = minimal_environ(BAR='bar')
        result = prepare_without_interaction(project, environ=environ)
        assert not result
        assert result.env_prefix is not None
        assert dict(BAR='bar') == strip_environ(environ)

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: {}
"""}, prepare_some_env_var)


def test_prepare_some_env_var_not_set_keep_going():
    def prepare_some_env_var_keep_going(dirname):
        project = project_no_dedicated_env(dirname)
        environ = minimal_environ(BAR='bar')
        stage = prepare_in_stages(project, environ=environ, keep_going_until_success=True)
        assert "Set up project." == stage.description_of_action
        assert ['FOO', 'CONDA_PREFIX'] == [status.requirement.env_var for status in stage.statuses_before_execute]

        # there's an initial stage to set the conda env
        next_stage = stage.execute()
        assert ['FOO', 'CONDA_PREFIX'] == [status.requirement.env_var for status in stage.statuses_after_execute]
        assert not stage.failed
        assert stage.environ['PROJECT_DIR'] == dirname
        assert "Set up project." == next_stage.description_of_action
        assert ['FOO', 'CONDA_PREFIX'] == [status.requirement.env_var for status in next_stage.statuses_before_execute]
        stage = next_stage

        for i in range(1, 10):
            next_stage = stage.execute()
            assert next_stage is not None
            assert stage.failed
            assert stage.environ['PROJECT_DIR'] == dirname
            stage = next_stage
        assert dict(BAR='bar') == strip_environ(environ)

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
variables:
  FOO: {}
"""}, prepare_some_env_var_keep_going)


def test_prepare_with_app_entry():
    def prepare_with_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        environ = minimal_environ(FOO='bar')
        env_path = conda_api.environ_get_prefix(environ)
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

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
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
"""
        }, prepare_with_app_entry)


def test_prepare_choose_command():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        environ = minimal_environ()
        result = prepare_without_interaction(project, environ=environ, command_name='foo')
        assert result.errors == []
        assert result
        assert os.path.join(project.directory_path, 'foo.py') in result.command_exec_info.args

        environ = minimal_environ()
        result = prepare_without_interaction(project, environ=environ, command_name='bar')
        assert result.errors == []
        assert result
        assert os.path.join(project.directory_path, 'bar.py') in result.command_exec_info.args

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
commands:
    foo:
       bokeh_app: foo.py
    bar:
       bokeh_app: bar.py
packages:
  - bokeh
""",
            "foo.py": "# foo",
            "bar.py": "# bar"
        }, check)


@pytest.mark.slow
def test_prepare_missing_unpack():
    def check(dirname):
        project = Project(dirname)
        environ = minimal_environ()
        result = prepare_without_interaction(project, environ=environ)
        assert result

        # now mimmick an unpacked project
        packed_file = os.path.join(dirname, 'envs', 'default', 'conda-meta', '.packed')
        with open(packed_file, 'wt') as f:
            f.write(conda_api.current_platform())

        # without a functional conda-unpack script it will rebuild the env
        result = prepare_without_interaction(project, environ=environ)
        assert result
        assert not os.path.exists(packed_file)

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
env_specs:
  default: {}
""",
            "foo.py": "# foo",
            "bar.py": "# bar",
        }, check)


def test_prepare_default_command():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        environ = minimal_environ()
        result = prepare_without_interaction(project, environ=environ, command_name='default')
        assert result.errors == []
        assert result
        assert os.path.join(project.directory_path, 'foo.py') in result.command_exec_info.args

        # environ = minimal_environ()
        # result = prepare_without_interaction(project, environ=environ, command_name='bar')
        # assert result.errors == []
        # assert result
        # assert os.path.join(project.directory_path, 'bar.py') in result.command_exec_info.args

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
commands:
    foo:
       bokeh_app: foo.py
    bar:
       bokeh_app: bar.py
packages:
  - bokeh
""",
            "foo.py": "# foo",
            "bar.py": "# bar"
        }, check)


def test_prepare_command_not_in_project():
    def check(dirname):
        # create a command that isn't in the Project
        project = project_no_dedicated_env(dirname)
        command = ProjectCommand(name="foo",
                                 attributes=dict(bokeh_app="foo.py", env_spec=project.default_env_spec_name))
        environ = minimal_environ()
        result = prepare_without_interaction(project, environ=environ, command=command)
        assert result.errors == []
        assert result
        assert os.path.join(project.directory_path, 'foo.py') in result.command_exec_info.args

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
commands:
  decoy:
    description: "do not use me"
    unix: foobar
    windows: foobar
""",
            "foo.py": "# foo"
        }, check)


def test_prepare_bad_command_name():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        environ = minimal_environ(BAR='bar')
        result = prepare_without_interaction(project, environ=environ, command_name="blah")
        assert not result
        assert result.env_prefix is None
        assert result.errors
        assert "Command name 'blah' is not in" in result.errors[0]

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
"""}, check)


def _push_fake_env_creator():
    class HappyCondaManager(CondaManager):
        def __init__(self, frontend):
            pass

        def resolve_dependencies(self, package_specs, channels, platforms):
            return CondaLockSet({})

        def find_environment_deviations(self, prefix, spec):
            return CondaEnvironmentDeviations(summary="all good",
                                              missing_packages=(),
                                              wrong_version_packages=(),
                                              missing_pip_packages=(),
                                              wrong_version_pip_packages=())

        def fix_environment_deviations(self, prefix, spec, deviations=None, create=True):
            pass

        def remove_packages(self, prefix, packages):
            pass

    push_conda_manager_class(HappyCondaManager)


def _pop_fake_env_creator():
    pop_conda_manager_class()


def test_prepare_choose_environment():
    def check(dirname):
        env_var = conda_api.conda_prefix_variable()

        try:
            _push_fake_env_creator()
            project = Project(dirname)
            environ = minimal_environ()
            result = prepare_without_interaction(project, environ=environ, env_spec_name='foo')
            expected_path = project.env_specs['foo'].path(project.directory_path)
            assert result.environ[env_var] == expected_path

            environ = minimal_environ()
            result = prepare_without_interaction(project, environ=environ, env_spec_name='bar')
            assert result.errors == []
            assert result
            expected_path = project.env_specs['bar'].path(project.directory_path)
            assert result.environ[env_var] == expected_path
        finally:
            _pop_fake_env_creator()

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME:
            """
name: blah
platforms: [linux-32,linux-64,osx-64,win-32,win-64]
env_specs:
    foo: {}
    bar: {}
"""
        }, check)


def test_prepare_no_env_specs():
    def check(dirname):
        env_var = conda_api.conda_prefix_variable()

        try:
            _push_fake_env_creator()
            project = Project(dirname)
            environ = minimal_environ()
            result = prepare_without_interaction(project, environ=environ, env_spec_name='default')
            expected_path = project.env_specs['default'].path(project.directory_path)
            assert result.environ[env_var] == expected_path
        finally:
            _pop_fake_env_creator()

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
name: blah
platforms: [linux-32,linux-64,osx-64,win-32,win-64]
"""}, check)


def test_prepare_use_command_specified_env_spec():
    def check(dirname):
        env_var = conda_api.conda_prefix_variable()

        try:
            _push_fake_env_creator()
            project = Project(dirname)
            environ = minimal_environ()
            # we specify the command name but not the
            # env_spec_name but it should imply the proper env
            # spec name.
            result = prepare_without_interaction(project, environ=environ, command_name='hello')
            expected_path = project.env_specs['foo'].path(project.directory_path)
            assert result.environ[env_var] == expected_path
        finally:
            _pop_fake_env_creator()

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME:
            """
name: blah
platforms: [linux-32,linux-64,osx-64,win-32,win-64]
env_specs:
    default: {}
    foo: {}
    bar: {}
commands:
    hello:
       env_spec: foo
       unix: echo hello
       windows: echo hello
"""
        }, check)


def test_prepare_use_command_no_env_specs():
    def check(dirname):
        env_var = conda_api.conda_prefix_variable()

        try:
            _push_fake_env_creator()
            project = Project(dirname)
            environ = minimal_environ()
            # we specify the command name but not the
            # env_spec_name but it should imply the proper env
            # spec name.
            result = prepare_without_interaction(project, environ=environ, command_name='hello')
            expected_path = project.env_specs['default'].path(project.directory_path)
            assert result.environ[env_var] == expected_path
        finally:
            _pop_fake_env_creator()

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME:
            """
name: blah
platforms: [linux-32,linux-64,osx-64,win-32,win-64]
commands:
    hello:
       unix: echo hello
       windows: echo hello
"""
        }, check)


def test_update_environ():
    def prepare_then_update_environ(dirname):
        project = project_no_dedicated_env(dirname)
        environ = minimal_environ(FOO='bar')
        result = prepare_without_interaction(project, environ=environ)
        assert result.errors == []
        assert result

        other = minimal_environ(BAR='baz')
        result.update_environ(other)
        assert dict(FOO='bar', BAR='baz', PROJECT_DIR=dirname) == strip_environ(other)

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
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
        stage.set_result(
            PrepareSuccess(statuses=(),
                           command_exec_info=None,
                           environ=dict(),
                           overrides=UserConfigOverrides(),
                           env_spec_name='first'), [])

        def last(stage):
            assert state['state'] == 'first'
            state['state'] = 'second'
            stage.set_result(
                PrepareFailure(statuses=(),
                               errors=[],
                               environ=dict(),
                               overrides=UserConfigOverrides(),
                               env_spec_name='last'), [])
            return None

        return _FunctionPrepareStage(dict(), UserConfigOverrides(), "second", [], last)

    first_stage = _FunctionPrepareStage(dict(), UserConfigOverrides(), "first", [], do_first)

    def after(updated_statuses):
        raise RuntimeError("should not have been called")

    stage = _after_stage_success(first_stage, after)
    assert stage.overrides is first_stage.overrides
    assert isinstance(stage.environ, dict)
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
        stage.set_result(
            PrepareSuccess(statuses=(),
                           command_exec_info=None,
                           environ=dict(),
                           overrides=UserConfigOverrides(),
                           env_spec_name='foo'), [])

        def last(stage):
            assert state['state'] == 'first'
            state['state'] = 'second'
            stage.set_result(
                PrepareSuccess(statuses=(),
                               command_exec_info=None,
                               environ=dict(),
                               overrides=UserConfigOverrides(),
                               env_spec_name='bar'), [])
            return None

        return _FunctionPrepareStage(dict(), UserConfigOverrides(), "second", [], last)

    first_stage = _FunctionPrepareStage(dict(), UserConfigOverrides(), "first", [], do_first)

    def after(updated_statuses):
        assert state['state'] == 'second'
        state['state'] = 'after'

    stage = _after_stage_success(first_stage, after)

    assert stage.overrides is first_stage.overrides
    assert stage.description_of_action == first_stage.description_of_action
    assert stage.environ == first_stage.environ
    assert stage.statuses_before_execute is first_stage.statuses_before_execute
    stage.configure()  # checking it doesn't raise

    while stage is not None:
        next_stage = stage.execute()

        if hasattr(stage, '_stage'):
            assert stage.statuses_after_execute is stage._stage.statuses_after_execute
            assert stage.failed is stage._stage.failed

        result = stage.result
        if result.failed:
            assert stage.failed
            break
        else:
            assert not stage.failed
        stage = next_stage
    assert not result.failed
    assert state['state'] == 'after'


def _monkeypatch_download_file(monkeypatch, dirname, filename='MYDATA', checksum=None):
    from tornado import gen

    @gen.coroutine
    def mock_downloader_run(self):
        class Res:
            pass

        res = Res()
        res.code = 200
        with open(os.path.join(dirname, filename), 'w') as out:
            out.write('data')
        if checksum:
            self._hash = checksum
        raise gen.Return(res)

    monkeypatch.setattr("anaconda_project.internal.http_client.FileDownloader.run", mock_downloader_run)


def test_provide_whitelist(monkeypatch):
    def check(dirname):
        from anaconda_project.requirements_registry.requirements.conda_env import CondaEnvRequirement

        _monkeypatch_download_file(monkeypatch, dirname, filename="nope")

        no_foo = [('missing requirement to run this project: A downloaded file which is ' + 'referenced by FOO.'),
                  '  Environment variable FOO is not set.']

        # whitelist only the env req by class
        project = project_no_dedicated_env(dirname)
        environ = minimal_environ()
        result = prepare_without_interaction(project, provide_whitelist=(CondaEnvRequirement, ), environ=environ)
        assert result.errors == no_foo

        # whitelist by instance
        env_req = [req for req in project.requirements(None) if isinstance(req, CondaEnvRequirement)][0]
        result = prepare_without_interaction(project, provide_whitelist=(env_req, ), environ=environ)
        assert result.errors == no_foo

        # whitelist by variable name
        result = prepare_without_interaction(project, provide_whitelist=(env_req.env_var, ), environ=environ)
        assert result.errors == no_foo

        # whitelist the download
        result = prepare_without_interaction(project,
                                             provide_whitelist=(env_req, project.download_requirements(None)[0]),
                                             environ=environ)
        assert result.errors == []
        assert 'FOO' in result.environ

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
downloads:
  FOO: "http://example.com/nope"

"""}, check)
