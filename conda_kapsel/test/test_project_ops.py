# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import codecs
import os
from tornado import gen
import platform
import pytest
import tarfile
import zipfile

from conda_kapsel import project_ops
from conda_kapsel.conda_manager import (CondaManager, CondaEnvironmentDeviations, CondaManagerError,
                                        push_conda_manager_class, pop_conda_manager_class)
from conda_kapsel.project import Project
import conda_kapsel.prepare as prepare
from conda_kapsel.internal.test.tmpfile_utils import (with_directory_contents, with_temporary_script_commandline,
                                                      with_directory_contents_completing_project_file,
                                                      complete_project_file_content)
from conda_kapsel.local_state_file import LocalStateFile
from conda_kapsel.project_file import DEFAULT_PROJECT_FILENAME, ProjectFile
from conda_kapsel.test.project_utils import project_no_dedicated_env
from conda_kapsel.internal.test.test_conda_api import monkeypatch_conda_not_to_use_links
from conda_kapsel.test.fake_server import fake_server
import conda_kapsel.internal.keyring as keyring


def test_create(monkeypatch):
    def check_create(dirname):
        subdir = os.path.join(dirname, 'foo')

        # dir doesn't exist
        project = project_ops.create(subdir, make_directory=False)
        assert [("Project directory '%s' does not exist." % subdir)] == project.problems

        # failing to create the dir
        def mock_failed_makedirs(path):
            raise IOError("nope")

        monkeypatch.setattr('os.makedirs', mock_failed_makedirs)
        project = project_ops.create(subdir, make_directory=True)
        assert [("Project directory '%s' does not exist." % subdir)] == project.problems
        monkeypatch.undo()

        # failing to create the .kapselignore, but still create dir and kapsel.yml
        from codecs import open as real_open

        def mock_codecs_open(*args, **kwargs):
            if args[0].endswith(".kapselignore") and args[1] == 'w':
                raise IOError("nope")
            else:
                return real_open(*args, **kwargs)

        monkeypatch.setattr('codecs.open', mock_codecs_open)
        project = project_ops.create(subdir, make_directory=True)
        monkeypatch.undo()
        assert [] == project.problems
        assert os.path.isfile(os.path.join(subdir, DEFAULT_PROJECT_FILENAME))
        assert not os.path.isfile(os.path.join(subdir, ".kapselignore"))

        # add .kapselignore if we create again and it isn't there
        project = project_ops.create(subdir, make_directory=True)
        assert [] == project.problems
        assert os.path.isfile(os.path.join(subdir, DEFAULT_PROJECT_FILENAME))
        assert os.path.isfile(os.path.join(subdir, ".kapselignore"))

    with_directory_contents(dict(), check_create)


def test_create_with_properties():
    def check_create(dirname):
        project = project_ops.create(dirname,
                                     make_directory=False,
                                     name='hello',
                                     icon='something.png',
                                     description="Hello World")
        assert [] == project.problems
        assert os.path.isfile(os.path.join(dirname, DEFAULT_PROJECT_FILENAME))
        assert project.name == 'hello'
        assert project.icon == os.path.join(dirname, 'something.png')
        assert project.description == "Hello World"

    with_directory_contents({'something.png': 'not a real png'}, check_create)


def test_create_imports_environment_yml():
    def check_create(dirname):
        project = project_ops.create(dirname,
                                     make_directory=False,
                                     name='hello',
                                     icon='something.png',
                                     description="Hello World")
        assert [] == project.problems
        assert os.path.isfile(os.path.join(dirname, DEFAULT_PROJECT_FILENAME))

        assert sorted(list(project.env_specs.keys())) == sorted(['stuff', 'default'])
        spec = project.env_specs['stuff']
        assert spec.conda_packages == ('a', 'b')
        assert spec.pip_packages == ('foo', )
        assert spec.channels == ('bar', )

    with_directory_contents(
        {'something.png': 'not a real png',
         "environment.yml": """
name: stuff
dependencies:
 - a
 - b
 - pip:
   - foo
channels:
 - bar
"""}, check_create)


def test_create_with_invalid_environment_yml():
    def check_create(dirname):
        project = project_ops.create(dirname, make_directory=False)
        project_filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert ["%s: invalid package specification: b $ 1.0" % project_filename] == project.problems
        # we should NOT create the kapsel.yml if it would be broken
        assert not os.path.isfile(project_filename)

    with_directory_contents(
        {'something.png': 'not a real png',
         "environment.yml": """
name: stuff
dependencies:
 - b $ 1.0
"""}, check_create)


def test_set_properties():
    def check(dirname):
        project = project_ops.create(dirname, make_directory=False)
        assert [] == project.problems
        assert os.path.isfile(os.path.join(dirname, DEFAULT_PROJECT_FILENAME))

        assert project.name == os.path.basename(dirname)
        assert project.icon is None

        result = project_ops.set_properties(project, name='hello', icon='something.png', description="HELLOOOO")
        assert result

        assert project.name == 'hello'
        assert project.icon == os.path.join(dirname, 'something.png')
        assert project.description == "HELLOOOO"

        # set to Unicode
        result = project_ops.set_properties(project, name=u'hello', icon=u'something.png', description=u'HELLOOOO')
        assert result

        assert project.name == u'hello'
        assert project.icon == os.path.join(dirname, 'something.png')
        assert project.description == u"HELLOOOO"

    with_directory_contents({'something.png': 'not a real png'}, check)


def test_set_properties_with_project_file_problems():
    def check(dirname):
        project = Project(dirname)
        status = project_ops.set_properties(project, name='foo')
        assert not status
        assert ["variables section contains wrong value type 42, should be dict or list of requirements"
                ] == status.errors

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_set_invalid_name():
    def check(dirname):
        project = project_ops.create(dirname, make_directory=False)
        assert [] == project.problems
        assert os.path.isfile(os.path.join(dirname, DEFAULT_PROJECT_FILENAME))

        assert project.name == os.path.basename(dirname)
        assert project.icon is None

        result = project_ops.set_properties(project, name=' ')
        print(repr(result))
        assert not result
        assert 'Failed to set project properties.' == result.status_description
        assert ["%s: name: field is an empty or all-whitespace string." %
                (os.path.join(dirname, DEFAULT_PROJECT_FILENAME))] == result.errors

        assert [] == project.problems
        assert project.name == os.path.basename(dirname)
        assert project.icon is None

    with_directory_contents(dict(), check)


def test_set_invalid_icon():
    def check(dirname):
        project = project_ops.create(dirname, make_directory=False)
        assert [] == project.problems
        assert os.path.isfile(os.path.join(dirname, DEFAULT_PROJECT_FILENAME))

        assert project.name == os.path.basename(dirname)
        assert project.icon is None

        result = project_ops.set_properties(project, icon='foobar')
        assert not result
        assert 'Failed to set project properties.' == result.status_description
        assert ["Icon file %s does not exist." % os.path.join(dirname, 'foobar')] == result.errors

        assert [] == project.problems
        assert project.name == os.path.basename(dirname)
        assert project.icon is None

    with_directory_contents(dict(), check)


def test_add_variables():
    def check_add_var(dirname):
        project = project_no_dedicated_env(dirname)
        status = project_ops.add_variables(project, ['foo', 'baz'], dict(foo='bar'))
        assert status
        req = project.find_requirements(env_var='foo')[0]
        assert req.options['default'] == 'bar'

        req = project.find_requirements(env_var='baz')[0]
        assert req.options.get('default') is None

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ""}, check_add_var)


def test_add_variables_existing_download():
    def check_set_var(dirname):
        project = project_no_dedicated_env(dirname)
        project_ops.add_variables(project, ['foo', 'baz'])
        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        assert dict(foo=None, baz=None, preset=None) == re_loaded.get_value(['variables'])
        assert re_loaded.get_value(['downloads', 'datafile']) == 'http://localhost:8000/data.tgz'

        local_state = LocalStateFile.load_for_directory(dirname)
        assert local_state.get_value(['variables', 'foo']) is None
        assert local_state.get_value(['variables', 'baz']) is None
        assert local_state.get_value(['variables', 'datafile']) is None

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('variables:\n'
                                    '  preset: null\n'
                                    'downloads:\n'
                                    '  datafile: http://localhost:8000/data.tgz')}, check_set_var)


def test_add_variables_existing_options():
    def check_set_var(dirname):
        project = project_no_dedicated_env(dirname)
        status = project_ops.add_variables(project,
                                           ['foo', 'baz', 'blah', 'woot', 'woot2'],
                                           dict(foo='bar',
                                                baz='qux',
                                                woot2='updated'))
        assert status
        re_loaded = ProjectFile.load_for_directory(project.directory_path)

        foo = re_loaded.get_value(['variables', 'foo'])
        assert isinstance(foo, dict)
        assert 'something' in foo
        assert foo['something'] == 42

        baz = re_loaded.get_value(['variables', 'baz'])
        assert isinstance(baz, dict)
        assert 'default' in baz
        assert baz['default'] == 'qux'

        blah = re_loaded.get_value(['variables', 'blah'])
        assert isinstance(blah, dict)
        assert 'default' in blah
        assert blah['default'] == 'unchanged'

        woot = re_loaded.get_value(['variables', 'woot'])
        assert woot == 'world'

        woot2 = re_loaded.get_value(['variables', 'woot2'])
        assert woot2 == 'updated'

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('variables:\n'
                                    '  foo: { something: 42 }\n'
                                    '  baz: { default: "hello" }\n'
                                    '  blah: { default: "unchanged" }\n'
                                    '  woot: "world"\n'
                                    '  woot2: "changed"\n'
                                    'downloads:\n'
                                    '  datafile: http://localhost:8000/data.tgz')}, check_set_var)


def test_remove_variables():
    def check_remove_var(dirname):
        project = project_no_dedicated_env(dirname)
        project_ops.remove_variables(project, ['foo', 'bar'])
        re_loaded = project.project_file.load_for_directory(project.directory_path)
        assert dict() == re_loaded.get_value(['variables'])
        assert re_loaded.get_value(['variables', 'foo']) is None
        assert re_loaded.get_value(['variables', 'bar']) is None
        local_state = LocalStateFile.load_for_directory(dirname)

        assert local_state.get_value(['variables', 'foo']) is None
        assert local_state.get_value(['variables', 'bar']) is None

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('variables:\n'
                                    '  foo: baz\n  bar: qux')}, check_remove_var)


def test_set_variables():
    def check_set_var(dirname):
        project = project_no_dedicated_env(dirname)
        status = project_ops.add_variables(project, ['foo', 'baz'], dict(foo='no', baz='nope'))
        assert status

        local_state = LocalStateFile.load_for_directory(dirname)
        assert local_state.get_value(['variables', 'foo']) is None
        assert local_state.get_value(['variables', 'baz']) is None

        status = project_ops.set_variables(project, [('foo', 'bar'), ('baz', 'qux')])
        assert status

        local_state = LocalStateFile.load_for_directory(dirname)
        assert local_state.get_value(['variables', 'foo']) == 'bar'
        assert local_state.get_value(['variables', 'baz']) == 'qux'

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('variables:\n'
                                    '  preset: null')}, check_set_var)


def test_set_variables_nonexistent():
    def check_set_var(dirname):
        project = project_no_dedicated_env(dirname)

        status = project_ops.set_variables(project, [('foo', 'bar'), ('baz', 'qux')])
        assert not status
        assert status.status_description == "Could not set variables."
        assert status.errors == ["Variable foo does not exist in the project.",
                                 "Variable baz does not exist in the project."]

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ''}, check_set_var)


def test_set_variables_cannot_create_environment(monkeypatch):
    def mock_create(prefix, pkgs, channels):
        from conda_kapsel.internal import conda_api
        raise conda_api.CondaError("error_from_conda_create")

    monkeypatch.setattr('conda_kapsel.internal.conda_api.create', mock_create)

    def check_set_var(dirname):
        project = Project(dirname)

        status = project_ops.set_variables(project, [('foo', 'bar'), ('baz', 'qux')])
        assert not status
        expected_env_path = os.path.join(dirname, 'envs', 'default')
        assert status.status_description == ("'%s' doesn't look like it contains a Conda environment yet." %
                                             expected_env_path)
        assert status.errors == ["Failed to create environment at %s: error_from_conda_create" % expected_env_path]

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ''}, check_set_var)


def test_unset_variables():
    def check_unset_var(dirname):
        project = project_no_dedicated_env(dirname)
        status = project_ops.add_variables(project, ['foo', 'baz'])
        assert status

        status = project_ops.set_variables(project, [('foo', 'no'), ('baz', 'nope')])
        assert status

        local_state = LocalStateFile.load_for_directory(dirname)
        assert local_state.get_value(['variables', 'foo']) == 'no'
        assert local_state.get_value(['variables', 'baz']) == 'nope'

        status = project_ops.unset_variables(project, ['foo', 'baz'])
        assert status

        local_state = LocalStateFile.load_for_directory(dirname)
        assert local_state.get_value(['variables', 'foo']) is None
        assert local_state.get_value(['variables', 'baz']) is None

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('variables:\n'
                                    '  preset: null')}, check_unset_var)


def test_set_and_unset_variables_encrypted():
    keyring.reset_keyring_module()

    def check_set_var(dirname):
        project = project_no_dedicated_env(dirname)
        status = project_ops.add_variables(project,
                                           ['foo_PASSWORD', 'baz_SECRET'],
                                           dict(foo_PASSWORD='no',
                                                baz_SECRET='nope'))
        assert status

        local_state = LocalStateFile.load_for_directory(dirname)
        assert local_state.get_value(['variables', 'foo_PASSWORD']) is None
        assert local_state.get_value(['variables', 'baz_SECRET']) is None

        assert set(keyring.fallback_data().values()) == set()

        status = project_ops.set_variables(project, [('foo_PASSWORD', 'bar'), ('baz_SECRET', 'qux')])
        assert status

        local_state = LocalStateFile.load_for_directory(dirname)
        # the encrypted variables are NOT in local state
        assert local_state.get_value(['variables', 'foo_PASSWORD']) is None
        assert local_state.get_value(['variables', 'baz_SECRET']) is None

        assert set(keyring.fallback_data().values()) == set(['bar', 'qux'])

        status = project_ops.unset_variables(project, ['foo_PASSWORD', 'baz_SECRET'])
        assert status

        assert set(keyring.fallback_data().values()) == set()

    try:
        keyring.enable_fallback_keyring()
        with_directory_contents_completing_project_file(
            {DEFAULT_PROJECT_FILENAME: ('variables:\n'
                                        '  preset: null')}, check_set_var)
    finally:
        keyring.disable_fallback_keyring()


def test_set_and_unset_variables_some_encrypted():
    keyring.reset_keyring_module()

    def check_set_var(dirname):
        project = project_no_dedicated_env(dirname)
        status = project_ops.add_variables(project,
                                           ['foo_PASSWORD', 'baz_SECRET', 'woo'],
                                           dict(foo_PASSWORD='no',
                                                baz_SECRET='nope',
                                                woo='something'))
        assert status

        local_state = LocalStateFile.load_for_directory(dirname)
        assert local_state.get_value(['variables', 'foo_PASSWORD']) is None
        assert local_state.get_value(['variables', 'baz_SECRET']) is None
        assert local_state.get_value(['variables', 'woo']) is None

        assert set(keyring.fallback_data().values()) == set()

        status = project_ops.set_variables(project, [('foo_PASSWORD', 'bar'), ('baz_SECRET', 'qux'), ('woo', 'w00t')])
        assert status

        local_state = LocalStateFile.load_for_directory(dirname)
        # the encrypted variables are NOT in local state
        assert local_state.get_value(['variables', 'foo_PASSWORD']) is None
        assert local_state.get_value(['variables', 'baz_SECRET']) is None
        assert local_state.get_value(['variables', 'woo']) == 'w00t'

        assert set(keyring.fallback_data().values()) == set(['bar', 'qux'])

        status = project_ops.unset_variables(project, ['foo_PASSWORD', 'baz_SECRET', 'woo'])
        assert status

        local_state = LocalStateFile.load_for_directory(dirname)
        assert set(keyring.fallback_data().values()) == set()
        assert local_state.get_value(['variables', 'woo']) is None

    try:
        keyring.enable_fallback_keyring()
        with_directory_contents_completing_project_file(
            {DEFAULT_PROJECT_FILENAME: ('variables:\n'
                                        '  preset: null')}, check_set_var)
    finally:
        keyring.disable_fallback_keyring()


def _test_add_command_line(command_type):
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        result = project_ops.add_command(project, 'default', command_type, 'echo "test"')
        assert result

        re_loaded = project.project_file.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'default'])
        assert command[command_type] == 'echo "test"'

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    %s: echo "pass"\n') % command_type}, check_add_command)


def test_add_command_shell():
    _test_add_command_line("unix")


def test_add_command_windows():
    _test_add_command_line("windows")


def _test_add_command_windows_to_shell(command_type):
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        result = project_ops.add_command(project, 'default', 'windows', 'echo "test"')
        assert result

        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'default'])
        assert command['windows'] == 'echo "test"'
        assert command['unix'] == 'echo "pass"'

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    unix: echo "pass"\n') % command_type}, check_add_command)


def test_add_command_bokeh():
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        result = project_ops.add_command(project, 'bokeh_test', 'bokeh_app', 'file.py')
        assert result

        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'bokeh_test'])
        assert len(command.keys()) == 2
        assert command['bokeh_app'] == 'file.py'
        assert command['env_spec'] == 'default'

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ""}, check_add_command)


def test_add_command_bokeh_overwrites():
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        result = project_ops.add_command(project, 'bokeh_test', 'bokeh_app', 'file.py')
        assert result

        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'bokeh_test'])
        assert len(command.keys()) == 2
        assert command['bokeh_app'] == 'file.py'
        assert command['env_spec'] == 'default'

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  bokeh_test:\n'
                                    '    bokeh_app: replaced.py\n')}, check_add_command)


def test_add_command_sets_env_spec():
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        result = project_ops.add_command(project, 'bokeh_test', 'bokeh_app', 'file.py', env_spec_name='foo')
        assert result

        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'bokeh_test'])
        assert command['bokeh_app'] == 'file.py'
        assert command['env_spec'] == 'foo'

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('env_specs:\n'
                                    '  foo: {}\n'
                                    'commands:\n'
                                    '  bokeh_test:\n'
                                    '    bokeh_app: replaced.py\n')}, check_add_command)


def test_add_command_leaves_env_spec():
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        result = project_ops.add_command(project, 'bokeh_test', 'bokeh_app', 'file.py', env_spec_name=None)
        assert result

        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'bokeh_test'])
        assert command['bokeh_app'] == 'file.py'
        assert command['env_spec'] == 'foo'

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('env_specs:\n'
                                    '  foo: {}\n'
                                    'commands:\n'
                                    '  bokeh_test:\n'
                                    '    env_spec: "foo"\n'
                                    '    bokeh_app: replaced.py\n')}, check_add_command)


def test_add_command_modifies_env_spec():
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        result = project_ops.add_command(project, 'bokeh_test', 'bokeh_app', 'file.py', env_spec_name='bar')
        if not result:
            assert result.errors == []  # prints the errors
        assert result

        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'bokeh_test'])
        assert command['bokeh_app'] == 'file.py'
        assert command['env_spec'] == 'bar'

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('env_specs:\n'
                                    '  foo: {}\n'
                                    '  bar: {}\n'
                                    'commands:\n'
                                    '  bokeh_test:\n'
                                    '    env_spec: "foo"\n'
                                    '    bokeh_app: replaced.py\n')}, check_add_command)


def test_add_command_leaves_supports_http_options():
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        result = project_ops.add_command(project,
                                         'bokeh_test',
                                         'bokeh_app',
                                         'file.py',
                                         env_spec_name=None,
                                         supports_http_options=None)
        assert result

        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'bokeh_test'])
        assert command['bokeh_app'] == 'file.py'
        assert command['env_spec'] == 'foo'
        assert command['supports_http_options'] is False

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('env_specs:\n'
                                    '  foo: {}\n'
                                    'commands:\n'
                                    '  bokeh_test:\n'
                                    '    supports_http_options: false\n'
                                    '    bokeh_app: replaced.py\n')}, check_add_command)


def test_add_command_leaves_supports_http_options_unset():
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        result = project_ops.add_command(project,
                                         'bokeh_test',
                                         'bokeh_app',
                                         'file.py',
                                         env_spec_name=None,
                                         supports_http_options=None)
        assert result

        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'bokeh_test'])
        assert command['bokeh_app'] == 'file.py'
        assert command['env_spec'] == 'foo'
        assert 'supports_http_options' not in command

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('env_specs:\n'
                                    '  foo: {}\n'
                                    'commands:\n'
                                    '  bokeh_test:\n'
                                    '    bokeh_app: replaced.py\n')}, check_add_command)


def test_add_command_modifies_supports_http_options():
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        result = project_ops.add_command(project,
                                         'bokeh_test',
                                         'bokeh_app',
                                         'file.py',
                                         env_spec_name=None,
                                         supports_http_options=True)
        assert result

        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'bokeh_test'])
        assert command['bokeh_app'] == 'file.py'
        assert command['env_spec'] == 'foo'
        assert command['supports_http_options'] is True

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('env_specs:\n'
                                    '  foo: {}\n'
                                    'commands:\n'
                                    '  bokeh_test:\n'
                                    '    supports_http_options: false\n'
                                    '    bokeh_app: replaced.py\n')}, check_add_command)


def test_add_command_invalid_type():
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        with pytest.raises(ValueError) as excinfo:
            project_ops.add_command(project, 'default', 'foo', 'echo "test"')
        assert 'Invalid command type foo' in str(excinfo.value)

    with_directory_contents_completing_project_file(dict(), check_add_command)


def test_add_command_conflicting_type():
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        result = project_ops.add_command(project, 'default', 'bokeh_app', 'myapp.py')
        assert [("%s: command 'default' has multiple commands in it, 'bokeh_app' can't go with 'unix'" %
                 project.project_file.filename)] == result.errors

        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'default'])
        assert command['unix'] == 'echo "pass"'
        assert 'bokeh_app' not in command

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    unix: echo "pass"\n')}, check_add_command)


def test_update_command_with_project_file_problems():
    def check(dirname):
        project = Project(dirname)
        status = project_ops.update_command(project, 'foo', 'unix', 'echo hello')

        assert not status
        assert ["variables section contains wrong value type 42, should be dict or list of requirements"
                ] == status.errors

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_update_command_invalid_type():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        with pytest.raises(ValueError) as excinfo:
            project_ops.update_command(project, 'default', 'foo', 'echo "test"')
        assert 'Invalid command type foo' in str(excinfo.value)

    with_directory_contents_completing_project_file(dict(), check)


def test_update_command_rename():
    file_content = complete_project_file_content('commands:\n  # this is a comment\n' +
                                                 '  foo:\n    # another comment\n    unix: echo "pass"\n')

    def check(dirname):
        project = project_no_dedicated_env(dirname)
        status = project_ops.update_command(project, 'foo', new_name='bar')
        print(status.status_description)
        print(status.errors)
        assert status

        project.project_file.load()
        with open(os.path.join(dirname, DEFAULT_PROJECT_FILENAME)) as proj_file:
            contents = proj_file.read()
            assert file_content.replace('foo:', 'bar:') == contents
            assert '# this is a comment' in contents
            assert '# another comment' in contents
        assert project.commands['bar']
        assert 'foo' not in project.commands

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: file_content}, check)


def test_update_command_no_command():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        with pytest.raises(ValueError) as excinfo:
            project_ops.update_command(project, 'default', 'bokeh_app')
        assert 'must also specify the command' in str(excinfo.value)

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    unix: echo "pass"\n')}, check)


def test_update_command_does_not_exist():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        result = project_ops.update_command(project, 'myapp', 'bokeh_app', 'myapp.py')
        assert not result

        assert ["No command 'myapp' found."] == result.errors

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    unix: echo "pass"\n')}, check)


def test_update_command_autogenerated():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        result = project_ops.update_command(project, 'foo.ipynb', 'bokeh_app', 'myapp.py')
        assert not result

        assert ["Autogenerated command 'foo.ipynb' can't be modified."] == result.errors

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    unix: echo "pass"\n'),
         "foo.ipynb": "stuff"}, check)


def test_update_command_conflicting_type():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.bokeh_app is None
        assert command.unix_shell_commandline == 'echo "pass"'

        result = project_ops.update_command(project, 'default', 'bokeh_app', 'myapp.py')
        assert result

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.bokeh_app == 'myapp.py'

        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'default'])
        assert command['bokeh_app'] == 'myapp.py'

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    unix: echo "pass"\n')}, check)


def test_update_command_same_type():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.unix_shell_commandline == 'echo "pass"'

        result = project_ops.update_command(project, 'default', 'unix', 'echo "blah"')
        assert result

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.unix_shell_commandline == 'echo "blah"'

        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'default'])
        assert command['unix'] == 'echo "blah"'

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    unix: echo "pass"\n')}, check)


def test_update_command_add_windows_alongside_shell():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.unix_shell_commandline == 'echo "pass"'

        result = project_ops.update_command(project, 'default', 'windows', 'echo "blah"')
        assert result

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.unix_shell_commandline == 'echo "pass"'
        assert command.windows_cmd_commandline == 'echo "blah"'

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    unix: echo "pass"\n')}, check)


def test_update_command_add_shell_alongside_windows():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.windows_cmd_commandline == 'echo "blah"'

        result = project_ops.update_command(project, 'default', 'unix', 'echo "pass"')
        assert result

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.unix_shell_commandline == 'echo "pass"'
        assert command.windows_cmd_commandline == 'echo "blah"'

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    windows: echo "blah"\n')}, check)


def test_update_command_empty_update():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.unix_shell_commandline == 'echo "pass"'

        result = project_ops.update_command(project, 'default')
        assert result

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.unix_shell_commandline == 'echo "pass"'

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    unix: echo "pass"\n')}, check)


def test_update_command_to_non_string_value():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.bokeh_app is None
        assert command.unix_shell_commandline == 'echo "pass"'

        result = project_ops.update_command(project, 'default', 'notebook', 42)
        assert not result
        assert [("%s: command 'default' attribute 'notebook' should be a string not '42'" %
                 project.project_file.filename)] == result.errors

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.unix_shell_commandline == 'echo "pass"'

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    unix: echo "pass"\n')}, check)


def _monkeypatch_download_file(monkeypatch, dirname, filename='MYDATA', checksum=None):
    @gen.coroutine
    def mock_downloader_run(self, loop):
        class Res:
            pass

        res = Res()
        res.code = 200
        with open(os.path.join(dirname, filename), 'w') as out:
            out.write('data')
        if checksum:
            self._hash = checksum
        raise gen.Return(res)

    monkeypatch.setattr("conda_kapsel.internal.http_client.FileDownloader.run", mock_downloader_run)


def _monkeypatch_download_file_fails(monkeypatch, dirname):
    @gen.coroutine
    def mock_downloader_run(self, loop):
        class Res:
            pass

        res = Res()
        res.code = 404
        raise gen.Return(res)

    monkeypatch.setattr("conda_kapsel.internal.http_client.FileDownloader.run", mock_downloader_run)


def _monkeypatch_download_file_fails_to_get_http_response(monkeypatch, dirname):
    @gen.coroutine
    def mock_downloader_run(self, loop):
        self._errors.append("Nope nope nope")
        raise gen.Return(None)

    monkeypatch.setattr("conda_kapsel.internal.http_client.FileDownloader.run", mock_downloader_run)


def test_add_download(monkeypatch):
    def check(dirname):
        _monkeypatch_download_file(monkeypatch, dirname)

        project = project_no_dedicated_env(dirname)
        status = project_ops.add_download(project, 'MYDATA', 'http://localhost:123456')

        assert os.path.isfile(os.path.join(dirname, "MYDATA"))
        assert status
        assert isinstance(status.logs, list)
        assert [] == status.errors

        # be sure download was added to the file and saved
        project2 = project_no_dedicated_env(dirname)
        assert {"url": 'http://localhost:123456'} == project2.project_file.get_value(['downloads', 'MYDATA'])

    with_directory_contents_completing_project_file(dict(), check)


def test_add_download_with_filename(monkeypatch):
    def check(dirname):
        FILENAME = 'TEST_FILENAME'
        _monkeypatch_download_file(monkeypatch, dirname, FILENAME)

        project = project_no_dedicated_env(dirname)
        status = project_ops.add_download(project, 'MYDATA', 'http://localhost:123456', FILENAME)

        assert os.path.isfile(os.path.join(dirname, FILENAME))
        assert status
        assert isinstance(status.logs, list)
        assert [] == status.errors

        # be sure download was added to the file and saved
        project2 = project_no_dedicated_env(dirname)
        requirement = project2.project_file.get_value(['downloads', 'MYDATA'])
        assert requirement['url'] == 'http://localhost:123456'
        assert requirement['filename'] == FILENAME

    with_directory_contents_completing_project_file(dict(), check)


def test_add_download_with_checksum(monkeypatch):
    def check(dirname):
        FILENAME = 'MYDATA'
        _monkeypatch_download_file(monkeypatch, dirname, checksum='DIGEST')

        project = project_no_dedicated_env(dirname)
        status = project_ops.add_download(project,
                                          'MYDATA',
                                          'http://localhost:123456',
                                          hash_algorithm='md5',
                                          hash_value='DIGEST')
        assert os.path.isfile(os.path.join(dirname, FILENAME))
        assert status
        assert isinstance(status.logs, list)
        assert [] == status.errors

        # be sure download was added to the file and saved
        project2 = project_no_dedicated_env(dirname)
        requirement = project2.project_file.get_value(['downloads', 'MYDATA'])
        assert requirement['url'] == 'http://localhost:123456'
        assert requirement['md5'] == 'DIGEST'

    with_directory_contents_completing_project_file(dict(), check)


def test_add_download_which_already_exists(monkeypatch):
    def check(dirname):
        _monkeypatch_download_file(monkeypatch, dirname, filename='foobar')

        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        assert dict(url='http://localhost:56789',
                    filename='foobar') == dict(project.project_file.get_value(['downloads', 'MYDATA']))

        status = project_ops.add_download(project, 'MYDATA', 'http://localhost:123456')

        assert os.path.isfile(os.path.join(dirname, "foobar"))
        assert status
        assert isinstance(status.logs, list)
        assert [] == status.errors

        # be sure download was added to the file and saved, and
        # the filename attribute was kept
        project2 = project_no_dedicated_env(dirname)
        assert dict(url='http://localhost:123456',
                    filename='foobar') == dict(project2.project_file.get_value(['downloads', 'MYDATA']))

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: 'downloads:\n    MYDATA: { url: "http://localhost:56789", filename: foobar }'},
        check)


def test_add_download_which_already_exists_with_fname(monkeypatch):
    def check(dirname):
        _monkeypatch_download_file(monkeypatch, dirname, filename='bazqux')

        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        assert dict(url='http://localhost:56789',
                    filename='foobar') == dict(project.project_file.get_value(['downloads', 'MYDATA']))

        status = project_ops.add_download(project, 'MYDATA', 'http://localhost:123456', filename="bazqux")

        assert os.path.isfile(os.path.join(dirname, "bazqux"))
        assert status
        assert isinstance(status.logs, list)
        assert [] == status.errors

        # be sure download was added to the file and saved, and
        # the filename attribute was kept
        project2 = project_no_dedicated_env(dirname)
        assert dict(url='http://localhost:123456',
                    filename='bazqux') == dict(project2.project_file.get_value(['downloads', 'MYDATA']))

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: 'downloads:\n    MYDATA: { url: "http://localhost:56789", filename: foobar }'},
        check)


def test_add_download_fails(monkeypatch):
    def check(dirname):
        _monkeypatch_download_file_fails(monkeypatch, dirname)

        project = project_no_dedicated_env(dirname)
        status = project_ops.add_download(project, 'MYDATA', 'http://localhost:123456')

        assert not os.path.isfile(os.path.join(dirname, "MYDATA"))
        assert not status
        assert isinstance(status.logs, list)
        assert ['Error downloading http://localhost:123456: response code 404'] == status.errors

        # be sure download was NOT added to the file
        project2 = project_no_dedicated_env(dirname)
        assert project2.project_file.get_value(['downloads', 'MYDATA']) is None
        # should have been dropped from the original project object also
        assert project.project_file.get_value(['downloads', 'MYDATA']) is None

    with_directory_contents_completing_project_file(dict(), check)


def test_add_download_fails_to_get_http_response(monkeypatch):
    def check(dirname):
        _monkeypatch_download_file_fails_to_get_http_response(monkeypatch, dirname)

        project = project_no_dedicated_env(dirname)
        status = project_ops.add_download(project, 'MYDATA', 'http://localhost:123456')

        assert not os.path.isfile(os.path.join(dirname, "MYDATA"))
        assert not status
        assert ['Nope nope nope'] == status.errors

        # be sure download was NOT added to the file
        project2 = project_no_dedicated_env(dirname)
        assert project2.project_file.get_value(['downloads', 'MYDATA']) is None
        # should have been dropped from the original project object also
        assert project.project_file.get_value(['downloads', 'MYDATA']) is None

    with_directory_contents_completing_project_file(dict(), check)


def test_add_download_with_project_file_problems():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        status = project_ops.add_download(project, 'MYDATA', 'http://localhost:123456')

        assert not os.path.isfile(os.path.join(dirname, "MYDATA"))
        assert not status
        assert ["variables section contains wrong value type 42, should be dict or list of requirements"
                ] == status.errors

        # be sure download was NOT added to the file
        project2 = project_no_dedicated_env(dirname)
        assert project2.project_file.get_value(['downloads', 'MYDATA']) is None
        # should have been dropped from the original project object also
        assert project.project_file.get_value(['downloads', 'MYDATA']) is None

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


# the other add_env_spec tests use a mock CondaManager, but we want to have
# one test that does the real thing to be sure it works.
def test_add_env_spec_with_real_conda_manager(monkeypatch):
    monkeypatch_conda_not_to_use_links(monkeypatch)

    def check(dirname):
        project = Project(dirname)
        status = project_ops.add_env_spec(project, name='foo', packages=['numpy'], channels=[])
        if not status:
            print(status.status_description)
            print(repr(status.errors))
        assert status

        # be sure it was really done
        project2 = Project(dirname)
        env_commented_map = project2.project_file.get_value(['env_specs', 'foo'])
        assert dict(packages=['numpy'], channels=[]) == dict(env_commented_map)
        assert os.path.isdir(os.path.join(dirname, 'envs', 'foo', 'conda-meta'))

    with_directory_contents_completing_project_file(dict(), check)


def _push_conda_test(fix_works, missing_packages, wrong_version_packages, remove_error):
    class TestCondaManager(CondaManager):
        def __init__(self):
            self.fix_works = fix_works
            self.fixed = False
            self.deviations = CondaEnvironmentDeviations(summary="test",
                                                         missing_packages=missing_packages,
                                                         wrong_version_packages=wrong_version_packages,
                                                         missing_pip_packages=(),
                                                         wrong_version_pip_packages=())

        def find_environment_deviations(self, prefix, spec):
            if self.fixed:
                return CondaEnvironmentDeviations(summary="fixed",
                                                  missing_packages=(),
                                                  wrong_version_packages=(),
                                                  missing_pip_packages=(),
                                                  wrong_version_pip_packages=())
            else:
                return self.deviations

        def fix_environment_deviations(self, prefix, spec, deviations=None):
            if self.fix_works:
                self.fixed = True

        def remove_packages(self, prefix, packages):
            if remove_error is not None:
                raise CondaManagerError(remove_error)

    push_conda_manager_class(TestCondaManager)


def _pop_conda_test():
    pop_conda_manager_class()


def _with_conda_test(f, fix_works=True, missing_packages=(), wrong_version_packages=(), remove_error=None):
    try:
        _push_conda_test(fix_works, missing_packages, wrong_version_packages, remove_error)
        f()
    finally:
        _pop_conda_test()


def test_add_env_spec():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            status = project_ops.add_env_spec(project, name='foo', packages=[], channels=[])
            assert status
            # with "None" for the args
            status = project_ops.add_env_spec(project, name='bar', packages=None, channels=None)
            assert status

        _with_conda_test(attempt)

        # be sure we really made the config changes
        project2 = Project(dirname)
        assert dict(packages=[], channels=[]) == dict(project2.project_file.get_value(['env_specs', 'foo']))
        assert dict(packages=[], channels=[]) == dict(project2.project_file.get_value(['env_specs', 'bar']))

    with_directory_contents_completing_project_file(dict(), check)


def test_add_env_spec_with_packages_and_channels():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            status = project_ops.add_env_spec(project,
                                              name='foo',
                                              packages=['a', 'b', 'c'],
                                              channels=['c1', 'c2', 'c3'])
            assert status

        _with_conda_test(attempt)

        # be sure download was added to the file and saved
        project2 = Project(dirname)
        assert dict(packages=['a', 'b', 'c'],
                    channels=['c1', 'c2', 'c3']) == dict(project2.project_file.get_value(['env_specs', 'foo']))

    with_directory_contents_completing_project_file(dict(), check)


def test_add_env_spec_extending_existing_lists():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            status = project_ops.add_env_spec(project,
                                              name='foo',
                                              packages=['a', 'b', 'c'],
                                              channels=['c1', 'c2', 'c3'])
            assert status

        _with_conda_test(attempt)

        # be sure download was added to the file and saved
        project2 = Project(dirname)
        assert dict(packages=['b', 'a', 'c'],
                    channels=['c3', 'c1', 'c2']) == dict(project2.project_file.get_value(['env_specs', 'foo']))

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
env_specs:
  foo:
    packages: [ 'b' ]
    channels: [ 'c3']
"""}, check)


def test_add_env_spec_extending_existing_lists_with_versions():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            status = project_ops.add_env_spec(project,
                                              name='foo',
                                              packages=['a', 'b=2.0', 'c'],
                                              channels=['c1', 'c2', 'c3'])
            assert status

        _with_conda_test(attempt)

        # be sure download was added to the file and saved
        project2 = Project(dirname)
        assert dict(packages=['b=2.0', 'a', 'c'],
                    channels=['c3', 'c1', 'c2']) == dict(project2.project_file.get_value(['env_specs', 'foo']))

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
env_specs:
  foo:
    packages: [ 'b=1.0' ]
    channels: [ 'c3']
"""}, check)


def test_add_packages_to_all_environments():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            status = project_ops.add_packages(project,
                                              env_spec_name=None,
                                              packages=['foo', 'bar'],
                                              channels=['hello', 'world'])
            assert status
            assert [] == status.errors

        _with_conda_test(attempt)

        # be sure we really made the config changes
        project2 = Project(dirname)
        assert ['foo', 'bar'] == list(project2.project_file.get_value('packages'))
        assert ['hello', 'world'] == list(project2.project_file.get_value('channels'))

    with_directory_contents_completing_project_file(dict(), check)


def test_add_packages_nonexistent_environment():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            status = project_ops.add_packages(project,
                                              env_spec_name="not_an_env",
                                              packages=['foo', 'bar'],
                                              channels=['hello', 'world'])
            assert not status
            assert [] == status.errors

        _with_conda_test(attempt)

    with_directory_contents_completing_project_file(dict(), check)


def test_add_packages_invalid_spec():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            status = project_ops.add_packages(project, env_spec_name=None, packages=['='], channels=[])
            assert not status
            assert 'Could not add packages.' == status.status_description
            assert ['Bad package specifications: =.'] == status.errors

        _with_conda_test(attempt)

    with_directory_contents_completing_project_file(dict(), check)


def test_remove_packages_from_all_environments():
    def check(dirname):
        def attempt():
            os.makedirs(os.path.join(dirname, 'envs', 'hello'))  # forces us to really run remove_packages
            project = Project(dirname)
            assert ['foo', 'bar', 'baz'] == list(project.project_file.get_value('packages'))
            assert ['foo', 'woot'] == list(project.project_file.get_value(['env_specs', 'hello', 'packages'], []))
            status = project_ops.remove_packages(project, env_spec_name=None, packages=['foo', 'bar'])
            assert status
            assert [] == status.errors

        _with_conda_test(attempt, remove_error="Removal fail")

        # be sure we really made the config changes
        project2 = Project(dirname)
        assert ['baz'] == list(project2.project_file.get_value('packages'))
        assert ['woot'] == list(project2.project_file.get_value(['env_specs', 'hello', 'packages']))

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
packages:
  - foo
  - bar
  - baz
env_specs:
  hello:
    packages:
     - foo
     - woot
"""}, check)


def test_remove_packages_from_one_environment():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            assert ['qbert', 'foo', 'bar'] == list(project.project_file.get_value('packages'))
            assert ['foo'] == list(project.project_file.get_value(['env_specs', 'hello', 'packages'], []))
            status = project_ops.remove_packages(project, env_spec_name='hello', packages=['foo', 'bar'])
            assert status
            assert [] == status.errors

        _with_conda_test(attempt)

        # be sure we really made the config changes
        project2 = Project(dirname)
        # note that hello will still inherit the deps from the global packages,
        # and that's fine
        assert ['qbert'] == list(project2.project_file.get_value('packages'))
        assert [] == list(project2.project_file.get_value(['env_specs', 'hello', 'packages'], []))

        # be sure we didn't delete comments from global packages section
        content = codecs.open(project2.project_file.filename, 'r', 'utf-8').read()
        assert '# this is a pre comment' in content
        assert '# this is a post comment' in content

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
packages:
  # this is a pre comment
  - qbert # this is a post comment
  - foo
  - bar
env_specs:
  hello:
    packages:
     - foo
"""}, check)


def test_remove_packages_from_one_environment_leaving_others_unaffected():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            assert ['qbert', 'foo', 'bar'] == list(project.project_file.get_value('packages'))
            assert ['foo'] == list(project.project_file.get_value(['env_specs', 'hello', 'packages'], []))
            status = project_ops.remove_packages(project, env_spec_name='hello', packages=['foo', 'bar'])
            assert status
            assert [] == status.errors

        _with_conda_test(attempt)

        # be sure we really made the config changes
        project2 = Project(dirname)
        assert ['qbert'] == list(project2.project_file.get_value('packages'))
        assert [] == list(project2.project_file.get_value(['env_specs', 'hello', 'packages'], []))
        assert set(['baz', 'foo', 'bar']) == set(project2.project_file.get_value(
            ['env_specs', 'another', 'packages'], []))
        assert project2.env_specs['another'].conda_package_names_set == set(['qbert', 'foo', 'bar', 'baz'])
        assert project2.env_specs['hello'].conda_package_names_set == set(['qbert'])

        # be sure we didn't delete comments from the env
        content = codecs.open(project2.project_file.filename, 'r', 'utf-8').read()
        assert '# this is a pre comment' in content
        assert '# this is a post comment' in content

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
packages:
  - qbert
  - foo
  - bar
env_specs:
  hello:
    packages:
     - foo
  another:
    packages:
     # this is a pre comment
     - baz # this is a post comment
"""}, check)


def test_remove_packages_from_nonexistent_environment():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            assert ['foo', 'bar'] == list(project.project_file.get_value('packages'))
            status = project_ops.remove_packages(project, env_spec_name='not_an_environment', packages=['foo', 'bar'])
            assert not status
            assert [] == status.errors
            assert "Environment spec not_an_environment doesn't exist." == status.status_description

        _with_conda_test(attempt)

        # be sure we didn't make the config changes
        project2 = Project(dirname)
        assert ['foo', 'bar'] == list(project2.project_file.get_value('packages'))

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
packages:
  - foo
  - bar
"""}, check)


def test_remove_packages_with_project_file_problems():
    def check(dirname):
        project = Project(dirname)
        status = project_ops.remove_packages(project, env_spec_name=None, packages=['foo'])

        assert not status
        assert ["variables section contains wrong value type 42, should be dict or list of requirements"
                ] == status.errors

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def _monkeypatch_can_connect_to_socket_on_standard_redis_port(monkeypatch):
    from conda_kapsel.plugins.network_util import can_connect_to_socket as real_can_connect_to_socket

    can_connect_args_list = []

    def mock_can_connect_to_socket(host, port, timeout_seconds=0.5):
        can_connect_args = dict()
        can_connect_args['host'] = host
        can_connect_args['port'] = port
        can_connect_args['timeout_seconds'] = timeout_seconds
        can_connect_args_list.append(can_connect_args)
        if port == 6379:
            return True
        else:
            return real_can_connect_to_socket(host, port, timeout_seconds)

    monkeypatch.setattr("conda_kapsel.plugins.network_util.can_connect_to_socket", mock_can_connect_to_socket)

    return can_connect_args_list


def test_add_service(monkeypatch):
    def check(dirname):
        _monkeypatch_can_connect_to_socket_on_standard_redis_port(monkeypatch)

        project = project_no_dedicated_env(dirname)
        status = project_ops.add_service(project, service_type='redis')

        assert status
        assert isinstance(status.logs, list)
        assert [] == status.errors

        # be sure service was added to the file and saved
        project2 = project_no_dedicated_env(dirname)
        assert 'redis' == project2.project_file.get_value(['services', 'REDIS_URL'])

    with_directory_contents_completing_project_file(dict(), check)


def test_add_service_nondefault_variable_name(monkeypatch):
    def check(dirname):
        _monkeypatch_can_connect_to_socket_on_standard_redis_port(monkeypatch)

        project = project_no_dedicated_env(dirname)
        status = project_ops.add_service(project, service_type='redis', variable_name='MY_SPECIAL_REDIS')

        assert status
        assert isinstance(status.logs, list)
        assert [] == status.errors

        # be sure service was added to the file and saved
        project2 = project_no_dedicated_env(dirname)
        assert 'redis' == project2.project_file.get_value(['services', 'MY_SPECIAL_REDIS'])

    with_directory_contents_completing_project_file(dict(), check)


def test_add_service_with_project_file_problems():
    def check(dirname):
        project = Project(dirname)
        status = project_ops.add_service(project, service_type='redis')

        assert not status
        assert ["variables section contains wrong value type 42, should be dict or list of requirements"
                ] == status.errors

        # be sure service was NOT added to the file
        project2 = Project(dirname)
        assert project2.project_file.get_value(['services', 'REDIS_URL']) is None
        # should have been dropped from the original project object also
        assert project.project_file.get_value(['services', 'REDIS_URL']) is None

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_add_service_already_exists(monkeypatch):
    def check(dirname):
        _monkeypatch_can_connect_to_socket_on_standard_redis_port(monkeypatch)

        project = project_no_dedicated_env(dirname)
        status = project_ops.add_service(project, service_type='redis')

        assert status
        assert isinstance(status.logs, list)
        assert [] == status.errors

        # be sure service was added to the file and saved
        project2 = Project(dirname)
        assert 'redis' == project2.project_file.get_value(['services', 'REDIS_URL'])

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, check)


def test_add_service_already_exists_with_different_type(monkeypatch):
    def check(dirname):
        _monkeypatch_can_connect_to_socket_on_standard_redis_port(monkeypatch)

        project = Project(dirname)
        status = project_ops.add_service(project, service_type='redis')

        assert not status
        # Once we have >1 known service types, we should change this test
        # to use the one other than redis and then this error will change.
        assert ["Service REDIS_URL has an unknown type 'foo'."] == status.errors

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: foo
"""}, check)


def test_add_service_already_exists_as_non_service(monkeypatch):
    def check(dirname):
        _monkeypatch_can_connect_to_socket_on_standard_redis_port(monkeypatch)

        project = Project(dirname)
        status = project_ops.add_service(project, service_type='redis')

        assert not status
        assert ['Variable REDIS_URL is already in use.'] == status.errors

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
variables:
  REDIS_URL: something
"""}, check)


def test_add_service_bad_service_type(monkeypatch):
    def check(dirname):
        _monkeypatch_can_connect_to_socket_on_standard_redis_port(monkeypatch)

        project = Project(dirname)
        status = project_ops.add_service(project, service_type='not_a_service')

        assert not status
        assert ["Unknown service type 'not_a_service', we know about: redis"] == status.errors

    with_directory_contents_completing_project_file(dict(), check)


def test_clean(monkeypatch):
    def mock_create(prefix, pkgs, channels):
        os.makedirs(os.path.join(prefix, "conda-meta"))

    monkeypatch.setattr('conda_kapsel.internal.conda_api.create', mock_create)

    def check(dirname):
        project = Project(dirname)

        result = prepare.prepare_without_interaction(project, env_spec_name='foo')

        assert result
        envs_dir = os.path.join(dirname, "envs")
        assert os.path.isdir(os.path.join(envs_dir, "foo"))

        # prepare again with 'bar' this time
        result = prepare.prepare_without_interaction(project, env_spec_name='bar')
        assert result
        bar_dir = os.path.join(dirname, "envs", "bar")
        assert os.path.isdir(bar_dir)

        # we don't really have a service in the test project file because
        # redis-server doesn't work on Windows and it's good to run this
        # test on Windows. So create some fake junk in services dir.
        services_dir = os.path.join(dirname, "services")
        os.makedirs(os.path.join(services_dir, "leftover-debris"))

        status = project_ops.clean(project, result)
        assert status
        assert status.status_description == "Cleaned."
        assert status.logs == [("Deleted environment files in %s." % bar_dir), ("Removing %s." % services_dir),
                               ("Removing %s." % envs_dir)]
        assert status.errors == []

        assert not os.path.isdir(os.path.join(dirname, "envs"))
        assert not os.path.isdir(os.path.join(dirname, "services"))

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
env_specs:
   foo: {}
   bar: {}
"""}, check)


def test_clean_failed_delete(monkeypatch):
    def mock_create(prefix, pkgs, channels):
        os.makedirs(os.path.join(prefix, "conda-meta"))

    monkeypatch.setattr('conda_kapsel.internal.conda_api.create', mock_create)

    def check(dirname):
        project = Project(dirname)

        result = prepare.prepare_without_interaction(project, env_spec_name='foo')

        assert result
        envs_dir = os.path.join(dirname, "envs")
        assert os.path.isdir(os.path.join(envs_dir, "foo"))

        # prepare again with 'bar' this time
        result = prepare.prepare_without_interaction(project, env_spec_name='bar')
        assert result
        bar_dir = os.path.join(dirname, "envs", "bar")
        assert os.path.isdir(bar_dir)

        # we don't really have a service in the test project file because
        # redis-server doesn't work on Windows and it's good to run this
        # test on Windows. So create some fake junk in services dir.
        services_dir = os.path.join(dirname, "services")
        os.makedirs(os.path.join(services_dir, "leftover-debris"))

        def mock_rmtree(path):
            raise IOError("No rmtree here")

        monkeypatch.setattr('shutil.rmtree', mock_rmtree)

        status = project_ops.clean(project, result)
        assert not status
        assert status.status_description == "Failed to clean everything up."
        assert status.logs == [("Removing %s." % services_dir), ("Removing %s." % envs_dir)]
        assert status.errors == [("Failed to remove environment files in %s: No rmtree here." % bar_dir),
                                 ("Error removing %s: No rmtree here." % services_dir),
                                 ("Error removing %s: No rmtree here." % envs_dir)]

        assert os.path.isdir(os.path.join(dirname, "envs"))
        assert os.path.isdir(os.path.join(dirname, "services"))

        # so with_directory_contents_completing_project_file can remove our tmp dir
        monkeypatch.undo()

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
env_specs:
   foo: {}
   bar: {}
"""}, check)


def _strip_prefixes(names):
    return list([name[len("archivedproj/"):] for name in names])


def _assert_zip_contains(zip_path, filenames):
    with zipfile.ZipFile(zip_path, mode='r') as zf:
        assert sorted(_strip_prefixes(zf.namelist())) == sorted(filenames)


def _assert_tar_contains(tar_path, filenames):
    with tarfile.open(tar_path, mode='r') as tf:
        assert sorted(_strip_prefixes(tf.getnames())) == sorted(filenames)


def _relative_to(root, path):
    prefix = root + os.sep
    assert path.startswith(prefix)
    return path[len(prefix):]


def _recursive_list(dir_path):
    for root, directories, filenames in os.walk(dir_path):
        for dir in directories:
            if not os.listdir(os.path.join(root, dir)):
                yield _relative_to(dir_path, os.path.join(root, dir))
        for filename in filenames:
            yield _relative_to(dir_path, os.path.join(root, filename))


def _assert_dir_contains(dir_path, filenames):
    assert sorted([filename.replace("\\", "/") for filename in _recursive_list(dir_path)]) == sorted(filenames)


def test_archive_zip():
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.zip")

        def check(dirname):
            # be sure we ignore these
            os.makedirs(os.path.join(dirname, "services"))
            os.makedirs(os.path.join(dirname, "envs"))

            project = project_no_dedicated_env(dirname)
            status = project_ops.archive(project, archivefile)

            assert status
            assert os.path.exists(archivefile)
            _assert_zip_contains(archivefile, ['a/b/c/d.py', 'a/b/c/e.py', 'emptydir/', 'foo.py', 'kapsel.yml',
                                               'kapsel-local.yml'])

            # overwriting should work
            status = project_ops.archive(project, archivefile)

            assert status
            assert os.path.exists(archivefile)
            _assert_zip_contains(archivefile, ['a/b/c/d.py', 'a/b/c/e.py', 'emptydir/', 'foo.py', 'kapsel.yml',
                                               'kapsel-local.yml'])

        with_directory_contents_completing_project_file(
            {DEFAULT_PROJECT_FILENAME: """
name: archivedproj
services:
   REDIS_URL: redis
    """,
             "foo.py": "print('hello')\n",
             "emptydir": None,
             "a/b/c/d.py": "",
             "a/b/c/e.py": ""}, check)

    with_directory_contents_completing_project_file(dict(), archivetest)


def test_archive_tar():
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.tar")

        def check(dirname):
            # be sure we ignore these
            os.makedirs(os.path.join(dirname, "services"))
            os.makedirs(os.path.join(dirname, "envs"))

            project = project_no_dedicated_env(dirname)
            status = project_ops.archive(project, archivefile)

            assert status
            assert os.path.exists(archivefile)
            _assert_tar_contains(archivefile, ['a/b/c/d.py', 'a/b/c/e.py', 'emptydir', 'foo.py', 'kapsel.yml',
                                               'kapsel-local.yml'])

            # overwriting should work
            status = project_ops.archive(project, archivefile)

            assert status
            assert os.path.exists(archivefile)
            _assert_tar_contains(archivefile, ['a/b/c/d.py', 'a/b/c/e.py', 'emptydir', 'foo.py', 'kapsel.yml',
                                               'kapsel-local.yml'])

        with_directory_contents_completing_project_file(
            {DEFAULT_PROJECT_FILENAME: """
name: archivedproj
services:
   REDIS_URL: redis
    """,
             "foo.py": "print('hello')\n",
             "emptydir": None,
             "a/b/c/d.py": "",
             "a/b/c/e.py": ""}, check)

    with_directory_contents_completing_project_file(dict(), archivetest)


def test_archive_tar_gz():
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.tar.gz")

        def check(dirname):
            # be sure we ignore these
            os.makedirs(os.path.join(dirname, "services"))
            os.makedirs(os.path.join(dirname, "envs"))

            project = project_no_dedicated_env(dirname)
            status = project_ops.archive(project, archivefile)

            assert status
            assert os.path.exists(archivefile)
            _assert_tar_contains(archivefile, ['a/b/c/d.py', 'a/b/c/e.py', 'emptydir', 'foo.py', 'kapsel.yml',
                                               'kapsel-local.yml'])

            # overwriting should work
            status = project_ops.archive(project, archivefile)

            assert status
            assert os.path.exists(archivefile)
            _assert_tar_contains(archivefile, ['a/b/c/d.py', 'a/b/c/e.py', 'emptydir', 'foo.py', 'kapsel.yml',
                                               'kapsel-local.yml'])

        with_directory_contents_completing_project_file(
            {DEFAULT_PROJECT_FILENAME: """
name: archivedproj
services:
   REDIS_URL: redis
    """,
             "foo.py": "print('hello')\n",
             "emptydir": None,
             "a/b/c/d.py": "",
             "a/b/c/e.py": ""}, check)

    with_directory_contents_completing_project_file(dict(), archivetest)


def test_archive_tar_bz2():
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.tar.bz2")

        def check(dirname):
            # be sure we ignore these
            os.makedirs(os.path.join(dirname, "services"))
            os.makedirs(os.path.join(dirname, "envs"))

            project = project_no_dedicated_env(dirname)
            status = project_ops.archive(project, archivefile)

            assert status
            assert os.path.exists(archivefile)
            _assert_tar_contains(archivefile, ['a/b/c/d.py', 'a/b/c/e.py', 'emptydir', 'foo.py', 'kapsel.yml',
                                               'kapsel-local.yml'])

            # overwriting should work
            status = project_ops.archive(project, archivefile)

            assert status
            assert os.path.exists(archivefile)
            _assert_tar_contains(archivefile, ['a/b/c/d.py', 'a/b/c/e.py', 'emptydir', 'foo.py', 'kapsel.yml',
                                               'kapsel-local.yml'])

        with_directory_contents_completing_project_file(
            {DEFAULT_PROJECT_FILENAME: """
name: archivedproj
services:
   REDIS_URL: redis
    """,
             "foo.py": "print('hello')\n",
             "emptydir": None,
             "a/b/c/d.py": "",
             "a/b/c/e.py": ""}, check)

    with_directory_contents_completing_project_file(dict(), archivetest)


def test_archive_cannot_write_destination_path(monkeypatch):
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.zip")

        def mock_ZipFile(*args, **kwargs):
            raise IOError("NOPE")

        monkeypatch.setattr('zipfile.ZipFile', mock_ZipFile)

        def check(dirname):
            # be sure we ignore this
            os.makedirs(os.path.join(dirname, "envs"))

            project = project_no_dedicated_env(dirname)
            status = project_ops.archive(project, archivefile)

            assert not status
            assert status.status_description == ('Failed to write project archive %s.' % archivefile)
            assert ['NOPE'] == status.errors

        with_directory_contents_completing_project_file(
            {DEFAULT_PROJECT_FILENAME: """
name: archivedproj
    """,
             "foo.py": "print('hello')\n"}, check)

    with_directory_contents_completing_project_file(dict(), archivetest)


def _add_empty_git(contents):
    contents.update({
        # I'm not sure these are all really needed for git to
        # recognize the directory as a git repo, but this is what
        # "git init" creates.
        '.git/branches': None,
        '.git/hooks': None,
        '.git/info': None,
        '.git/objects/info': None,
        '.git/objects/pack': None,
        '.git/refs/heads': None,
        '.git/refs/tags': None,
        '.git/config': """
[core]
        repositoryformatversion = 0
        filemode = true
        bare = false
        logallrefupdates = true
        """,
        '.git/description': "TestingGitRepository\n",
        '.git/HEAD': 'ref: refs/heads/master\n'
    })
    return contents


def test_archive_zip_with_gitignore():
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.zip")

        def check(dirname):
            # be sure we ignore this
            os.makedirs(os.path.join(dirname, "envs"))

            project = project_no_dedicated_env(dirname)
            status = project_ops.archive(project, archivefile)

            assert status
            assert os.path.exists(archivefile)
            _assert_zip_contains(archivefile, ['foo.py', '.gitignore', 'kapsel.yml', 'kapsel-local.yml'])

        with_directory_contents_completing_project_file(
            _add_empty_git({DEFAULT_PROJECT_FILENAME: """
name: archivedproj
        """,
                            "foo.py": "print('hello')\n",
                            '.gitignore': "/ignored.py\n/subdir\n/subwithslash/\n",
                            'ignored.py': 'print("ignore me!")',
                            'subdir/foo.py': 'foo',
                            'subdir/subsub/bar.py': 'bar',
                            'subwithslash/something.py': 'something'}), check)

    with_directory_contents_completing_project_file(dict(), archivetest)


def test_archive_zip_with_failing_git_command(monkeypatch):
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.zip")

        def check(dirname):
            # be sure we ignore this
            os.makedirs(os.path.join(dirname, "envs"))

            project = project_no_dedicated_env(dirname)

            from subprocess import check_output as real_check_output

            def mock_check_output(args, cwd):
                def run(commandline):
                    return real_check_output(commandline)

                return with_temporary_script_commandline("import sys\nsys.exit(1)\n", run)

            monkeypatch.setattr('subprocess.check_output', mock_check_output)

            status = project_ops.archive(project, archivefile)

            assert not status
            assert not os.path.exists(archivefile)
            # before the "." is the command output, but "false" has no output.
            assert status.errors == ["'git ls-files' failed to list ignored files: ."]

        with_directory_contents_completing_project_file(
            _add_empty_git({DEFAULT_PROJECT_FILENAME: """
        """,
                            "foo.py": "print('hello')\n"}), check)

    with_directory_contents_completing_project_file(dict(), archivetest)


def test_archive_zip_with_exception_executing_git_command(monkeypatch):
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.zip")

        def check(dirname):
            # be sure we ignore these
            os.makedirs(os.path.join(dirname, "services"))
            os.makedirs(os.path.join(dirname, "envs"))

            project = project_no_dedicated_env(dirname)

            from subprocess import check_output as real_check_output

            def mock_check_output(args, cwd):
                return real_check_output(args=['this-is-not-a-real-command'], cwd=cwd)

            monkeypatch.setattr('subprocess.check_output', mock_check_output)

            status = project_ops.archive(project, archivefile)

            assert not status
            assert not os.path.exists(archivefile)
            assert len(status.errors) == 1
            # full error message is platform-dependent
            assert status.errors[0].startswith("Failed to run 'git ls-files'")

        with_directory_contents_completing_project_file(
            _add_empty_git({DEFAULT_PROJECT_FILENAME: """
        """,
                            "foo.py": "print('hello')\n"}), check)

    with_directory_contents_completing_project_file(dict(), archivetest)


def test_archive_zip_with_inability_to_walk_directory(monkeypatch):
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.zip")

        def check(dirname):
            # be sure we ignore these
            os.makedirs(os.path.join(dirname, "services"))
            os.makedirs(os.path.join(dirname, "envs"))

            project = project_no_dedicated_env(dirname)
            assert project.problems == []

            def mock_os_walk(dirname):
                raise OSError("NOPE")

            monkeypatch.setattr('os.walk', mock_os_walk)

            status = project_ops.archive(project, archivefile)

            assert not status
            assert not os.path.exists(archivefile)
            assert status.status_description == "Failed to list files in the project."
            assert len(status.errors) > 0
            assert status.errors[0].startswith("Could not list files in")

        with_directory_contents_completing_project_file(
            _add_empty_git({DEFAULT_PROJECT_FILENAME: """
name: archivedproj
        """,
                            "foo.py": "print('hello')\n"}), check)

    with_directory_contents_completing_project_file(dict(), archivetest)


def test_archive_zip_with_unreadable_projectignore(monkeypatch):
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.zip")

        def check(dirname):
            # be sure we ignore these
            os.makedirs(os.path.join(dirname, "services"))
            os.makedirs(os.path.join(dirname, "envs"))

            project = project_no_dedicated_env(dirname)

            ignorefile = os.path.join(dirname, ".kapselignore")
            with codecs.open(ignorefile, 'w', 'utf-8') as f:
                f.write("\n")

            from codecs import open as real_open

            def mock_codecs_open(*args, **kwargs):
                if args[0].endswith(".kapselignore"):
                    raise IOError("NOPE")
                else:
                    return real_open(*args, **kwargs)

            monkeypatch.setattr('codecs.open', mock_codecs_open)

            status = project_ops.archive(project, archivefile)

            assert not status
            assert not os.path.exists(archivefile)
            assert ["Failed to read %s: NOPE" % ignorefile] == status.errors

        with_directory_contents_completing_project_file(
            _add_empty_git({DEFAULT_PROJECT_FILENAME: """
name: archivedproj
        """,
                            "foo.py": "print('hello')\n"}), check)

    with_directory_contents_completing_project_file(dict(), archivetest)


def test_archive_with_bogus_filename(monkeypatch):
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.bar")

        def check(dirname):
            project = project_no_dedicated_env(dirname)

            status = project_ops.archive(project, archivefile)

            assert not status
            assert not os.path.exists(archivefile)
            assert status.status_description == "Project archive filename must be a .zip, .tar.gz, or .tar.bz2."
            assert status.errors == ["Unsupported archive filename %s." % archivefile]

        with_directory_contents_completing_project_file(
            _add_empty_git({DEFAULT_PROJECT_FILENAME: """
name: archivedproj
        """,
                            "foo.py": "print('hello')\n"}), check)

    with_directory_contents_completing_project_file(dict(), archivetest)


def test_archive_zip_with_downloaded_file():
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.zip")

        def check(dirname):
            project = project_no_dedicated_env(dirname)
            status = project_ops.archive(project, archivefile)

            assert status
            assert os.path.exists(archivefile)
            _assert_zip_contains(archivefile, ['foo.py', 'kapsel.yml', 'kapsel-local.yml'])

        with_directory_contents_completing_project_file(
            _add_empty_git({DEFAULT_PROJECT_FILENAME: """
name: archivedproj
downloads:
   MYDOWNLOAD: "http://example.com/downloaded.py"
""",
                            "foo.py": "print('hello')\n",
                            'downloaded.py': 'print("ignore me!")',
                            'downloaded.py.part': ''}), check)

    with_directory_contents_completing_project_file(dict(), archivetest)


def test_archive_zip_overwrites_but_does_not_include_the_dest_zip():
    def check(dirname):
        project = project_no_dedicated_env(dirname)

        archivefile = os.path.join(dirname, "foo.zip")
        assert os.path.isfile(archivefile)

        status = project_ops.archive(project, archivefile)

        assert status
        assert os.path.exists(archivefile)

        _assert_zip_contains(archivefile, ['foo.py', 'kapsel.yml', 'kapsel-local.yml'])

        # re-archive to the same file
        status = project_ops.archive(project, archivefile)

        assert status
        assert os.path.exists(archivefile)

        _assert_zip_contains(archivefile, ['foo.py', 'kapsel.yml', 'kapsel-local.yml'])

    with_directory_contents_completing_project_file(
        _add_empty_git({DEFAULT_PROJECT_FILENAME: """
name: archivedproj
""",
                        "foo.py": "print('hello')\n",
                        'foo.zip': ""}), check)


def test_archive_zip_with_projectignore():
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.zip")

        def check(dirname):
            # be sure we ignore this
            os.makedirs(os.path.join(dirname, "envs"))

            project = project_ops.create(dirname)
            assert [] == project.problems
            status = project_ops.archive(project, archivefile)

            assert status
            assert os.path.exists(archivefile)
            _assert_zip_contains(archivefile, ['foo.py', 'kapsel.yml', '.kapselignore', 'bar/'])

        with_directory_contents_completing_project_file(
            {DEFAULT_PROJECT_FILENAME: """
name: archivedproj
        """,
             "foo.py": "print('hello')\n",
             "foo.pyc": "",
             ".ipynb_checkpoints": "",
             "bar/blah.pyc": ""}, check)

    with_directory_contents_completing_project_file(dict(), archivetest)


_CONTENTS_DIR = 1
_CONTENTS_FILE = 2
_CONTENTS_SYMLINK = 3


def _make_zip(archive_dest_dir, contents):
    archivefile = os.path.join(archive_dest_dir, "foo.zip")
    with zipfile.ZipFile(archivefile, 'w') as zf:
        for (key, what) in contents.items():
            if what is _CONTENTS_DIR:
                # create a directory
                if not key.endswith(os.sep):
                    key = key + os.sep
                zf.writestr(key, "")
            elif what is _CONTENTS_FILE:
                zf.writestr(key, "hello")
            else:
                raise AssertionError("can't put this in a zip")
    return archivefile


def _make_tar(archive_dest_dir, contents, compression=None):
    mode = 'w'
    extension = '.tar'
    if compression == 'gz':
        mode = mode + ':gz'
        extension = extension + '.gz'
    elif compression == 'bz2':
        mode = mode + ':bz2'
        extension = extension + '.bz2'

    # the tarfile API only lets us put in files, so we need
    # files to put in
    a_directory = os.path.join(archive_dest_dir, "a_directory")
    os.mkdir(a_directory)
    a_file = os.path.join(archive_dest_dir, "a_file")
    with open(a_file, 'w') as f:
        f.write("hello")
    a_symlink = os.path.join(archive_dest_dir, "a_link")
    if _CONTENTS_SYMLINK in contents.values():
        os.symlink("/somewhere", a_symlink)

    archivefile = os.path.join(archive_dest_dir, "foo" + extension)
    with tarfile.open(archivefile, mode) as tf:
        for (key, what) in contents.items():
            t = tarfile.TarInfo(key)
            if what is _CONTENTS_DIR:
                t.type = tarfile.DIRTYPE
            elif what is _CONTENTS_FILE:
                pass
            elif what is _CONTENTS_SYMLINK:
                t.type = tarfile.SYMTYPE
            tf.addfile(t)

    os.remove(a_file)
    os.rmdir(a_directory)
    if os.path.exists(a_symlink):
        os.remove(a_symlink)

    return archivefile


def _test_unarchive_tar(compression):
    def archivetest(archive_dest_dir):
        archivefile = _make_tar(archive_dest_dir,
                                {'a/a.txt': _CONTENTS_FILE,
                                 'a/q/b.txt': _CONTENTS_FILE,
                                 'a/c': _CONTENTS_DIR,
                                 'a': _CONTENTS_DIR},
                                compression=compression)
        # with tarfile.open(archivefile, 'r') as tf:
        #     tf.list()
        if compression is not None:
            assert archivefile.endswith(compression)

        def check(dirname):
            unpacked = os.path.join(dirname, "foo")
            status = project_ops.unarchive(archivefile, unpacked)

            assert status.errors == []
            assert status
            assert os.path.isdir(unpacked)
            _assert_dir_contains(unpacked, ['a.txt', 'c', 'q/b.txt'])

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_tar():
    _test_unarchive_tar(compression=None)


def test_unarchive_tar_gz():
    _test_unarchive_tar(compression='gz')


def test_unarchive_tar_bz2():
    _test_unarchive_tar(compression='bz2')


def test_unarchive_zip():
    def archivetest(archive_dest_dir):
        archivefile = _make_zip(archive_dest_dir, {'a/a.txt': _CONTENTS_FILE,
                                                   'a/q/b.txt': _CONTENTS_FILE,
                                                   'a/c': _CONTENTS_DIR,
                                                   'a': _CONTENTS_DIR})

        # with zipfile.ZipFile(archivefile, 'r') as zf:
        #    print(repr(zf.namelist()))

        def check(dirname):
            unpacked = os.path.join(dirname, "foo")
            status = project_ops.unarchive(archivefile, unpacked)

            assert status.errors == []
            assert status
            assert os.path.isdir(unpacked)
            _assert_dir_contains(unpacked, ['a.txt', 'c', 'q/b.txt'])
            assert status.project_dir == unpacked

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_zip_to_current_directory():
    def archivetest(archive_dest_dir):
        archivefile = _make_zip(archive_dest_dir, {'a/a.txt': _CONTENTS_FILE,
                                                   'a/q/b.txt': _CONTENTS_FILE,
                                                   'a/c': _CONTENTS_DIR,
                                                   'a': _CONTENTS_DIR})

        # with zipfile.ZipFile(archivefile, 'r') as zf:
        #    print(repr(zf.namelist()))

        def check(dirname):
            old = os.getcwd()
            try:
                os.chdir(dirname)
                status = project_ops.unarchive(archivefile, project_dir=None)
            finally:
                os.chdir(old)

            unpacked = os.path.join(dirname, "a")

            assert status.errors == []
            assert status
            assert os.path.isdir(unpacked)
            _assert_dir_contains(unpacked, ['a.txt', 'c', 'q/b.txt'])
            assert status.project_dir == unpacked

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_zip_to_parent_dir_with_auto_project_dir():
    def archivetest(archive_dest_dir):
        archivefile = _make_zip(archive_dest_dir, {'a/a.txt': _CONTENTS_FILE,
                                                   'a/q/b.txt': _CONTENTS_FILE,
                                                   'a/c': _CONTENTS_DIR})

        # with zipfile.ZipFile(archivefile, 'r') as zf:
        #    print(repr(zf.namelist()))

        def check(dirname):
            unpacked = os.path.join(dirname, "a")
            status = project_ops.unarchive(archivefile, project_dir=None, parent_dir=dirname)

            assert status.errors == []
            assert status
            assert os.path.isdir(unpacked)
            _assert_dir_contains(unpacked, ['a.txt', 'c', 'q/b.txt'])
            assert status.project_dir == unpacked

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_tar_to_parent_dir_with_auto_project_dir():
    def archivetest(archive_dest_dir):
        archivefile = _make_tar(archive_dest_dir, {'a/a.txt': _CONTENTS_FILE,
                                                   'a/q/b.txt': _CONTENTS_FILE,
                                                   'a/c': _CONTENTS_DIR})

        def check(dirname):
            unpacked = os.path.join(dirname, "a")
            status = project_ops.unarchive(archivefile, project_dir=None, parent_dir=dirname)

            assert status.errors == []
            assert status
            assert os.path.isdir(unpacked)
            _assert_dir_contains(unpacked, ['a.txt', 'c', 'q/b.txt'])
            assert status.project_dir == unpacked

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_error_on_dest_dir_exists():
    def archivetest(archive_dest_dir):
        archivefile = _make_tar(archive_dest_dir, {'a/a.txt': _CONTENTS_FILE})

        def check(dirname):
            unpacked = os.path.join(dirname, "foo")
            os.mkdir(unpacked)
            status = project_ops.unarchive(archivefile, unpacked)

            message = "Directory '%s' already exists." % unpacked
            assert status.errors == [message]
            assert not status

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_ignore_rmtree_fail_when_unzipping(monkeypatch):
    def archivetest(archive_dest_dir):
        archivefile = _make_zip(archive_dest_dir, {'a/a.txt': _CONTENTS_FILE})

        def check(dirname):
            unpacked = os.path.join(dirname, "foo")

            def mock_rmtree(*args, **kwargs):
                raise IOError("FAILURE")

            monkeypatch.setattr('shutil.rmtree', mock_rmtree)

            status = project_ops.unarchive(archivefile, unpacked)
            monkeypatch.undo()

            assert status
            assert os.path.isdir(unpacked)
            assert os.path.isfile(os.path.join(unpacked, "a.txt"))

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_error_on_bad_extension():
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.bar")
        with open(archivefile, 'w') as f:
            f.write("hello")

        def check(dirname):
            unpacked = os.path.join(dirname, "foo")
            status = project_ops.unarchive(archivefile, unpacked)

            message = "Unsupported archive filename %s, must be a .zip, .tar.gz, or .tar.bz2" % archivefile
            assert status.errors == [message]
            assert not status
            assert not os.path.isdir(unpacked)

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_error_on_corrupt_zip():
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.zip")
        with open(archivefile, 'w') as f:
            f.write("hello")

        def check(dirname):
            unpacked = os.path.join(dirname, "foo")
            status = project_ops.unarchive(archivefile, unpacked)

            message = "File is not a zip file"
            assert status.errors == [message]
            assert not status
            assert not os.path.isdir(unpacked)

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_error_on_corrupt_tar():
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.tar")
        with open(archivefile, 'w') as f:
            f.write("hello")

        def check(dirname):
            unpacked = os.path.join(dirname, "foo")
            status = project_ops.unarchive(archivefile, unpacked)

            message = "file could not be opened successfully"
            assert status.errors == [message]
            assert not status
            assert not os.path.isdir(unpacked)

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_error_on_nonexistent_tar():
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.tar")

        def check(dirname):
            unpacked = os.path.join(dirname, "foo")
            status = project_ops.unarchive(archivefile, unpacked)

            # the exact message here varies by OS so not checking
            assert len(status.errors) == 1
            assert not status
            assert not os.path.isdir(unpacked)

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_error_on_nonexistent_zip():
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.zip")

        def check(dirname):
            unpacked = os.path.join(dirname, "foo")
            status = project_ops.unarchive(archivefile, unpacked)

            # the exact message here varies by OS so not checking
            assert len(status.errors) == 1
            assert not status
            assert not os.path.isdir(unpacked)

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_tar_ignores_symlink():
    if platform.system() == 'Windows':
        print("Can't test tars with symlinks on Windows because there's no way to create one")
        return

    def archivetest(archive_dest_dir):
        archivefile = _make_tar(archive_dest_dir, {'a/a.txt': _CONTENTS_FILE,
                                                   'a/q/b.txt': _CONTENTS_FILE,
                                                   'a/c': _CONTENTS_DIR,
                                                   'a/link': _CONTENTS_SYMLINK})
        with tarfile.open(archivefile, 'r') as tf:
            member = tf.getmember('a/link')
            assert member is not None
            assert member.issym()

        def check(dirname):
            unpacked = os.path.join(dirname, "foo")
            status = project_ops.unarchive(archivefile, unpacked)

            assert status.errors == []
            assert status
            assert os.path.isdir(unpacked)
            _assert_dir_contains(unpacked, ['a.txt', 'c', 'q/b.txt'])

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_tar_error_on_relative_path():
    def archivetest(archive_dest_dir):
        archivefile = _make_tar(archive_dest_dir, {'a/../a.txt': _CONTENTS_FILE})

        def check(dirname):
            unpacked = os.path.join(dirname, "foo")
            status = project_ops.unarchive(archivefile, unpacked)

            assert not os.path.exists(unpacked)
            message = "Archive entry 'a/../a.txt' would end up at '%s' which is outside '%s'." % (os.path.join(
                dirname, "a.txt"), os.path.join(unpacked))
            assert status.errors == [message]
            assert not status

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_tar_error_on_root_relative_path():
    def archivetest(archive_dest_dir):
        archivefile = _make_tar(archive_dest_dir, {'../a.txt': _CONTENTS_FILE})

        def check(dirname):
            # root relative path fails when project_dir=None
            status = project_ops.unarchive(archivefile, project_dir=None, parent_dir=dirname)

            message = "Archive contains relative path '../a.txt' which is not allowed."
            assert status.errors == [message]
            assert not status

            # and also when it is specified
            unpacked = os.path.join(dirname, "foo")
            status = project_ops.unarchive(archivefile, project_dir=unpacked)

            message = "Archive contains relative path '../a.txt' which is not allowed."
            assert status.errors == [message]
            assert not status
            assert not os.path.isdir(unpacked)

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_zip_error_on_relative_path():
    def archivetest(archive_dest_dir):
        archivefile = _make_zip(archive_dest_dir, {'a/../a.txt': _CONTENTS_FILE})

        def check(dirname):
            unpacked = os.path.join(dirname, "foo")
            status = project_ops.unarchive(archivefile, unpacked)

            message = "Archive entry 'a/../a.txt' would end up at '%s' which is outside '%s'." % (os.path.join(
                dirname, "a.txt"), os.path.join(unpacked))
            assert status.errors == [message]
            assert not status
            assert not os.path.exists(unpacked)

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_zip_error_on_root_relative_path():
    def archivetest(archive_dest_dir):
        archivefile = _make_zip(archive_dest_dir, {'../a.txt': _CONTENTS_FILE})

        def check(dirname):
            # root relative path fails when project_dir=None
            status = project_ops.unarchive(archivefile, project_dir=None, parent_dir=dirname)

            message = "Archive contains relative path '../a.txt' which is not allowed."
            assert status.errors == [message]
            assert not status

            # and also when it is specified
            unpacked = os.path.join(dirname, "foo")
            status = project_ops.unarchive(archivefile, project_dir=unpacked)

            message = "Archive contains relative path '../a.txt' which is not allowed."
            assert status.errors == [message]
            assert not status
            assert not os.path.isdir(unpacked)

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_tar_error_on_no_directory():
    def archivetest(archive_dest_dir):
        archivefile = _make_tar(archive_dest_dir, {'a.txt': _CONTENTS_FILE})

        def check(dirname):
            unpacked = os.path.join(dirname, "foo")
            status = project_ops.unarchive(archivefile, unpacked)

            assert not os.path.exists(unpacked)
            message = "Archive does not contain a project directory or is empty."
            assert status.errors == [message]
            assert not status

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_tar_error_on_only_directory():
    def archivetest(archive_dest_dir):
        archivefile = _make_tar(archive_dest_dir, {'a': _CONTENTS_DIR})

        def check(dirname):
            unpacked = os.path.join(dirname, "foo")
            status = project_ops.unarchive(archivefile, unpacked)

            assert not os.path.exists(unpacked)
            message = "Archive does not contain a project directory or is empty."
            assert status.errors == [message]
            assert not status

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_tar_error_on_multiple_directories():
    def archivetest(archive_dest_dir):
        archivefile = _make_tar(archive_dest_dir, {'a/b.txt': _CONTENTS_FILE, 'c/d.txt': _CONTENTS_FILE})

        def check(dirname):
            unpacked = os.path.join(dirname, "foo")
            status = project_ops.unarchive(archivefile, unpacked)

            assert not os.path.exists(unpacked)
            message = "A valid project archive contains only one project directory " + \
                      "with all files inside that directory. 'c/d.txt' is outside 'a'."
            assert status.errors == [message]
            assert not status

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_tar_error_on_empty():
    def archivetest(archive_dest_dir):
        archivefile = _make_tar(archive_dest_dir, {})

        def check(dirname):
            unpacked = os.path.join(dirname, "foo")
            status = project_ops.unarchive(archivefile, unpacked)

            assert not os.path.exists(unpacked)
            message = "A valid project archive must contain at least one file."
            assert status.errors == [message]
            assert not status

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_zip_error_on_empty():
    def archivetest(archive_dest_dir):
        archivefile = _make_zip(archive_dest_dir, {})

        def check(dirname):
            unpacked = os.path.join(dirname, "foo")
            status = project_ops.unarchive(archivefile, unpacked)

            assert not os.path.exists(unpacked)
            message = "A valid project archive must contain at least one file."
            assert status.errors == [message]
            assert not status

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_abs_project_dir_with_parent_dir():
    with pytest.raises(ValueError) as excinfo:
        project_ops.unarchive("foo.tar.gz", "/absolute", "/bar")
    assert "If supplying parent_dir to unarchive, project_dir must be relative or None" == str(excinfo.value)


def test_unarchive_tar_error_on_writing_removes_dir(monkeypatch):
    def archivetest(archive_dest_dir):
        archivefile = _make_tar(archive_dest_dir, {'a/b.txt': _CONTENTS_FILE, 'a/c.txt': _CONTENTS_FILE})

        def check(dirname):
            unpacked = os.path.join(dirname, "foo")

            # this test is trying to prove that we clean up the dest
            # directory if we get IO errors partway through creating
            # it.
            state = dict(count=0)

            def mock_copyfileobj(*args, **kwargs):
                # assert that 'unpacked' exists at some point
                assert os.path.exists(unpacked)
                state['count'] = state['count'] + 1
                if state['count'] == 2:
                    raise IOError("Not copying second file")

            monkeypatch.setattr('tarfile.copyfileobj', mock_copyfileobj)

            status = project_ops.unarchive(archivefile, unpacked)

            assert state['count'] == 2
            assert not os.path.exists(unpacked)
            message = "Not copying second file"
            assert status.errors == [message]
            assert not status

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_unarchive_tar_error_on_writing_then_error_removing_dir(monkeypatch):
    def archivetest(archive_dest_dir):
        archivefile = _make_tar(archive_dest_dir, {'a/b.txt': _CONTENTS_FILE, 'a/c.txt': _CONTENTS_FILE})

        def check(dirname):
            unpacked = os.path.join(dirname, "foo")

            state = dict(count=0, rmtree_count=0)

            def mock_copyfileobj(*args, **kwargs):
                # assert that 'unpacked' exists at some point
                assert os.path.exists(unpacked)
                state['count'] = state['count'] + 1
                if state['count'] == 2:
                    raise IOError("Not copying second file")

            monkeypatch.setattr('tarfile.copyfileobj', mock_copyfileobj)

            # this test is trying to prove that we ignore an exception
            # from rmtree when cleaning up "unpacked"
            def mock_rmtree(path):
                assert os.path.exists(unpacked)
                state['rmtree_count'] = state['rmtree_count'] + 1
                raise IOError("rmtree failed")

            monkeypatch.setattr('shutil.rmtree', mock_rmtree)

            status = project_ops.unarchive(archivefile, unpacked)

            monkeypatch.undo()

            assert state['count'] == 2
            assert state['rmtree_count'] == 1
            assert os.path.exists(unpacked)  # since the rmtree failed
            message = "Not copying second file"
            assert status.errors == [message]
            assert not status

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_upload(monkeypatch):
    def check(dirname):
        with fake_server(monkeypatch, expected_basename='foo.tar.bz2'):
            project = project_no_dedicated_env(dirname)
            assert [] == project.problems
            status = project_ops.upload(project, site='unit_test')
            assert status
            assert status.url == 'http://example.com/whatevs'

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "name: foo\n",
         "foo.py": "print('hello')\n"}, check)


def test_upload_with_project_file_problems():
    def check(dirname):
        project = Project(dirname)
        status = project_ops.upload(project)
        assert not status
        assert ["variables section contains wrong value type 42, should be dict or list of requirements"
                ] == status.errors

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_upload_cannot_walk_directory(monkeypatch):
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        def mock_os_walk(dirname):
            raise OSError("NOPE")

        monkeypatch.setattr('os.walk', mock_os_walk)

        status = project_ops.upload(project, site='unit_test')
        assert not status
        assert status.errors[0].startswith("Could not list files in")

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: "name: foo\n",
         "foo.py": "print('hello')\n"}, check)
