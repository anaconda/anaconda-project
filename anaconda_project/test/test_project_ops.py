# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import codecs
import os
from tornado import gen
import platform
import pytest
import stat
import tarfile
import zipfile
import glob
import sys
from collections import OrderedDict

from anaconda_project import project_ops
from anaconda_project.conda_manager import (CondaManager, CondaEnvironmentDeviations, CondaLockSet, CondaManagerError,
                                            push_conda_manager_class, pop_conda_manager_class)
from anaconda_project.project import Project
import anaconda_project.prepare as prepare
from anaconda_project.internal.conda_api import current_platform
from anaconda_project.internal.test.tmpfile_utils import (with_directory_contents, with_temporary_script_commandline,
                                                          with_directory_contents_completing_project_file,
                                                          complete_project_file_content)
from anaconda_project.test.test_prepare import _monkeypatch_reduced_environment
from anaconda_project.local_state_file import LocalStateFile
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME, ProjectFile
from anaconda_project.project_lock_file import DEFAULT_PROJECT_LOCK_FILENAME
from anaconda_project.test.project_utils import project_no_dedicated_env
from anaconda_project.internal.test.fake_frontend import FakeFrontend
from anaconda_project.internal.test.test_conda_api import monkeypatch_conda_not_to_use_links
from anaconda_project.test.fake_server import fake_server
import anaconda_project.internal.keyring as keyring
import anaconda_project.internal.conda_api as conda_api
import anaconda_project.internal.plugins as plugins_api
from anaconda_project.internal.simple_status import SimpleStatus


@pytest.fixture()
def mocked_hash(monkeypatch):
    # Certain # tests are designed without explicitly specifying
    # the supported platform, which means that anaconda-project will
    # inject the default platforms into the yaml files.
    # If tests are run on non-default platforms (not linux-64, osx-64, win-64)
    # then the platforms list is amended with the current platform.
    # The logical_hash is computed with the platforms list so the hash
    # will change if it is run on a non-default platform.
    # The purpose of the mock (used in only select tests) is to provide
    # a hash without the platform list to allow the tests to run correctly
    # on non-default platforms.
    from anaconda_project.env_spec import EnvSpec
    old_compute_hash = EnvSpec._compute_hash

    def fake_hash(self, conda_packages, platforms):
        return old_compute_hash(self, conda_packages=conda_packages, platforms=())

    monkeypatch.setattr('anaconda_project.env_spec.EnvSpec._compute_hash', fake_hash)


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

        # failing to create the .projectignore, but still create dir and anaconda-project.yml
        from codecs import open as real_open

        def mock_codecs_open(*args, **kwargs):
            if args[0].endswith(".projectignore") and args[1] == 'w':
                raise IOError("nope")
            else:
                return real_open(*args, **kwargs)

        monkeypatch.setattr('codecs.open', mock_codecs_open)
        project = project_ops.create(subdir, make_directory=True)
        monkeypatch.undo()
        assert [] == project.problems
        assert os.path.isfile(os.path.join(subdir, DEFAULT_PROJECT_FILENAME))
        assert not os.path.isfile(os.path.join(subdir, ".projectignore"))

        # add .projectignore if we create again and it isn't there
        project = project_ops.create(subdir, make_directory=True)
        assert [] == project.problems
        assert os.path.isfile(os.path.join(subdir, DEFAULT_PROJECT_FILENAME))
        assert os.path.isfile(os.path.join(subdir, ".projectignore"))

        assert sorted(list(project.env_specs.keys())) == sorted(['default'])
        spec = project.env_specs['default']
        assert spec.conda_packages == ()
        assert spec.pip_packages == ()
        assert spec.channels == ()

        # Test the --with-anaconda-package flag
        project = project_ops.create(subdir, make_directory=True, with_anaconda_package=True)
        spec = project.env_specs['default']
        assert spec.conda_packages == ('anaconda', )
        assert spec.pip_packages == ()

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

        assert sorted(list(project.env_specs.keys())) == sorted(['stuff'])
        spec = project.env_specs['stuff']
        assert spec.conda_packages == ('a', 'b')
        assert spec.pip_packages == ('foo', )
        assert spec.channels == ('bar', )

    with_directory_contents(
        {
            'something.png': 'not a real png',
            "environment.yml": """
name: stuff
dependencies:
 - a
 - b
 - pip:
   - foo
channels:
 - bar
"""
        }, check_create)


def test_create_imports_environment_yml_when_project_yml_exists_and_fix_problems():
    def check_create(dirname):
        project = project_ops.create(dirname,
                                     make_directory=False,
                                     name='hello',
                                     icon='something.png',
                                     description="Hello World",
                                     fix_problems=True)
        assert [] == project.problems
        assert os.path.isfile(os.path.join(dirname, DEFAULT_PROJECT_FILENAME))

        assert sorted(list(project.env_specs.keys())) == sorted(['stuff'])
        spec = project.env_specs['stuff']
        assert spec.conda_packages == ('a', 'b')
        assert spec.pip_packages == ('foo', )
        assert spec.channels == ('bar', )

    with_directory_contents(
        {
            'something.png': 'not a real png',
            "anaconda-project.yml": """
name: foo
platforms: [linux-32,linux-64,osx-64,win-32,win-64]
""",
            "environment.yml": """
name: stuff
dependencies:
 - a
 - b
 - pip:
   - foo
channels:
 - bar
"""
        }, check_create)


def test_create_no_import_environment_yml_when_not_fix_problems():
    def check_create(dirname):
        project = project_ops.create(dirname,
                                     make_directory=False,
                                     name='hello',
                                     icon='something.png',
                                     description="Hello World",
                                     fix_problems=False)
        assert ["Environment spec 'stuff' from environment.yml is not in anaconda-project.yml."] == project.problems

    with_directory_contents(
        {
            'something.png': 'not a real png',
            "anaconda-project.yml": """
name: foo
platforms: [linux-32,linux-64,osx-64,win-32,win-64]
""",
            "environment.yml": """
name: stuff
dependencies:
 - a
 - b
 - pip:
   - foo
channels:
 - bar
"""
        }, check_create)


def test_create_with_invalid_environment_yml():
    def check_create(dirname):
        project = project_ops.create(dirname, make_directory=False)
        project_filename = os.path.join(dirname, DEFAULT_PROJECT_FILENAME)
        assert ["%s: invalid package specification: b $ 1.0" % DEFAULT_PROJECT_FILENAME] == project.problems
        # we should NOT create the anaconda-project.yml if it would be broken
        assert not os.path.isfile(project_filename)

    with_directory_contents(
        {
            'something.png': 'not a real png',
            "environment.yml": """
name: stuff
dependencies:
 - b $ 1.0
"""
        }, check_create)


def test_create_imports_notebook():
    def check_create(dirname):
        project = project_ops.create(dirname,
                                     make_directory=False,
                                     name='hello',
                                     description="Hello World",
                                     with_anaconda_package=True)
        assert [] == project.problems
        assert [] == project.suggestions
        assert os.path.isfile(os.path.join(dirname, DEFAULT_PROJECT_FILENAME))

        assert sorted(list(project.env_specs.keys())) == sorted(['default'])
        spec = project.env_specs['default']
        # we default to anaconda in the env
        assert spec.conda_packages == ('anaconda', )
        assert spec.channels == ()

        assert ['foo.ipynb'] == list(project.commands.keys())

    with_directory_contents({'foo.ipynb': '{}'}, check_create)


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
        assert [
            "%s: variables section contains wrong value type 42, should be dict or list of requirements" %
            project.project_file.basename
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
        assert ["%s: name: field is an empty or all-whitespace string." % (DEFAULT_PROJECT_FILENAME)] == result.errors

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
        status = project_ops.add_variables(project, None, ['foo', 'baz'], dict(foo='bar'))
        assert status
        req = project.find_requirements(project.default_env_spec_name, env_var='foo')[0]
        assert req.options['default'] == 'bar'

        req = project.find_requirements(project.default_env_spec_name, env_var='baz')[0]
        assert req.options.get('default') is None

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ""}, check_add_var)


def test_add_variables_to_env_spec():
    def check_add_var(dirname):
        project = project_no_dedicated_env(dirname)
        status = project_ops.add_variables(project, 'myspec', ['foo', 'baz'], dict(foo='bar'))
        assert status
        req = project.find_requirements('myspec', env_var='foo')[0]
        assert req.options['default'] == 'bar'

        assert [] == project.find_requirements('default', env_var='foo')
        assert [] == project.find_requirements('default', env_var='baz')

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
env_specs:
    default:
      packages: [python]
      channels: []
    myspec:
      packages: [python]
      channels: []
"""
        }, check_add_var)


def test_add_variables_bad_env_spec():
    def check_add_var(dirname):
        project = project_no_dedicated_env(dirname)
        status = project_ops.add_variables(project, 'nope', ['foo', 'baz'], dict(foo='bar'))
        assert "Environment spec nope doesn't exist." == status.status_description
        assert not status

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ""}, check_add_var)


def test_add_variables_existing_download():
    def check_set_var(dirname):
        project = project_no_dedicated_env(dirname)
        project_ops.add_variables(project, None, ['foo', 'baz'])
        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        assert dict(foo=None, baz=None, preset=None) == re_loaded.get_value(['variables'])
        assert re_loaded.get_value(['downloads', 'datafile']) == 'http://localhost:8000/data.tgz'

        local_state = LocalStateFile.load_for_directory(dirname)
        assert local_state.get_value(['variables', 'foo']) is None
        assert local_state.get_value(['variables', 'baz']) is None
        assert local_state.get_value(['variables', 'datafile']) is None

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: ('variables:\n'
                                       '  preset: null\n'
                                       'downloads:\n'
                                       '  datafile: http://localhost:8000/data.tgz')
        }, check_set_var)


def test_add_variables_existing_options():
    def check_set_var(dirname):
        project = project_no_dedicated_env(dirname)
        status = project_ops.add_variables(project, None, ['foo', 'baz', 'blah', 'woot', 'woot2'],
                                           dict(foo='bar', baz='qux', woot2='updated'))
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
        {
            DEFAULT_PROJECT_FILENAME: ('variables:\n'
                                       '  foo: { something: 42 }\n'
                                       '  baz: { default: "hello" }\n'
                                       '  blah: { default: "unchanged" }\n'
                                       '  woot: "world"\n'
                                       '  woot2: "changed"\n'
                                       'downloads:\n'
                                       '  datafile: http://localhost:8000/data.tgz')
        }, check_set_var)


def test_remove_variables():
    def check_remove_var(dirname):
        project = project_no_dedicated_env(dirname)
        project_ops.remove_variables(project, None, ['foo', 'bar'])
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


def test_remove_variables_with_env_spec():
    def check_remove_var(dirname):
        project = project_no_dedicated_env(dirname)

        pf = project.project_file
        assert pf.get_value(['env_specs', 'myspec', 'variables']) == dict(foo='baz', bar='qux')
        assert pf.get_value(['env_specs', 'myspec', 'variables', 'foo']) is not None
        assert pf.get_value(['env_specs', 'myspec', 'variables', 'bar']) is not None

        project_ops.remove_variables(project, 'myspec', ['foo', 'bar'])
        re_loaded = project.project_file.load_for_directory(project.directory_path)
        assert re_loaded.get_value(['env_specs', 'myspec', 'variables']) == {}
        assert re_loaded.get_value(['env_specs', 'myspec', 'variables', 'foo']) is None
        assert re_loaded.get_value(['env_specs', 'myspec', 'variables', 'bar']) is None

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
env_specs:
  default:
    packages: [python]
    channels: []
  myspec:
    packages: [python]
    channels: []
    variables:
      foo: baz
      bar: qux
        """
        }, check_remove_var)


def test_set_variables():
    def check_set_var(dirname):
        project = project_no_dedicated_env(dirname)
        status = project_ops.add_variables(project, None, ['foo', 'baz'], dict(foo='no', baz='nope'))
        assert status

        local_state = LocalStateFile.load_for_directory(dirname)
        assert local_state.get_value(['variables', 'foo']) is None
        assert local_state.get_value(['variables', 'baz']) is None

        status = project_ops.set_variables(project, None, [('foo', 'bar'), ('baz', 'qux')])
        assert status

        local_state = LocalStateFile.load_for_directory(dirname)
        assert local_state.get_value(['variables', 'foo']) == 'bar'
        assert local_state.get_value(['variables', 'baz']) == 'qux'

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ('variables:\n'
                                                                                '  preset: null')}, check_set_var)


def test_set_variables_nonexistent():
    def check_set_var(dirname):
        project = project_no_dedicated_env(dirname)

        status = project_ops.set_variables(project, None, [('foo', 'bar'), ('baz', 'qux')])
        assert not status
        assert status.status_description == "Could not set variables."
        assert status.errors == [
            "Variable foo does not exist in the project.", "Variable baz does not exist in the project."
        ]

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ''}, check_set_var)


def test_set_variables_cannot_create_environment(monkeypatch):
    def mock_create(prefix, pkgs, channels, stdout_callback, stderr_callback):
        from anaconda_project.internal import conda_api
        raise conda_api.CondaError("error_from_conda_create")

    monkeypatch.setattr('anaconda_project.internal.conda_api.create', mock_create)

    def check_set_var(dirname):
        project = Project(dirname)

        status = project_ops.set_variables(project, None, [('foo', 'bar'), ('baz', 'qux')])
        assert not status
        expected_env_path = os.path.join(dirname, 'envs', 'default')
        assert status.status_description == ("'%s' doesn't look like it contains a Conda environment yet." %
                                             expected_env_path)
        assert status.errors == ["Failed to create environment at %s: error_from_conda_create" % expected_env_path]

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ''}, check_set_var)


def test_unset_variables():
    def check_unset_var(dirname):
        project = project_no_dedicated_env(dirname)
        status = project_ops.add_variables(project, None, ['foo', 'baz'])
        assert status

        status = project_ops.set_variables(project, None, [('foo', 'no'), ('baz', 'nope')])
        assert status

        local_state = LocalStateFile.load_for_directory(dirname)
        assert local_state.get_value(['variables', 'foo']) == 'no'
        assert local_state.get_value(['variables', 'baz']) == 'nope'

        status = project_ops.unset_variables(project, None, ['foo', 'baz'])
        assert status

        local_state = LocalStateFile.load_for_directory(dirname)
        assert local_state.get_value(['variables', 'foo']) is None
        assert local_state.get_value(['variables', 'baz']) is None

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ('variables:\n'
                                                                                '  preset: null')}, check_unset_var)


def test_set_and_unset_variables_encrypted():
    keyring.reset_keyring_module()

    def check_set_var(dirname):
        project = project_no_dedicated_env(dirname)
        status = project_ops.add_variables(project, None, ['foo_PASSWORD', 'baz_SECRET'],
                                           dict(foo_PASSWORD='no', baz_SECRET='nope'))
        assert status

        local_state = LocalStateFile.load_for_directory(dirname)
        assert local_state.get_value(['variables', 'foo_PASSWORD']) is None
        assert local_state.get_value(['variables', 'baz_SECRET']) is None

        assert set(keyring.fallback_data().values()) == set()

        status = project_ops.set_variables(project, None, [('foo_PASSWORD', 'bar'), ('baz_SECRET', 'qux')])
        assert status

        local_state = LocalStateFile.load_for_directory(dirname)
        # the encrypted variables are NOT in local state
        assert local_state.get_value(['variables', 'foo_PASSWORD']) is None
        assert local_state.get_value(['variables', 'baz_SECRET']) is None

        assert set(keyring.fallback_data().values()) == set(['bar', 'qux'])

        status = project_ops.unset_variables(project, None, ['foo_PASSWORD', 'baz_SECRET'])
        assert status

        assert set(keyring.fallback_data().values()) == set()

    try:
        keyring.enable_fallback_keyring()
        with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ('variables:\n'
                                                                                    '  preset: null')}, check_set_var)
    finally:
        keyring.disable_fallback_keyring()


def test_set_and_unset_variables_some_encrypted():
    keyring.reset_keyring_module()

    def check_set_var(dirname):
        project = project_no_dedicated_env(dirname)
        status = project_ops.add_variables(project, None, ['foo_PASSWORD', 'baz_SECRET', 'woo'],
                                           dict(foo_PASSWORD='no', baz_SECRET='nope', woo='something'))
        assert status

        local_state = LocalStateFile.load_for_directory(dirname)
        assert local_state.get_value(['variables', 'foo_PASSWORD']) is None
        assert local_state.get_value(['variables', 'baz_SECRET']) is None
        assert local_state.get_value(['variables', 'woo']) is None

        assert set(keyring.fallback_data().values()) == set()

        status = project_ops.set_variables(project, None, [('foo_PASSWORD', 'bar'), ('baz_SECRET', 'qux'),
                                                           ('woo', 'w00t')])
        assert status

        local_state = LocalStateFile.load_for_directory(dirname)
        # the encrypted variables are NOT in local state
        assert local_state.get_value(['variables', 'foo_PASSWORD']) is None
        assert local_state.get_value(['variables', 'baz_SECRET']) is None
        assert local_state.get_value(['variables', 'woo']) == 'w00t'

        assert set(keyring.fallback_data().values()) == set(['bar', 'qux'])

        status = project_ops.unset_variables(project, None, ['foo_PASSWORD', 'baz_SECRET', 'woo'])
        assert status

        local_state = LocalStateFile.load_for_directory(dirname)
        assert set(keyring.fallback_data().values()) == set()
        assert local_state.get_value(['variables', 'woo']) is None

    try:
        keyring.enable_fallback_keyring()
        with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ('variables:\n'
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
        {
            DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                       '  bokeh_test:\n'
                                       '    bokeh_app: replaced.py\n'
                                       'packages:\n'
                                       '  - bokeh\n')
        }, check_add_command)


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
        {
            DEFAULT_PROJECT_FILENAME: ('env_specs:\n'
                                       '  foo: { "packages" : ["bokeh"] }\n'
                                       'commands:\n'
                                       '  bokeh_test:\n'
                                       '    bokeh_app: replaced.py\n')
        }, check_add_command)


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
        {
            DEFAULT_PROJECT_FILENAME: ('env_specs:\n'
                                       '  foo: { "packages" : ["bokeh"] }\n'
                                       'commands:\n'
                                       '  bokeh_test:\n'
                                       '    env_spec: "foo"\n'
                                       '    bokeh_app: replaced.py\n')
        }, check_add_command)


def test_add_command_generates_env_spec_suggestion():
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.problems == []
        assert project.suggestions == []
        # the 'bar' env spec does not have bokeh in it
        assert len(project.env_specs['bar'].conda_package_names_set) == 0
        # We are changing the env spec from 'foo' to 'bar'
        result = project_ops.add_command(project, 'bokeh_test', 'bokeh_app', 'file.py', env_spec_name='bar')
        if not result:
            assert result.errors == []  # prints the errors
        assert result

        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'bokeh_test'])
        assert command['bokeh_app'] == 'file.py'
        assert command['env_spec'] == 'bar'
        assert re_loaded.get_value(['env_specs', 'bar', 'packages']) is None

        assert project.problems == []
        assert project.suggestions == [('%s: Command ' % project.project_file.basename) +
                                       'bokeh_test uses env spec bar which does not have the packages: bokeh']

        project.fix_problems_and_suggestions()
        project.project_file.save()

        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        assert re_loaded.get_value(['env_specs', 'bar', 'packages']) == ['bokeh']

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: ('env_specs:\n'
                                       '  foo: { "packages" : ["bokeh"] }\n'
                                       '  bar: {}\n'
                                       'commands:\n'
                                       '  bokeh_test:\n'
                                       '    env_spec: "foo"\n'
                                       '    bokeh_app: replaced.py\n')
        }, check_add_command)


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
        {
            DEFAULT_PROJECT_FILENAME: ('env_specs:\n'
                                       '  foo: { "packages" : ["bokeh"] }\n'
                                       'commands:\n'
                                       '  bokeh_test:\n'
                                       '    supports_http_options: false\n'
                                       '    bokeh_app: replaced.py\n')
        }, check_add_command)


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
        {
            DEFAULT_PROJECT_FILENAME: ('env_specs:\n'
                                       '  foo: { "packages" : ["bokeh"] }\n'
                                       'commands:\n'
                                       '  bokeh_test:\n'
                                       '    bokeh_app: replaced.py\n')
        }, check_add_command)


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
        {
            DEFAULT_PROJECT_FILENAME: ('env_specs:\n'
                                       '  foo: { "packages" : ["bokeh"] }\n'
                                       'commands:\n'
                                       '  bokeh_test:\n'
                                       '    supports_http_options: false\n'
                                       '    bokeh_app: replaced.py\n')
        }, check_add_command)


def test_add_command_notebook():
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        result = project_ops.add_command(project, 'notebook_test', 'notebook', 'foo.ipynb')
        assert [] == result.errors
        assert result

        re_loaded = ProjectFile.load_for_directory(project.directory_path)
        command = re_loaded.get_value(['commands', 'notebook_test'])
        assert len(command.keys()) == 3
        assert command['notebook'] == 'foo.ipynb'
        assert command['env_spec'] == 'default'
        assert command['registers_fusion_function'] is True

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            "",
            'foo.ipynb':
            """
{
  "cells" : [ { "source" : [ "@fusion.register\\n", "def foo():\\n", "  pass\\n" ] } ]
}
                                                     """
        }, check_add_command)


def test_add_command_broken_notebook():
    def check_add_command(dirname):
        project = project_no_dedicated_env(dirname)
        result = project_ops.add_command(project, 'default', 'notebook', 'foo.ipynb')
        assert len(result.errors) > 0
        assert not result
        assert 'Failed to read or parse' in result.errors[0]
        assert result.status_description == 'Unable to add the command.'

    with_directory_contents_completing_project_file({"foo.ipynb": "not valid json"}, check_add_command)


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
                 project.project_file.basename)] == result.errors

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
        assert [
            "%s: variables section contains wrong value type 42, should be dict or list of requirements" %
            project.project_file.basename
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
        assert [
            ("%s: command 'default' attribute 'notebook' should be a string not '42'" % project.project_file.basename)
        ] == result.errors

        assert 'default' in project.commands
        command = project.commands['default']
        assert command.unix_shell_commandline == 'echo "pass"'

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: ('commands:\n'
                                    '  default:\n'
                                    '    unix: echo "pass"\n')}, check)


def _monkeypatch_download_file(monkeypatch, dirname, filename='MYDATA', checksum=None):
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


def _monkeypatch_download_file_fails(monkeypatch, dirname):
    @gen.coroutine
    def mock_downloader_run(self):
        class Res:
            pass

        res = Res()
        res.code = 404
        raise gen.Return(res)

    monkeypatch.setattr("anaconda_project.internal.http_client.FileDownloader.run", mock_downloader_run)


def _monkeypatch_download_file_fails_to_get_http_response(monkeypatch, dirname):
    @gen.coroutine
    def mock_downloader_run(self):
        self._errors.append("Nope nope nope")
        raise gen.Return(None)

    monkeypatch.setattr("anaconda_project.internal.http_client.FileDownloader.run", mock_downloader_run)


def test_add_download(monkeypatch):
    def check(dirname):
        _monkeypatch_download_file(monkeypatch, dirname)

        project = project_no_dedicated_env(dirname)
        status = project_ops.add_download(project, None, 'MYDATA', 'http://localhost:123456')

        assert os.path.isfile(os.path.join(dirname, "MYDATA"))
        assert status
        assert [] == status.errors

        # be sure download was added to the file and saved
        project2 = project_no_dedicated_env(dirname)
        assert {"url": 'http://localhost:123456'} == project2.project_file.get_value(['downloads', 'MYDATA'])

    with_directory_contents_completing_project_file(dict(), check)


def test_add_download_to_env_spec(monkeypatch):
    def check(dirname):
        _monkeypatch_download_file(monkeypatch, dirname)

        project = project_no_dedicated_env(dirname)
        status = project_ops.add_download(project, 'myspec', 'MYDATA', 'http://localhost:123456')

        assert os.path.isfile(os.path.join(dirname, "MYDATA"))
        assert status
        assert [] == status.errors

        # be sure download was added to the file and saved
        project2 = project_no_dedicated_env(dirname)
        assert {
            "url": 'http://localhost:123456'
        } == project2.project_file.get_value(['env_specs', 'myspec', 'downloads', 'MYDATA'])

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
env_specs:
    default:
      packages: [python]
      channels: []
    myspec:
      packages: [python]
      channels: []
        """
        }, check)


def test_add_download_with_filename(monkeypatch):
    def check(dirname):
        FILENAME = 'TEST_FILENAME'
        _monkeypatch_download_file(monkeypatch, dirname, FILENAME)

        project = project_no_dedicated_env(dirname)
        status = project_ops.add_download(project, None, 'MYDATA', 'http://localhost:123456', FILENAME)

        assert os.path.isfile(os.path.join(dirname, FILENAME))
        assert status
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
                                          None,
                                          'MYDATA',
                                          'http://localhost:123456',
                                          hash_algorithm='md5',
                                          hash_value='DIGEST')
        assert os.path.isfile(os.path.join(dirname, FILENAME))
        assert status
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

        status = project_ops.add_download(project, None, 'MYDATA', 'http://localhost:123456')

        assert os.path.isfile(os.path.join(dirname, "foobar"))
        assert status
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

        status = project_ops.add_download(project, None, 'MYDATA', 'http://localhost:123456', filename="bazqux")

        assert os.path.isfile(os.path.join(dirname, "bazqux"))
        assert status
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
        status = project_ops.add_download(project, None, 'MYDATA', 'http://localhost:123456')

        assert not os.path.isfile(os.path.join(dirname, "MYDATA"))
        assert not status
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
        status = project_ops.add_download(project, None, 'MYDATA', 'http://localhost:123456')

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
        status = project_ops.add_download(project, None, 'MYDATA', 'http://localhost:123456')

        assert not os.path.isfile(os.path.join(dirname, "MYDATA"))
        assert not status
        assert [
            "%s: variables section contains wrong value type 42, should be dict or list of requirements" %
            project.project_file.basename
        ] == status.errors

        # be sure download was NOT added to the file
        project2 = project_no_dedicated_env(dirname)
        assert project2.project_file.get_value(['downloads', 'MYDATA']) is None
        # should have been dropped from the original project object also
        assert project.project_file.get_value(['downloads', 'MYDATA']) is None

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_remove_download(monkeypatch):
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        status = project_ops.remove_download(project, None, 'MYDATA', prepare_result=None)

        assert status
        assert [] == status.errors

        # be sure it was removed
        project2 = project_no_dedicated_env(dirname)
        assert project2.project_file.get_value(['downloads', 'MYDATA']) is None
        assert not os.path.isfile(os.path.join(dirname, "MYDATA"))

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
downloads:
  MYDATA: "http://localhost:123456"
"""}, check)


def test_remove_download_with_prepare(monkeypatch):
    def check(dirname):
        _monkeypatch_download_file(monkeypatch, dirname)
        project = project_no_dedicated_env(dirname)
        result = prepare.prepare_without_interaction(project)
        assert result
        assert os.path.isfile(os.path.join(dirname, "MYDATA"))
        status = project_ops.remove_download(project, None, 'MYDATA', prepare_result=result)

        assert status
        assert [] == status.errors
        assert not os.path.isfile(os.path.join(dirname, "MYDATA"))

        # be sure download was removed
        project2 = project_no_dedicated_env(dirname)
        assert project2.project_file.get_value(['downloads', 'MYDATA']) is None

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
downloads:
  MYDATA: "http://localhost:123456"
"""}, check)


def test_remove_download_with_env_spec(monkeypatch):
    def check(dirname):
        config_path = ['env_specs', 'myspec', 'downloads', 'MYDATA']
        project = project_no_dedicated_env(dirname)
        assert "http://localhost:123456" == project.project_file.get_value(config_path)
        status = project_ops.remove_download(project, 'myspec', 'MYDATA', prepare_result=None)

        assert status
        assert [] == status.errors

        # be sure it was removed
        project2 = project_no_dedicated_env(dirname)
        assert project2.project_file.get_value(config_path) is None

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
env_specs:
    default:
      packages: [python]
      channels: []
    myspec:
      packages: [python]
      channels: []
      downloads:
        MYDATA: "http://localhost:123456"
"""
        }, check)


# the other add_env_spec tests use a mock CondaManager, but we want to have
# one test that does the real thing to be sure it works. Furthermore, we want
# to exercise the logic that ensures anaconda-project can properly pin package
# versions during intermediate install steps. To do so, we purposefully install
# a version of markupsafe that is incompatible with the latest version of jinja2, and
# then we add a latest version of jinja2. If anaconda-project does the right thing,
# conda will install an earlier version of jinja2 to respect the markupsafe version pin.
@pytest.mark.slow
def test_add_env_spec_with_real_conda_manager(monkeypatch):
    monkeypatch_conda_not_to_use_links(monkeypatch)
    _monkeypatch_reduced_environment(monkeypatch)

    def check(dirname):
        project = Project(dirname)

        status = project_ops.add_env_spec(project, name='foo', packages=['python=3.8'], channels=[])
        assert status, status.errors

        for spec in ['markupsafe<2.0.0', 'jinja2', 'pip']:
            status = project_ops.add_packages(project, 'foo', packages=[spec], channels=[])
            assert status, status.errors

            assert 'foo' in project.env_specs
            env = project.env_specs['foo']
            assert env.lock_set.enabled
            assert os.path.isfile(os.path.join(dirname, DEFAULT_PROJECT_LOCK_FILENAME))

            # be sure it was really done
            project2 = Project(dirname)
            env_commented_map = project2.project_file.get_value(['env_specs', 'foo'])
            assert spec in env_commented_map['packages'], env_commented_map['packages']

            # ensure markupsafe <2.0.0 is present in both passes
            meta_path = os.path.join(dirname, 'envs', 'foo', 'conda-meta')
            # pinned file no longer present between environment preparation steps
            assert os.path.isdir(meta_path)
            pinned = os.path.join(meta_path, 'pinned')
            assert not os.path.exists(pinned)
            # assert open(pinned, 'r').read() == specs[0]
            files = glob.glob(os.path.join(meta_path, 'markupsafe-1.*-*'))
            assert len(files) == 1, files
            version = os.path.basename(files[0]).split('-', 2)[1]
            assert tuple(map(int, version.split('.'))) < (2, 0, 0), files[0]

        status = project_ops.add_packages(project, 'foo', packages=['chardet'], pip=True, channels=[])
        assert status, status.errors
        project2 = Project(dirname)
        env_spec = project2.env_specs['foo']
        assert 'chardet' in env_spec.pip_packages, {'conda': env_spec.conda_packages, 'pip': env_spec.pip_packages}

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n",
            DEFAULT_PROJECT_FILENAME: "platforms: [linux-64,osx-64,osx-arm64,win-64]\n"
        }, check)


def _push_conda_test(fix_works, missing_packages, wrong_version_packages, remove_error, resolve_dependencies,
                     resolve_dependencies_error):
    class TestCondaManager(CondaManager):
        def __init__(self, frontend):
            self.fix_works = fix_works
            self.fixed = False
            self.deviations = CondaEnvironmentDeviations(summary="test deviation",
                                                         missing_packages=missing_packages,
                                                         wrong_version_packages=wrong_version_packages,
                                                         missing_pip_packages=(),
                                                         wrong_version_pip_packages=())

        def resolve_dependencies(self, package_specs, channels, platforms):
            if resolve_dependencies_error is not None:
                raise CondaManagerError(resolve_dependencies_error)
            else:
                return CondaLockSet(resolve_dependencies, platforms=platforms)

        def find_environment_deviations(self, prefix, spec):
            if self.fixed:
                return CondaEnvironmentDeviations(summary="fixed",
                                                  missing_packages=(),
                                                  wrong_version_packages=(),
                                                  missing_pip_packages=(),
                                                  wrong_version_pip_packages=())
            else:
                return self.deviations

        def fix_environment_deviations(self, prefix, spec, deviations=None, create=True):
            if self.fix_works:
                self.fixed = True

        def remove_packages(self, prefix, packages, pip=False):
            if remove_error is not None:
                raise CondaManagerError(remove_error)

    push_conda_manager_class(TestCondaManager)


def _pop_conda_test():
    pop_conda_manager_class()


def _with_conda_test(f,
                     fix_works=True,
                     missing_packages=(),
                     wrong_version_packages=(),
                     remove_error=None,
                     resolve_dependencies=None,
                     resolve_dependencies_error=None):
    try:
        if resolve_dependencies is None:
            resolve_dependencies = {'all': []}
        _push_conda_test(fix_works, missing_packages, wrong_version_packages, remove_error, resolve_dependencies,
                         resolve_dependencies_error)
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
        assert dict(locked=True,
                    env_spec_hash='a30f02c961ef4f3fe07ceb09e0906394c3885a79',
                    packages=dict(all=[]),
                    platforms=['linux-64', 'osx-64',
                               'win-64']) == dict(project2.lock_file.get_value(['env_specs', 'foo']))
        assert dict(locked=True,
                    env_spec_hash='a30f02c961ef4f3fe07ceb09e0906394c3885a79',
                    packages=dict(all=[]),
                    platforms=['linux-64', 'osx-64',
                               'win-64']) == dict(project2.lock_file.get_value(['env_specs', 'bar']))

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"}, check)


def test_add_env_spec_no_global_platforms(mocked_hash):
    def check(dirname):
        def attempt():
            project = Project(dirname)
            platforms = project.project_file.get_value(['platforms'])
            project.project_file.unset_value(['platforms'])
            project.project_file.set_value(['env_specs', 'default', 'platforms'], platforms)
            project.save()

            assert project.project_file.get_value(['platforms']) is None
            assert len(project.env_specs['default'].platforms) > 0

            status = project_ops.add_env_spec(project, name='foo', packages=[], channels=[])
            assert status

            assert conda_api.default_platforms_with_current() == project.env_specs['foo'].platforms

        _with_conda_test(attempt)

        # be sure we really made the config changes
        project2 = Project(dirname)
        assert dict(packages=[], channels=[], platforms=list(conda_api.default_platforms_with_current())) == dict(
            project2.project_file.get_value(['env_specs', 'foo']))

        assert dict(locked=True,
                    env_spec_hash='da39a3ee5e6b4b0d3255bfef95601890afd80709',
                    packages=dict(all=[]),
                    platforms=list(conda_api.default_platforms_with_current())) == dict(
                        project2.lock_file.get_value(['env_specs', 'foo']))

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"}, check)


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

        env_spec = project2.env_specs['foo']
        assert env_spec.name == 'foo'
        assert env_spec.lock_set.enabled
        assert env_spec.lock_set.equivalent_to(CondaLockSet({'all': []}, platforms=['linux-64', 'osx-64', 'win-64']))

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"}, check)


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


def test_add_env_spec_cannot_resolve_deps():
    def check(dirname):
        def attempt():
            project = Project(dirname, frontend=FakeFrontend())
            status = project_ops.add_env_spec(project, name='foo', packages=[], channels=[])
            assert status.status_description == "Error resolving dependencies for foo: NOPE."
            assert status.errors == []
            assert project.frontend.logs == []
            assert not status

        _with_conda_test(attempt, resolve_dependencies_error="NOPE")

        # be sure we didn't make the config changes
        project2 = Project(dirname)
        assert project2.project_file.get_value(['env_specs', 'foo']) is None
        assert project2.lock_file.get_value(['env_specs', 'foo']) is None

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"}, check)


def test_remove_env_spec():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            assert project.lock_file.get_value(['env_specs', 'hello'], None) is not None
            assert 'hello' in project.env_specs
            env = project.env_specs['hello']
            assert env.lock_set.enabled
            assert env.lock_set.package_specs_for_current_platform == ('a=1.0=1', )

            status = project_ops.remove_env_spec(project, name='hello')
            assert [] == status.errors
            assert status.status_description == "Nothing to clean up for environment 'hello'."
            assert status

            assert 'hello' not in project.env_specs

        _with_conda_test(attempt)

        # we should have cleaned up the lock file too
        project2 = Project(dirname)
        assert project2.lock_file.get_value(['env_specs', 'hello'], None) is None

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
name: foo
env_specs:
  hello:
   packages:
     - a
  another:
   packages:
     - b
    """,
            DEFAULT_PROJECT_LOCK_FILENAME:
            """
locking_enabled: true
env_specs:
  hello:
    platforms: [linux-32,linux-64,osx-64,osx-arm64,win-32,win-64]
    packages:
      all:
      - a=1.0=1
"""
        }, check)


def test_remove_only_env_spec():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            assert 'hello' in project.env_specs

            status = project_ops.remove_env_spec(project, name='hello')
            assert [] == status.errors
            assert status.status_description == ("At least one environment spec is required; " +
                                                 "'hello' is the only one left.")
            assert not status

            assert 'hello' in project.env_specs

        _with_conda_test(attempt)

        # we should have cleaned up the lock file too
        project2 = Project(dirname)
        assert project2.lock_file.get_value(['env_specs', 'hello'], None) is None

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
name: foo
env_specs:
  hello:
   packages:
     - a
    """}, check)


def test_remove_env_spec_causes_problem():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            assert project.lock_file.get_value(['env_specs', 'hello'], None) is not None
            assert 'hello' in project.env_specs
            env = project.env_specs['hello']
            assert env.lock_set.enabled
            assert env.lock_set.package_specs_for_current_platform == ('a=1.0=1', )

            status = project_ops.remove_env_spec(project, name='hello')
            assert [("anaconda-project.yml: env_spec 'hello' for command 'default'" +
                     " does not appear in the env_specs section")] == status.errors
            assert status.status_description == "Unable to load the project."
            assert not status

            assert 'hello' in project.env_specs

        _with_conda_test(attempt)

        # we should not have made changes
        project2 = Project(dirname)
        assert project2.lock_file.get_value(['env_specs', 'hello'], None) is not None
        assert project2.project_file.get_value(['env_specs', 'hello'], None) is not None

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
name: foo
commands:
  default:
    unix: echo hi
    env_spec: hello
env_specs:
  hello:
   packages:
     - a
  another:
   packages:
     - b
    """,
            DEFAULT_PROJECT_LOCK_FILENAME:
            """
locking_enabled: true
env_specs:
  hello:
    platforms: [linux-32,linux-64,osx-64,osx-arm64,win-32,win-64]
    packages:
      all:
      - a=1.0=1
"""
        }, check)


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
        assert [dict(pip=[]), 'foo', 'bar'] == list(project2.project_file.get_value('packages'))
        assert ['hello', 'world'] == list(project2.project_file.get_value('channels'))

        for env_spec in project2.env_specs.values():
            assert env_spec.lock_set.enabled
            assert env_spec.lock_set.equivalent_to(CondaLockSet({'all': []}, platforms=['linux-64', 'osx-64',
                                                                                        'win-64']))

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
packages:
 - pip: [] # be sure we don't break with this in the list
                """,
            DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"
        }, check)


def test_add_pip_packages_to_all_environments():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            status = project_ops.add_packages(project,
                                              env_spec_name=None,
                                              packages=['foo', 'bar'],
                                              pip=True,
                                              channels=None)
            assert status
            assert [] == status.errors

        _with_conda_test(attempt)

        # be sure we really made the config changes
        project2 = Project(dirname)
        assert [
            dict(pip=['foo', 'bar']),
        ] == list(project2.project_file.get_value('packages'))
        # assert ['hello', 'world'] == list(project2.project_file.get_value('channels'))

        for env_spec in project2.env_specs.values():
            assert env_spec.lock_set.enabled
            assert env_spec.lock_set.equivalent_to(CondaLockSet({'all': []}, platforms=['linux-64', 'osx-64',
                                                                                        'win-64']))

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
packages:
 - pip: [] # be sure we don't break with this in the list
                """,
            DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"
        }, check)


def test_add_packages_cannot_resolve_deps():
    def check(dirname):
        def attempt():
            project = Project(dirname, frontend=FakeFrontend())
            status = project_ops.add_packages(project,
                                              env_spec_name=None,
                                              packages=['foo', 'bar'],
                                              channels=['hello', 'world'])
            assert status.status_description == "Error resolving dependencies for default: NOPE."
            assert status.errors == []
            assert project.frontend.logs == []
            assert not status

        _with_conda_test(attempt, resolve_dependencies_error="NOPE")

        # be sure we didn't make the config changes
        project2 = Project(dirname)
        assert project2.project_file.get_value('packages', None) is None
        assert project2.project_file.get_value('channels', None) is None

        for env_spec in project2.env_specs.values():
            assert env_spec.lock_set.enabled
            assert env_spec.lock_set.platforms == ()

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"}, check)


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
            for env_spec in project.env_specs.values():
                assert env_spec.lock_set.enabled
                assert env_spec.lock_set.platforms == ()

            assert ['foo', 'bar', 'baz'] == list(project.project_file.get_value('packages'))
            assert ['foo', 'woot'] == list(project.project_file.get_value(['env_specs', 'hello', 'packages'], []))
            status = project_ops.remove_packages(project, env_spec_name=None, packages=['foo', 'bar'])
            assert [] == status.errors
            assert status

        _with_conda_test(attempt, remove_error="Removal fail")

        # be sure we really made the config changes
        project2 = Project(dirname)
        assert ['baz'] == list(project2.project_file.get_value('packages'))
        assert ['woot'] == list(project2.project_file.get_value(['env_specs', 'hello', 'packages']))

        for env_spec in project2.env_specs.values():
            assert env_spec.lock_set.enabled
            assert env_spec.lock_set.equivalent_to(CondaLockSet({'all': []}, platforms=['linux-64', 'osx-64',
                                                                                        'win-64']))

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
packages:
  - foo
  - bar
  - baz
env_specs:
  hello:
    packages:
     - foo
     - woot
  hello2:
    packages:
     - foo
     - bar
     - pip: [] # make sure we don't choke on non-string items in list
        """,
            DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"
        }, check)


def test_remove_conda_packages_from_global_with_pip_packages():
    def check(dirname):
        def attempt():
            os.makedirs(os.path.join(dirname, 'envs', 'hello'))  # forces us to really run remove_packages
            project = Project(dirname)
            for env_spec in project.env_specs.values():
                assert env_spec.lock_set.enabled
                assert env_spec.lock_set.platforms == ()

            assert ['foo', 'bar', 'baz', OrderedDict([('pip', [])])] == list(project.project_file.get_value('packages'))
            assert ['foo', 'woot'] == list(project.project_file.get_value(['env_specs', 'hello', 'packages'], []))
            status = project_ops.remove_packages(project, env_spec_name=None, packages=['foo', 'bar'])
            assert [] == status.errors
            assert status

        _with_conda_test(attempt, remove_error="Removal fail")

        # be sure we really made the config changes
        project2 = Project(dirname)
        assert ['baz', OrderedDict([('pip', [])])] == list(project2.project_file.get_value('packages'))
        assert ['woot'] == list(project2.project_file.get_value(['env_specs', 'hello', 'packages']))

        for env_spec in project2.env_specs.values():
            assert env_spec.lock_set.enabled
            assert env_spec.lock_set.equivalent_to(CondaLockSet({'all': []}, platforms=['linux-64', 'osx-64',
                                                                                        'win-64']))

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
packages:
  - foo
  - bar
  - baz
  - pip: []
env_specs:
  hello:
    packages:
     - foo
     - woot
  hello2:
    packages:
     - foo
     - bar
     - pip: [] # make sure we don't choke on non-string items in list
        """,
            DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"
        }, check)


def test_remove_pip_packages_from_global():
    def check(dirname):
        def attempt():
            os.makedirs(os.path.join(dirname, 'envs', 'hello'))  # forces us to really run remove_packages
            project = Project(dirname)
            for env_spec in project.env_specs.values():
                assert env_spec.lock_set.enabled
                assert env_spec.lock_set.platforms == ()

            assert ['foo', OrderedDict([('pip', ['bar', 'baz'])])] == list(project.project_file.get_value('packages'))
            assert ['foo', OrderedDict([('pip', ['bar', 'woot'])])
                    ] == list(project.project_file.get_value(['env_specs', 'hello', 'packages'], []))
            status = project_ops.remove_packages(project, env_spec_name=None, packages=['bar'], pip=True)
            assert [] == status.errors
            assert status

        _with_conda_test(attempt, remove_error="Removal fail")

        # be sure we really made the config changes
        project2 = Project(dirname)
        assert ['foo', OrderedDict([('pip', ['baz'])])] == list(project2.project_file.get_value('packages'))
        assert ['foo', OrderedDict([('pip', ['woot'])])
                ] == list(project2.project_file.get_value(['env_specs', 'hello', 'packages']))

        for env_spec in project2.env_specs.values():
            assert env_spec.lock_set.enabled
            assert env_spec.lock_set.equivalent_to(CondaLockSet({'all': []}, platforms=['linux-64', 'osx-64',
                                                                                        'win-64']))

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
packages:
  - foo
  - pip:
    - bar
    - baz
env_specs:
  hello:
    packages:
     - foo
     - pip:
       - bar
       - woot
  hello2: {}
        """,
            DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"
        }, check)


def test_remove_pip_packages_from_one_environment():
    def check(dirname):
        def attempt():
            project = Project(dirname)

            for env_spec in project.env_specs.values():
                assert env_spec.lock_set.enabled
                assert env_spec.lock_set.platforms == ()

            assert ['qbert', OrderedDict([('pip', ['pbert', 'foo',
                                                   'bar'])])] == list(project.project_file.get_value('packages'))
            status = project_ops.remove_packages(project, env_spec_name='hello', packages=['foo', 'bar'], pip=True)
            assert status
            assert [] == status.errors

        _with_conda_test(attempt)

        # be sure we really made the config changes
        project2 = Project(dirname)
        # note that hello will still inherit the deps from the global packages,
        # and that's fine
        assert ['qbert', OrderedDict([('pip', ['pbert'])])] == list(project2.project_file.get_value('packages'))
        assert [OrderedDict([('pip', [])])
                ] == list(project2.project_file.get_value(['env_specs', 'hello', 'packages'], []))

        # be sure we didn't delete comments from global packages section
        content = codecs.open(project2.project_file.filename, 'r', 'utf-8').read()
        assert '# this is a pre comment' in content
        assert '# this is a post comment' in content

        for env_spec in project2.env_specs.values():
            if env_spec.name == 'hello':
                assert env_spec.lock_set.enabled
                assert env_spec.lock_set.equivalent_to(
                    CondaLockSet({'all': []}, platforms=['linux-64', 'osx-64', 'win-64']))
            else:
                assert env_spec.lock_set.enabled

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
packages:
  # this is a pre comment
  - qbert # this is a post comment
  - pip:
    - pbert
    - foo
    - bar
env_specs:
  hello:
    packages:
      - pip:
        - foo
        """,
            DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"
        }, check)


def test_remove_pip_packages_from_one_environment_with_pkgs():
    def check(dirname):
        def attempt():
            project = Project(dirname)

            for env_spec in project.env_specs.values():
                assert env_spec.lock_set.enabled
                assert env_spec.lock_set.platforms == ()

            assert ['qbert', OrderedDict([('pip', ['pbert', 'foo',
                                                   'bar'])])] == list(project.project_file.get_value('packages'))
            status = project_ops.remove_packages(project, env_spec_name='hello', packages=['foo', 'bar'], pip=True)
            assert status
            assert [] == status.errors

        _with_conda_test(attempt)

        # be sure we really made the config changes
        project2 = Project(dirname)
        # note that hello will still inherit the deps from the global packages,
        # and that's fine
        assert ['qbert', OrderedDict([('pip', ['pbert'])])] == list(project2.project_file.get_value('packages'))
        assert ['qbert', OrderedDict([('pip', [])])
                ] == list(project2.project_file.get_value(['env_specs', 'hello', 'packages'], []))

        # be sure we didn't delete comments from global packages section
        content = codecs.open(project2.project_file.filename, 'r', 'utf-8').read()
        assert '# this is a pre comment' in content
        assert '# this is a post comment' in content

        for env_spec in project2.env_specs.values():
            if env_spec.name == 'hello':
                assert env_spec.lock_set.enabled
                assert env_spec.lock_set.equivalent_to(
                    CondaLockSet({'all': []}, platforms=['linux-64', 'osx-64', 'win-64']))
            else:
                assert env_spec.lock_set.enabled

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
packages:
  # this is a pre comment
  - qbert # this is a post comment
  - pip:
    - pbert
    - foo
    - bar
env_specs:
  hello:
    packages:
      - qbert
        """,
            DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"
        }, check)


def test_remove_pip_packages_from_one_environment_empty_pkgs():
    def check(dirname):
        def attempt():
            project = Project(dirname)

            for env_spec in project.env_specs.values():
                assert env_spec.lock_set.enabled
                assert env_spec.lock_set.platforms == ()

            assert ['qbert', OrderedDict([('pip', ['pbert', 'foo',
                                                   'bar'])])] == list(project.project_file.get_value('packages'))
            status = project_ops.remove_packages(project, env_spec_name='hello', packages=['foo', 'bar'], pip=True)
            assert status
            assert [] == status.errors

        _with_conda_test(attempt)

        # be sure we really made the config changes
        project2 = Project(dirname)
        # note that hello will still inherit the deps from the global packages,
        # and that's fine
        assert ['qbert', OrderedDict([('pip', ['pbert'])])] == list(project2.project_file.get_value('packages'))
        assert [OrderedDict([('pip', [])])
                ] == list(project2.project_file.get_value(['env_specs', 'hello', 'packages'], []))

        # be sure we didn't delete comments from global packages section
        content = codecs.open(project2.project_file.filename, 'r', 'utf-8').read()
        assert '# this is a pre comment' in content
        assert '# this is a post comment' in content

        for env_spec in project2.env_specs.values():
            if env_spec.name == 'hello':
                assert env_spec.lock_set.enabled
                assert env_spec.lock_set.equivalent_to(
                    CondaLockSet({'all': []}, platforms=['linux-64', 'osx-64', 'win-64']))
            else:
                assert env_spec.lock_set.enabled

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
packages:
  # this is a pre comment
  - qbert # this is a post comment
  - pip:
    - pbert
    - foo
    - bar
env_specs:
  hello:
    packages: []
        """,
            DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"
        }, check)


def test_remove_packages_from_one_environment():
    def check(dirname):
        def attempt():
            project = Project(dirname)

            for env_spec in project.env_specs.values():
                assert env_spec.lock_set.enabled
                assert env_spec.lock_set.platforms == ()

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

        for env_spec in project2.env_specs.values():
            if env_spec.name == 'hello':
                assert env_spec.lock_set.enabled
                assert env_spec.lock_set.equivalent_to(
                    CondaLockSet({'all': []}, platforms=['linux-64', 'osx-64', 'win-64']))
            else:
                assert env_spec.lock_set.enabled

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
packages:
  # this is a pre comment
  - qbert # this is a post comment
  - foo
  - bar
env_specs:
  hello:
    packages:
     - foo
        """,
            DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"
        }, check)


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
        assert set(['baz', 'foo',
                    'bar']) == set(project2.project_file.get_value(['env_specs', 'another', 'packages'], []))
        assert project2.env_specs['another'].conda_package_names_set == set(['qbert', 'foo', 'bar', 'baz'])
        assert project2.env_specs['hello'].conda_package_names_set == set(['qbert'])

        # be sure we didn't delete comments from the env
        content = codecs.open(project2.project_file.filename, 'r', 'utf-8').read()
        assert '# this is a pre comment' in content
        assert '# this is a post comment' in content

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
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
"""
        }, check)


def test_remove_pip_packages_from_one_environment_leaving_others_unaffected():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            assert ['qbert', OrderedDict([('pip', ['pbert', 'foo',
                                                   'bar'])])] == list(project.project_file.get_value('packages'))
            status = project_ops.remove_packages(project, env_spec_name='hello', packages=['foo', 'bar'], pip=True)
            assert status
            assert [] == status.errors

        _with_conda_test(attempt)

        # be sure we really made the config changes
        project2 = Project(dirname)
        assert ['qbert', OrderedDict([('pip', ['pbert'])])] == list(project2.project_file.get_value('packages'))
        assert [OrderedDict([('pip', [])])
                ] == list(project2.project_file.get_value(['env_specs', 'hello', 'packages'], []))
        assert set(['baz', 'foo',
                    'bar']) == set(project2.project_file.get_value(['env_specs', 'another', 'packages'], [])[0]['pip'])
        assert project2.env_specs['another'].pip_package_names_set == set(['foo', 'bar', 'baz', 'pbert'])
        assert project2.env_specs['hello'].pip_package_names_set == set(['pbert'])

        # be sure we didn't delete comments from the env
        content = codecs.open(project2.project_file.filename, 'r', 'utf-8').read()
        assert '# this is a pre comment' in content
        assert '# this is a post comment' in content

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
packages:
  - qbert
  - pip:
    - pbert
    - foo
    - bar
env_specs:
  hello:
    packages:
     - pip:
       - foo
  another:
    packages:
      - pip:
        # this is a pre comment
        - baz # this is a post comment
"""
        }, check)


def test_remove_packages_cannot_resolve_deps():
    def check(dirname):
        def attempt():
            os.makedirs(os.path.join(dirname, 'envs', 'hello'))  # forces us to really run remove_packages
            project = Project(dirname, frontend=FakeFrontend())
            for env_spec in project.env_specs.values():
                assert env_spec.lock_set.enabled
                assert env_spec.lock_set.platforms == ()

            assert ['foo', 'bar', 'baz'] == list(project.project_file.get_value('packages'))
            assert ['foo', 'woot'] == list(project.project_file.get_value(['env_specs', 'hello', 'packages'], []))
            status = project_ops.remove_packages(project, env_spec_name=None, packages=['foo', 'bar'])
            assert status.status_description == "Error resolving dependencies for hello: NOPE."
            assert status.errors == []
            assert project.frontend.logs == []
            assert not status

        _with_conda_test(attempt, resolve_dependencies_error="NOPE")

        # be sure we didn't make the config changes
        project2 = Project(dirname)
        assert ['foo', 'bar', 'baz'] == list(project2.project_file.get_value('packages'))
        assert ['foo', 'woot'] == list(project2.project_file.get_value(['env_specs', 'hello', 'packages']))

        for env_spec in project2.env_specs.values():
            assert env_spec.lock_set.enabled
            assert env_spec.lock_set.platforms == ()

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
packages:
  - foo
  - bar
  - baz
env_specs:
  hello:
    packages:
     - foo
     - woot
        """,
            DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"
        }, check)


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

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
packages:
  - foo
  - bar
"""}, check)


def test_remove_packages_with_project_file_problems():
    def check(dirname):
        project = Project(dirname)
        status = project_ops.remove_packages(project, env_spec_name=None, packages=['foo'])

        assert not status
        assert [
            "%s: variables section contains wrong value type 42, should be dict or list of requirements" %
            project.project_file.basename
        ] == status.errors

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_add_platforms_to_all_environments():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            status = project_ops.add_platforms(project, env_spec_name=None, platforms=['linux-64', 'win-64'])
            assert status
            assert [] == status.errors

        _with_conda_test(attempt)

        # be sure we really made the config changes
        project2 = Project(dirname)
        assert ['osx-32', 'linux-64', 'win-64'] == list(project2.project_file.get_value('platforms'))

        for env_spec in project2.env_specs.values():
            assert env_spec.lock_set.enabled
            assert env_spec.lock_set.equivalent_to(CondaLockSet({'all': []}, platforms=['linux-64', 'osx-32',
                                                                                        'win-64']))

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
platforms: [osx-32]
                """,
            DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"
        }, check)


def test_add_platforms_already_exists():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            status = project_ops.add_platforms(project, env_spec_name=None, platforms=['osx-32'])
            assert status
            assert [] == status.errors

        _with_conda_test(attempt)

        project2 = Project(dirname)
        assert ['osx-32', 'win-64'] == list(project2.project_file.get_value('platforms'))

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
platforms: [osx-32, win-64]
                """,
            DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"
        }, check)


def test_add_platforms_cannot_resolve_deps():
    def check(dirname):
        def attempt():
            project = Project(dirname, frontend=FakeFrontend())
            assert project.project_file.get_value('platforms', None) == ['linux-64', 'osx-64', 'win-64']
            status = project_ops.add_platforms(project, env_spec_name=None, platforms=['osx-32', 'win-32'])
            assert status.status_description == "Error resolving dependencies for default: NOPE."
            assert status.errors == []
            assert project.frontend.logs == []
            assert not status

        _with_conda_test(attempt, resolve_dependencies_error="NOPE")

        # be sure we didn't make the config changes
        project2 = Project(dirname)
        assert project2.project_file.get_value('platforms', None) == ['linux-64', 'osx-64', 'win-64']

        for env_spec in project2.env_specs.values():
            assert env_spec.lock_set.enabled
            assert env_spec.lock_set.platforms == ()

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"}, check)


def test_add_platforms_nonexistent_environment():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            status = project_ops.add_platforms(project, env_spec_name="not_an_env", platforms=['foo', 'bar'])
            assert not status
            assert [] == status.errors

        _with_conda_test(attempt)

    with_directory_contents_completing_project_file(dict(), check)


def test_add_platforms_invalid_platform():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            status = project_ops.add_platforms(project, env_spec_name=None, platforms=['invalid_platform'])
            assert not status
            assert 'Unable to load the project.' == status.status_description
            assert [
                "anaconda-project.yml: Platform name 'invalid_platform' is invalid (valid "
                "examples: linux-64, osx-64, win-64)"
            ] == status.errors

        _with_conda_test(attempt)

    with_directory_contents_completing_project_file(dict(), check)


def test_remove_platforms_from_all_environments():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            for env_spec in project.env_specs.values():
                assert env_spec.lock_set.enabled
                assert env_spec.lock_set.platforms == ()

            assert ['linux-64', 'osx-32'] == list(project.project_file.get_value('platforms'))
            status = project_ops.remove_platforms(project, env_spec_name=None, platforms=['linux-64'])
            assert [] == status.errors
            assert status

        _with_conda_test(attempt)

        # be sure we really made the config changes
        project2 = Project(dirname)
        assert ['osx-32'] == list(project2.project_file.get_value('platforms'))

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
platforms:
  - linux-64
  - osx-32
env_specs:
  hello: {}
        """,
            DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"
        }, check)


def test_remove_platforms_from_one_environment():
    def check(dirname):
        def attempt():
            project = Project(dirname)

            for env_spec in project.env_specs.values():
                assert env_spec.lock_set.enabled
                assert env_spec.lock_set.platforms == ()

            assert ['linux-64', 'osx-32'] == list(project.project_file.get_value('platforms'))
            assert ['linux-32',
                    'osx-32'] == list(project.project_file.get_value(['env_specs', 'hello', 'platforms'], []))
            status = project_ops.remove_platforms(project, env_spec_name='hello', platforms=['osx-32'])
            assert status
            assert [] == status.errors

        _with_conda_test(attempt)

        # be sure we really made the config changes
        project2 = Project(dirname)
        # remove_platforms is too simple to take this osx-32 out, but really it should,
        # similar to how remove_packages does it.
        assert ['linux-64', 'osx-32'] == list(project2.project_file.get_value('platforms'))
        # note that hello will still inherit the deps from the global platforms,
        # and that's fine
        assert ['linux-32'] == list(project2.project_file.get_value(['env_specs', 'hello', 'platforms'], []))

        # be sure we didn't delete comments from global platforms section
        content = codecs.open(project2.project_file.filename, 'r', 'utf-8').read()
        assert '# this is a pre comment' in content
        assert '# this is a post comment' in content

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
platforms:
  # this is a pre comment
  - linux-64 # this is a post comment
  - osx-32
env_specs:
  hello:
    platforms:
     - linux-32
     - osx-32
        """,
            DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"
        }, check)


def test_remove_platforms_cannot_resolve_deps():
    def check(dirname):
        def attempt():
            project = Project(dirname, frontend=FakeFrontend())
            for env_spec in project.env_specs.values():
                assert env_spec.lock_set.enabled
                assert env_spec.lock_set.platforms == ()

            assert ['linux-64', 'osx-32'] == list(project.project_file.get_value('platforms'))
            assert ['linux-32',
                    'osx-32'] == list(project.project_file.get_value(['env_specs', 'hello', 'platforms'], []))

            status = project_ops.remove_platforms(project, env_spec_name='hello', platforms=['linux-32'])
            assert status.errors == []
            assert project.frontend.logs == []
            assert status.status_description == "Error resolving dependencies for hello: NOPE."
            assert not status

        _with_conda_test(attempt, resolve_dependencies_error="NOPE")

        # be sure we didn't make the config changes
        project2 = Project(dirname)
        assert ['linux-64', 'osx-32'] == list(project2.project_file.get_value('platforms'))
        assert ['linux-32', 'osx-32'] == list(project2.project_file.get_value(['env_specs', 'hello', 'platforms'], []))

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
platforms:
  - linux-64
  - osx-32
env_specs:
  hello:
    platforms:
     - linux-32
     - osx-32
        """,
            DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"
        }, check)


def test_remove_platforms_from_nonexistent_environment():
    def check(dirname):
        def attempt():
            project = Project(dirname)
            assert ['linux-64'] == list(project.project_file.get_value('platforms'))
            status = project_ops.remove_platforms(project, env_spec_name='not_an_environment', platforms=['linux-64'])
            assert not status
            assert [] == status.errors
            assert "Environment spec not_an_environment doesn't exist." == status.status_description

        _with_conda_test(attempt)

        # be sure we didn't make the config changes
        project2 = Project(dirname)
        assert ['linux-64'] == list(project2.project_file.get_value('platforms'))

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
platforms:
  - linux-64
"""}, check)


def test_remove_platforms_with_project_file_problems():
    def check(dirname):
        project = Project(dirname)
        status = project_ops.remove_platforms(project, env_spec_name=None, platforms=['foo'])

        assert not status
        assert [
            "%s: variables section contains wrong value type 42, should be dict or list of requirements" %
            project.project_file.basename
        ] == status.errors

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_lock_nonexistent_environment():
    def check(dirname):
        def attempt():
            project = project_no_dedicated_env(dirname)
            status = project_ops.lock(project, env_spec_name="not_an_env")
            assert not status
            assert [] == status.errors
            assert "Environment spec not_an_env doesn't exist." == status.status_description

        _with_conda_test(attempt)

    with_directory_contents_completing_project_file(dict(), check)


def test_unlock_nonexistent_environment():
    def check(dirname):
        def attempt():
            project = project_no_dedicated_env(dirname)
            status = project_ops.unlock(project, env_spec_name="not_an_env")
            assert not status
            assert [] == status.errors
            assert "Environment spec not_an_env doesn't exist." == status.status_description

        _with_conda_test(attempt)

    with_directory_contents_completing_project_file(dict(), check)


def test_lock_broken_project():
    def check(dirname):
        def attempt():
            project = project_no_dedicated_env(dirname)
            status = project_ops.lock(project, env_spec_name=None)
            assert not status
            assert len(status.errors) > 0

        _with_conda_test(attempt)

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ""}, check)


def test_unlock_broken_project():
    def check(dirname):
        def attempt():
            project = project_no_dedicated_env(dirname)
            status = project_ops.unlock(project, env_spec_name=None)
            assert not status
            assert len(status.errors) > 0

        _with_conda_test(attempt)

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ""}, check)


def test_lock_and_update_and_unlock_all_envs():
    def check(dirname):
        resolve_results = {'all': ['a=1.0=1'], 'pip': ['cc==1.0']}

        def attempt():
            filename = os.path.join(dirname, DEFAULT_PROJECT_LOCK_FILENAME)
            assert not os.path.isfile(filename)

            project = Project(dirname, frontend=FakeFrontend())

            assert project.env_specs['foo'].platforms == ()
            assert project.env_specs['bar'].platforms == ()

            # Lock
            status = project_ops.lock(project, env_spec_name=None)
            assert [] == status.errors
            assert status

            # yapf: disable
            expected_output = """Set project platforms list to {platforms}
Updating locked dependencies for env spec bar...
Changes to locked dependencies for bar:
  platforms:
{platforms_diff}
  packages:
+   all:
+     a=1.0=1
+   pip:
+     cc==1.0
Added locked dependencies for env spec bar to anaconda-project-lock.yml.
Updating locked dependencies for env spec foo...
Changes to locked dependencies for foo:
  platforms:
{platforms_diff}
  packages:
+   all:
+     a=1.0=1
+   pip:
+     cc==1.0
Added locked dependencies for env spec foo to anaconda-project-lock.yml.""".format(
                platforms=', '.join(conda_api.default_platforms_with_current()),
                platforms_diff='\n'.join(['+   {p}'.format(p=p) for p in conda_api.default_platforms_with_current()])
            ).splitlines()
            assert expected_output == project.frontend.logs
            # yapf: enable

            assert os.path.isfile(filename)

            assert ('a=1.0=1', ) == project.env_specs['foo'].lock_set.package_specs_for_current_platform
            assert ('a=1.0=1', ) == project.env_specs['bar'].lock_set.package_specs_for_current_platform

            assert ['cc==1.0'] == project.env_specs['foo'].lock_set.pip_package_specs
            assert ['cc==1.0'] == project.env_specs['bar'].lock_set.pip_package_specs

            assert ('a=1.0=1', ) == project.env_specs['foo'].conda_packages_for_create
            # 'b' gets dropped here since it wasn't in the lock set
            assert ('a=1.0=1', ) == project.env_specs['bar'].conda_packages_for_create

            assert ['cc==1.0'] == project.env_specs['foo'].pip_packages_for_create
            assert ['cc==1.0'] == project.env_specs['bar'].pip_packages_for_create

            assert project.env_specs['foo'].platforms == conda_api.default_platforms_with_current()
            assert project.env_specs['bar'].platforms == conda_api.default_platforms_with_current()

            # we should have set the global platforms, not in each env spec
            assert conda_api.default_platforms_with_current() == project.project_file.get_value('platforms')
            assert project.project_file.get_value(['env_specs', 'foo', 'platforms'], None) is None
            assert project.project_file.get_value(['env_specs', 'bar', 'platforms'], None) is None

            # Lock again (idempotent)
            project.frontend.reset()
            status = project_ops.lock(project, env_spec_name=None)
            assert [] == status.errors
            assert status

            # Update (does nothing in this case)
            project.frontend.reset()
            status = project_ops.update(project, env_spec_name=None)
            assert [] == status.errors
            assert status
            assert [
                "Updating locked dependencies for env spec bar...",
                "Locked dependencies for env spec bar are already up to date.",
                "Updating locked dependencies for env spec foo...",
                "Locked dependencies for env spec foo are already up to date."
            ] == project.frontend.logs
            assert status.status_description == "Update complete."

            # Update (does something after tweaking resolve results)
            project.frontend.reset()
            resolve_results['all'] = ['a=2.0=0']
            status = project_ops.update(project, env_spec_name=None)
            assert [] == status.errors
            assert status
            assert status.status_description == "Update complete."
            assert ('a=2.0=0', ) == project.env_specs['foo'].conda_packages_for_create

            assert '-     a=1.0=1' in project.frontend.logs
            assert '+     a=2.0=0' in project.frontend.logs

            # Unlock
            project.frontend.reset()
            status = project_ops.unlock(project, env_spec_name=None)
            assert [] == status.errors
            assert status
            assert 'Dependency locking is now disabled.' == status.status_description

            assert project.env_specs['foo'].lock_set.disabled
            assert project.env_specs['bar'].lock_set.disabled

            assert ('a', ) == project.env_specs['foo'].conda_packages_for_create
            assert ('b', ) == project.env_specs['bar'].conda_packages_for_create

            assert ('cc', ) == project.env_specs['foo'].pip_packages_for_create
            assert ('dd', ) == project.env_specs['bar'].pip_packages_for_create

        _with_conda_test(attempt, resolve_dependencies=resolve_results)

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME:
            """
name: locktest
env_specs:
  foo:
    packages:
      - a
      - pip:
        - cc
  bar:
    packages:
      - b
      - pip:
        - dd
"""
        }, check)


def test_lock_and_unlock_single_env(mocked_hash):
    def check(dirname):
        def attempt():
            filename = os.path.join(dirname, DEFAULT_PROJECT_LOCK_FILENAME)
            assert not os.path.isfile(filename)

            project = Project(dirname, frontend=FakeFrontend())

            assert project.env_specs['foo'].platforms == ()
            assert project.env_specs['bar'].platforms == ('osx-64', )

            # Lock
            status = project_ops.lock(project, env_spec_name='foo')
            assert [] == status.errors
            assert status

            # yapf: disable
            expected_output = """Set platforms for foo to {platforms}
Updating locked dependencies for env spec foo...
Changes to locked dependencies for foo:
  platforms:
{platforms_diff}
  packages:
+   all:
+     a=1.0=1
Added locked dependencies for env spec foo to anaconda-project-lock.yml.""".format(
                platforms=', '.join(conda_api.default_platforms_with_current()),
                platforms_diff='\n'.join(['+   {p}'.format(p=p) for p in conda_api.default_platforms_with_current()])
            ).splitlines()
            assert expected_output == project.frontend.logs
            # yapf: enable

            assert 'Project dependencies are locked.' == status.status_description

            assert os.path.isfile(filename)

            foo_lock_set = project.env_specs['foo'].lock_set
            assert ('a=1.0=1', ) == foo_lock_set.package_specs_for_current_platform
            assert foo_lock_set.env_spec_hash == '86f7e437faa5a7fce15d1ddcb9eaeaea377667b8'
            assert project.env_specs['bar'].lock_set.disabled

            assert ('a=1.0=1', ) == project.env_specs['foo'].conda_packages_for_create
            assert ('b', ) == project.env_specs['bar'].conda_packages_for_create

            assert project.env_specs['foo'].platforms == conda_api.default_platforms_with_current()
            assert project.env_specs['bar'].platforms == ('osx-64', )

            # we should NOT have set the global platforms
            assert project.project_file.get_value('platforms', None) is None
            assert conda_api.default_platforms_with_current() == project.project_file.get_value(
                ['env_specs', 'foo', 'platforms'], None)
            assert [
                'osx-64',
            ] == project.project_file.get_value(['env_specs', 'bar', 'platforms'], None)

            # Locking a second time is a no-op
            project.frontend.reset()
            status = project_ops.lock(project, env_spec_name='foo')
            assert [] == status.errors
            assert status
            assert ['Env spec foo is already locked.'] == project.frontend.logs
            assert 'Project dependencies are locked.' == status.status_description

            # Update (does nothing in this case)
            project.frontend.reset()
            status = project_ops.update(project, env_spec_name='foo')
            assert [] == status.errors
            assert status
            assert [
                "Updating locked dependencies for env spec foo...",
                "Locked dependencies for env spec foo are already up to date."
            ] == project.frontend.logs
            assert 'Update complete.' == status.status_description

            # Now add a package (should change the hash)
            project.frontend.reset()
            status = project_ops.add_packages(project, 'foo', packages='q', channels=[])
            assert [] == status.errors
            assert status
            assert [] == project.frontend.logs
            assert status.status_description.startswith("Using Conda environment")

            foo_lock_set = project.env_specs['foo'].lock_set
            assert ('a=1.0=1', ) == foo_lock_set.package_specs_for_current_platform
            assert foo_lock_set.env_spec_hash == 'b3a7c645306726ef4965c7be7e859ec0efd9af5b'

            # Now unlock
            project.frontend.reset()
            status = project_ops.unlock(project, env_spec_name='foo')
            assert [] == status.errors
            assert status
            assert [] == project.frontend.logs
            assert 'Dependency locking is now disabled for env spec foo.' == status.status_description

            assert project.env_specs['foo'].lock_set.disabled
            assert project.env_specs['bar'].lock_set.disabled

            assert ('a', 'q') == project.env_specs['foo'].conda_packages_for_create
            assert ('b', ) == project.env_specs['bar'].conda_packages_for_create

        _with_conda_test(attempt, resolve_dependencies={'all': ['a=1.0=1']})

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME:
            """
name: locktest
env_specs:
  foo:
    packages:
      - a
  bar:
    platforms: [osx-64]
    packages:
      - b
"""
        }, check)


def test_locking_with_missing_lock_set_does_an_update():
    def check(dirname):
        def attempt():
            filename = os.path.join(dirname, DEFAULT_PROJECT_LOCK_FILENAME)
            assert os.path.isfile(filename)

            project = Project(dirname, frontend=FakeFrontend())

            assert project.env_specs['foo'].platforms == ('linux-64', 'osx-64', 'osx-arm64', 'win-64')
            # lock set should be enabled yet missing and empty
            assert project.env_specs['foo'].lock_set.enabled
            assert project.env_specs['foo'].lock_set.missing

            # Lock
            status = project_ops.lock(project, env_spec_name='foo')
            assert [] == status.errors
            assert status

            # yapf: disable
            assert ['Updating locked dependencies for env spec foo...',
                    'Changes to locked dependencies for foo:',
                    '  platforms:',
                    '+   linux-64',
                    '+   osx-64',
                    '+   osx-arm64',
                    '+   win-64',
                    '  packages:',
                    '+   all:',
                    '+     a=1.0=1',
                    'Added locked dependencies for env spec foo to anaconda-project-lock.yml.'] == project.frontend.logs
            # yapf: enable

            assert 'Project dependencies are locked.' == status.status_description

            assert os.path.isfile(filename)
            assert project.lock_file.get_value(['env_specs', 'foo']) is not None

            foo_lock_set = project.env_specs['foo'].lock_set
            assert ('a=1.0=1', ) == foo_lock_set.package_specs_for_current_platform
            assert foo_lock_set.env_spec_hash == '83ac707b75eaa131f7a26a0b09172a7f39ff7195'
            assert project.env_specs['foo'].lock_set.enabled
            assert not project.env_specs['foo'].lock_set.missing

        _with_conda_test(attempt, resolve_dependencies={'all': ['a=1.0=1']})

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME: """
name: locktest
platforms: [linux-64,osx-64,osx-arm64,win-64]
env_specs:
  foo:
    packages:
      - a
        """,
            DEFAULT_PROJECT_LOCK_FILENAME: """
locking_enabled: true
# No lock set in here!
"""
        }, check)


def test_update_changes_only_the_hash():
    def check(dirname):
        def attempt():
            project = Project(dirname, frontend=FakeFrontend())

            foo_lock_set = project.env_specs['foo'].lock_set
            assert ('a=1.0=1', ) == foo_lock_set.package_specs_for_current_platform
            assert foo_lock_set.env_spec_hash == 'old'

            assert ('a=1.0=1', ) == project.env_specs['foo'].conda_packages_for_create

            # Update
            status = project_ops.update(project, env_spec_name='foo')
            assert [] == status.errors
            assert status
            assert [
                'Updating locked dependencies for env spec foo...',
                'Updated hash for env spec foo to 072f81028686690f6e2c6602e484ba78d084eec9 in '
                'anaconda-project-lock.yml.'
            ] == project.frontend.logs
            assert 'Update complete.' == status.status_description

            foo_lock_set = project.env_specs['foo'].lock_set
            assert ('a=1.0=1', ) == foo_lock_set.package_specs_for_current_platform
            assert foo_lock_set.env_spec_hash == '072f81028686690f6e2c6602e484ba78d084eec9'

        _with_conda_test(attempt, resolve_dependencies={'all': ['a=1.0=1']})

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME:
            """
name: locktest
platforms: [linux-32,linux-64,osx-64,osx-arm64,win-32,win-64]
env_specs:
  foo:
    packages:
      - a
""",
            DEFAULT_PROJECT_LOCK_FILENAME:
            """
locking_enabled: true
env_specs:
  foo:
    platforms: [linux-32,linux-64,osx-64,osx-arm64,win-32,win-64]
    env_spec_hash: old
    packages:
      all: ['a=1.0=1']
"""
        }, check)


def test_lock_conda_error():
    def check(dirname):
        def attempt():
            filename = os.path.join(dirname, DEFAULT_PROJECT_LOCK_FILENAME)
            assert not os.path.isfile(filename)

            project = Project(dirname, frontend=FakeFrontend())
            status = project_ops.lock(project, env_spec_name=None)
            assert [] == status.errors
            assert not status
            assert "test deviation" == status.status_description

            assert not os.path.isfile(filename)

        _with_conda_test(attempt,
                         missing_packages=('a', 'b'),
                         resolve_dependencies={'all': ['a=1.0=1']},
                         fix_works=False)

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME:
            """
name: locktest
platforms: [linux-32,linux-64,osx-64,win-32,win-64]
env_specs:
  foo:
    packages:
      - a
  bar:
    packages:
      - b
"""
        }, check)


def test_lock_resolve_dependencies_error(monkeypatch):
    def check(dirname):
        def attempt():
            filename = os.path.join(dirname, DEFAULT_PROJECT_LOCK_FILENAME)
            assert not os.path.isfile(filename)

            project = Project(dirname, frontend=FakeFrontend())
            status = project_ops.lock(project, env_spec_name=None)
            assert [] == status.errors
            assert not status
            assert 'Nope on resolve' in status.status_description

            assert not os.path.isfile(filename)

        _with_conda_test(attempt, missing_packages=('a', 'b'), resolve_dependencies_error="Nope on resolve")

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME:
            """
name: locktest
platforms: [linux-32,linux-64,osx-64,win-32,win-64]
env_specs:
  foo:
    packages:
      - a
  bar:
    packages:
      - b
"""
        }, check)


def test_unlock_conda_error():
    def check(dirname):
        def attempt():
            filename = os.path.join(dirname, DEFAULT_PROJECT_LOCK_FILENAME)
            assert os.path.isfile(filename)

            project = Project(dirname, frontend=FakeFrontend())

            assert project.env_specs['foo'].lock_set.enabled
            assert project.env_specs['bar'].lock_set.enabled

            status = project_ops.unlock(project, env_spec_name=None)
            assert [] == status.errors
            assert not status
            assert "test deviation" == status.status_description

            assert os.path.isfile(filename)

            assert project.env_specs['foo'].lock_set.enabled
            assert project.env_specs['bar'].lock_set.enabled

        _with_conda_test(attempt,
                         missing_packages=('a', 'b'),
                         resolve_dependencies={'all': ['a=1.0=1']},
                         fix_works=False)

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME:
            """
name: locktest
platforms: [linux-32,linux-64,osx-64,win-32,win-64]
env_specs:
  foo:
    packages:
      - a
  bar:
    packages:
      - b
""",
            DEFAULT_PROJECT_LOCK_FILENAME:
            """
locking_enabled: true
env_specs:
  foo:
    locked: true
    platforms: [linux-32,linux-64,osx-64,win-32,win-64]
    packages:
       all:
         - c
  bar:
    locked: true
    platforms: [linux-32,linux-64,osx-64,win-32,win-64]
    packages:
       all:
         - d
"""
        }, check)


def test_update_unlocked_envs():
    def check(dirname):
        resolve_results = {'all': ['a=1.0=1']}

        def attempt():
            filename = os.path.join(dirname, DEFAULT_PROJECT_LOCK_FILENAME)
            assert not os.path.isfile(filename)

            project = Project(dirname, frontend=FakeFrontend())

            # all lock sets disabled
            for env in project.env_specs.values():
                assert env.lock_set.disabled

            # Update (should install packages but not make a lock file)
            status = project_ops.update(project, env_spec_name=None)
            assert [] == status.errors
            assert status
            assert status.status_description == "Update complete."
            assert project.frontend.logs == [
                'Updating locked dependencies for env spec bar...', 'Updated installed dependencies for bar.',
                'Updating locked dependencies for env spec foo...', 'Updated installed dependencies for foo.'
            ]

            # no project lock file created
            assert not os.path.isfile(filename)

            # all lock sets still disabled
            for env in project.env_specs.values():
                assert env.lock_set.disabled

        _with_conda_test(attempt, resolve_dependencies=resolve_results)

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME:
            """
name: locktest
platforms: [linux-32,linux-64,osx-64,win-32,win-64]
env_specs:
  foo:
    packages:
      - a
  bar:
    packages:
      - b
"""
        }, check)


def test_update_empty_lock_sets():
    def check(dirname):
        resolve_results = {'all': ['a=1.0=1']}

        def attempt():
            project = Project(dirname, frontend=FakeFrontend())

            # all lock sets enabled but empty
            for env in project.env_specs.values():
                assert env.lock_set.enabled
                assert env.lock_set.platforms == ()
                assert not env.lock_set.supports_current_platform

            # Update
            status = project_ops.update(project, env_spec_name=None)
            assert [] == status.errors
            assert status
            assert status.status_description == "Update complete."
            # yapf: disable
            assert project.frontend.logs == [
                'Updating locked dependencies for env spec bar...',
                'Changes to locked dependencies for bar:',
                '  platforms:',
                '+   linux-64',
                '+   osx-64',
                '+   osx-arm64',
                '+   win-64',
                '  packages:',
                '+   all:',
                '+     a=1.0=1',
                'Updated locked dependencies for env spec bar in anaconda-project-lock.yml.',
                'Updating locked dependencies for env spec foo...',
                'Changes to locked dependencies for foo:',
                '  platforms:',
                '+   linux-64',
                '+   osx-64',
                '+   osx-arm64',
                '+   win-64',
                '  packages:',
                '+   all:',
                '+     a=1.0=1',
                'Updated locked dependencies for env spec foo in anaconda-project-lock.yml.'
            ]
            # yapf: enable
            for env in project.env_specs.values():
                assert env.lock_set.enabled
                assert env.lock_set.supports_current_platform
                assert env.lock_set.platforms == ('linux-64', 'osx-64', 'osx-arm64', 'win-64')
                assert env.lock_set.package_specs_for_current_platform == ('a=1.0=1', )

        _with_conda_test(attempt, resolve_dependencies=resolve_results)

    with_directory_contents(
        {
            DEFAULT_PROJECT_FILENAME: """
name: locktest
platforms: [linux-64,osx-64,osx-arm64,win-64]
env_specs:
  foo:
    packages:
      - a
  bar:
    packages:
      - b
        """,
            DEFAULT_PROJECT_LOCK_FILENAME: "locking_enabled: true\n"
        }, check)


def test_export_env_spec():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        exported = os.path.join(dirname, "exported.yml")
        status = project_ops.export_env_spec(project, name='default', filename=exported)
        assert status
        assert status.status_description == ('Exported environment spec default to %s.' % exported)

    with_directory_contents_completing_project_file(
        {"anaconda-project.yml": """
env_specs:
  default:
    packages:
      - blah
    channels:
      - boo
"""}, check)


def test_export_nonexistent_env_spec():
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        exported = os.path.join(dirname, "exported.yml")
        status = project_ops.export_env_spec(project, name='bar', filename=exported)
        assert not status
        assert not os.path.exists(exported)
        assert status.status_description == "Environment spec bar doesn't exist."

    with_directory_contents_completing_project_file(
        {"anaconda-project.yml": """
env_specs:
  default:
    packages:
      - blah
    channels:
      - boo
"""}, check)


def test_export_env_spec_io_error(monkeypatch):
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        exported = os.path.join(dirname, "exported.yml")

        def mock_atomic_replace(*args, **kwargs):
            raise IOError("NOOO")

        monkeypatch.setattr('anaconda_project.yaml_file._atomic_replace', mock_atomic_replace)
        status = project_ops.export_env_spec(project, name='default', filename=exported)
        assert not status
        assert not os.path.exists(exported)
        assert status.status_description == ("Failed to save %s: NOOO." % exported)

    with_directory_contents_completing_project_file(
        {"anaconda-project.yml": """
env_specs:
  default:
    packages:
      - blah
    channels:
      - boo
"""}, check)


def _monkeypatch_can_connect_to_socket_on_standard_redis_port(monkeypatch):
    from anaconda_project.requirements_registry.network_util import can_connect_to_socket as real_can_connect_to_socket

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

    monkeypatch.setattr("anaconda_project.requirements_registry.network_util.can_connect_to_socket",
                        mock_can_connect_to_socket)

    return can_connect_args_list


def test_add_service(monkeypatch):
    def check(dirname):
        _monkeypatch_can_connect_to_socket_on_standard_redis_port(monkeypatch)

        project = project_no_dedicated_env(dirname)
        status = project_ops.add_service(project, None, service_type='redis')

        assert status
        assert isinstance(project.frontend.logs, list)
        assert [] == status.errors

        # be sure service was added to the file and saved
        project2 = project_no_dedicated_env(dirname)
        assert 'redis' == project2.project_file.get_value(['services', 'REDIS_URL'])

    with_directory_contents_completing_project_file(dict(), check)


def test_add_service_with_env_spec(monkeypatch):
    def check(dirname):
        _monkeypatch_can_connect_to_socket_on_standard_redis_port(monkeypatch)

        project = project_no_dedicated_env(dirname)
        status = project_ops.add_service(project, 'myspec', service_type='redis')

        assert status
        assert isinstance(project.frontend.logs, list)
        assert [] == status.errors

        # be sure service was added to the file and saved
        project2 = project_no_dedicated_env(dirname)
        assert 'redis' == project2.project_file.get_value(['env_specs', 'myspec', 'services', 'REDIS_URL'])

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
env_specs:
    default:
      packages: [python]
      channels: []
    myspec:
      packages: [python]
      channels: []
"""
        }, check)


def test_add_service_nondefault_variable_name(monkeypatch):
    def check(dirname):
        _monkeypatch_can_connect_to_socket_on_standard_redis_port(monkeypatch)

        project = project_no_dedicated_env(dirname)
        status = project_ops.add_service(project, None, service_type='redis', variable_name='MY_SPECIAL_REDIS')

        assert status
        assert isinstance(project.frontend.logs, list)
        assert [] == status.errors

        # be sure service was added to the file and saved
        project2 = project_no_dedicated_env(dirname)
        assert 'redis' == project2.project_file.get_value(['services', 'MY_SPECIAL_REDIS'])

    with_directory_contents_completing_project_file(dict(), check)


def test_add_service_with_project_file_problems():
    def check(dirname):
        project = Project(dirname, frontend=FakeFrontend())
        status = project_ops.add_service(project, None, service_type='redis')

        assert not status
        assert [
            "%s: variables section contains wrong value type 42, should be dict or list of requirements" %
            project.project_file.basename
        ] == status.errors

        # be sure service was NOT added to the file
        project2 = Project(dirname, frontend=FakeFrontend())
        assert project2.project_file.get_value(['services', 'REDIS_URL']) is None
        # should have been dropped from the original project object also
        assert project.project_file.get_value(['services', 'REDIS_URL']) is None

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_add_service_already_exists(monkeypatch):
    def check(dirname):
        _monkeypatch_can_connect_to_socket_on_standard_redis_port(monkeypatch)

        project = project_no_dedicated_env(dirname)
        status = project_ops.add_service(project, None, service_type='redis')

        assert status
        assert isinstance(project.frontend.logs, list)
        assert [] == status.errors

        # be sure service was added to the file and saved
        project2 = Project(dirname, frontend=FakeFrontend())
        assert 'redis' == project2.project_file.get_value(['services', 'REDIS_URL'])

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, check)


def test_add_service_already_exists_with_different_type(monkeypatch):
    def check(dirname):
        _monkeypatch_can_connect_to_socket_on_standard_redis_port(monkeypatch)

        project = Project(dirname, frontend=FakeFrontend())
        status = project_ops.add_service(project, None, service_type='redis')

        assert not status
        # Once we have >1 known service types, we should change this test
        # to use the one other than redis and then this error will change.
        assert ["Service REDIS_URL has an unknown type 'foo'."] == status.errors

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: foo
"""}, check)


def test_add_service_already_exists_as_non_service(monkeypatch):
    def check(dirname):
        _monkeypatch_can_connect_to_socket_on_standard_redis_port(monkeypatch)

        project = Project(dirname, frontend=FakeFrontend())
        status = project_ops.add_service(project, None, service_type='redis')

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

        project = Project(dirname, frontend=FakeFrontend())
        status = project_ops.add_service(project, None, service_type='not_a_service')

        assert not status
        assert ["Unknown service type 'not_a_service', we know about: redis"] == status.errors

    with_directory_contents_completing_project_file(dict(), check)


def test_remove_service(monkeypatch):
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        status = project_ops.remove_service(project, None, variable_name='redis')

        assert status
        assert [] == status.errors

        project2 = project_no_dedicated_env(dirname)
        assert project2.project_file.get_value(['services', 'REDIS_URL']) is None

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, check)


def test_remove_service_with_prepare(monkeypatch):
    def check(dirname):
        _monkeypatch_can_connect_to_socket_on_standard_redis_port(monkeypatch)
        project = project_no_dedicated_env(dirname)
        result = prepare.prepare_without_interaction(project)
        assert result
        status = project_ops.remove_service(project, None, variable_name='redis', prepare_result=result)

        assert status
        assert [] == status.errors

        project2 = project_no_dedicated_env(dirname)
        assert project2.project_file.get_value(['services', 'REDIS_URL']) is None

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, check)


def test_remove_service_with_env_spec(monkeypatch):
    def check(dirname):
        config_path = ['env_specs', 'myspec', 'services', 'REDIS_URL']
        project = project_no_dedicated_env(dirname)
        assert project.project_file.get_value(config_path) == 'redis'
        status = project_ops.remove_service(project, 'myspec', variable_name='redis')

        assert status
        assert [] == status.errors

        project2 = project_no_dedicated_env(dirname)
        assert project2.project_file.get_value(config_path) is None

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """
env_specs:
    default:
      packages: [python]
      channels: []
    myspec:
      packages: [python]
      channels: []
      services:
        REDIS_URL: redis
"""
        }, check)


def check_cleaned(dirname, envs_dirname="envs"):
    project = Project(dirname, frontend=FakeFrontend())

    result = prepare.prepare_without_interaction(project, env_spec_name='foo')

    assert result
    envs_dir = os.path.join(dirname, envs_dirname)
    assert os.path.isdir(os.path.join(envs_dir, "foo"))

    # prepare again with 'bar' this time
    result = prepare.prepare_without_interaction(project, env_spec_name='bar')
    assert result
    bar_dir = os.path.join(dirname, envs_dirname, "bar")
    assert os.path.isdir(bar_dir)

    # we don't really have a service in the test project file because
    # redis-server doesn't work on Windows and it's good to run this
    # test on Windows. So create some fake junk in services dir.
    services_dir = os.path.join(dirname, "services")
    os.makedirs(os.path.join(services_dir, "leftover-debris"))

    status = project_ops.clean(project, result)
    assert status
    assert status.status_description == "Cleaned."
    assert project.frontend.logs == [("Deleted environment files in %s." % bar_dir), ("Removing %s." % services_dir),
                                     ("Removing %s." % envs_dir)]
    assert status.errors == []

    assert not os.path.isdir(os.path.join(dirname, envs_dirname))
    assert not os.path.isdir(os.path.join(dirname, "services"))


def test_clean(monkeypatch):
    def mock_create(prefix, pkgs, channels, stdout_callback, stderr_callback):
        os.makedirs(os.path.join(prefix, "conda-meta"))

    monkeypatch.setattr('anaconda_project.internal.conda_api.create', mock_create)

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
env_specs:
   foo: {}
   bar: {}
"""}, check_cleaned)


def test_clean_from_environ(monkeypatch):
    def mock_create(prefix, pkgs, channels, stdout_callback, stderr_callback):
        os.makedirs(os.path.join(prefix, "conda-meta"))

    monkeypatch.setattr('anaconda_project.internal.conda_api.create', mock_create)

    def check(dirname):
        os.environ['ANACONDA_PROJECT_ENVS_PATH'] = os.path.join(dirname, "some_random_path")
        res = check_cleaned(dirname, "some_random_path")
        os.environ.pop('ANACONDA_PROJECT_ENVS_PATH')
        return res

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
env_specs:
   foo: {}
   bar: {}
"""}, check)


def test_clean_failed_delete(monkeypatch):
    def mock_create(prefix, pkgs, channels, stdout_callback, stderr_callback):
        os.makedirs(os.path.join(prefix, "conda-meta"))

    monkeypatch.setattr('anaconda_project.internal.conda_api.create', mock_create)

    def check(dirname):
        project = Project(dirname, frontend=FakeFrontend())

        result = prepare.prepare_without_interaction(project, env_spec_name='foo')

        assert result
        envs_dir = os.path.join(dirname, "envs")
        assert os.path.isdir(os.path.join(envs_dir, "foo"))

        # prepare again with 'bar' this time
        project.frontend.reset()
        result = prepare.prepare_without_interaction(project, env_spec_name='bar')
        assert result
        bar_dir = os.path.join(dirname, "envs", "bar")
        assert os.path.isdir(bar_dir)

        # we don't really have a service in the test project file because
        # redis-server doesn't work on Windows and it's good to run this
        # test on Windows. So create some fake junk in services dir.
        services_dir = os.path.join(dirname, "services")
        os.makedirs(os.path.join(services_dir, "leftover-debris"))

        def mock_rmtree(path, onerror=None):
            raise IOError("No rmtree here")

        monkeypatch.setattr('shutil.rmtree', mock_rmtree)

        project.frontend.reset()
        status = project_ops.clean(project, result)
        assert not status
        assert status.status_description == "Failed to clean everything up."
        assert project.frontend.logs == [("Removing %s." % services_dir), ("Removing %s." % envs_dir)]
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


def test_clean_environ_failed_delete(monkeypatch):
    def mock_create(prefix, pkgs, channels, stdout_callback, stderr_callback):
        os.makedirs(os.path.join(prefix, "conda-meta"))

    monkeypatch.setattr('anaconda_project.internal.conda_api.create', mock_create)

    def check(dirname):
        envs_dir = os.environ['ANACONDA_PROJECT_ENVS_PATH'] = os.path.join(dirname, "some_random_failed_path")

        project = Project(dirname, frontend=FakeFrontend())

        result = prepare.prepare_without_interaction(project, env_spec_name='foo')

        assert result
        assert os.path.isdir(os.path.join(envs_dir, "foo"))

        # prepare again with 'bar' this time
        project.frontend.reset()
        result = prepare.prepare_without_interaction(project, env_spec_name='bar')
        assert result
        bar_dir = os.path.join(envs_dir, "bar")
        assert os.path.isdir(bar_dir)

        # we don't really have a service in the test project file because
        # redis-server doesn't work on Windows and it's good to run this
        # test on Windows. So create some fake junk in services dir.
        services_dir = os.path.join(dirname, "services")
        os.makedirs(os.path.join(services_dir, "leftover-debris"))

        def mock_rmtree(path, onerror=None):
            raise IOError("No rmtree here")

        monkeypatch.setattr('shutil.rmtree', mock_rmtree)

        project.frontend.reset()
        status = project_ops.clean(project, result)
        assert not status
        assert status.status_description == "Failed to clean everything up."
        assert project.frontend.logs == [("Removing %s." % services_dir), ("Removing %s." % envs_dir)]
        assert status.errors == [("Failed to remove environment files in %s: No rmtree here." % bar_dir),
                                 ("Error removing %s: No rmtree here." % services_dir),
                                 ("Error removing %s: No rmtree here." % envs_dir)]

        assert os.path.isdir(os.path.join(envs_dir))
        assert os.path.isdir(os.path.join(dirname, "services"))

        # so with_directory_contents_completing_project_file can remove our tmp dir
        monkeypatch.undo()
        # clean environ
        os.environ.pop('ANACONDA_PROJECT_ENVS_PATH')

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
env_specs:
   foo: {}
   bar: {}
"""}, check)


def _strip_prefixes(names):
    return list([name[len("archivedproj/"):].replace('\\', '/') for name in names])


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
            _assert_zip_contains(
                archivefile,
                ['.projectignore', 'a/b/c/d.py', 'a/b/c/e.py', 'emptydir/', 'foo.py', 'anaconda-project.yml'])

            # overwriting should work
            status = project_ops.archive(project, archivefile)

            assert status
            assert os.path.exists(archivefile)
            _assert_zip_contains(
                archivefile,
                ['.projectignore', 'a/b/c/d.py', 'a/b/c/e.py', 'emptydir/', 'foo.py', 'anaconda-project.yml'])

        with_directory_contents_completing_project_file(
            {
                DEFAULT_PROJECT_FILENAME: """
name: archivedproj
services:
   REDIS_URL: redis
    """,
                "foo.py": "print('hello')\n",
                "emptydir": None,
                "a/b/c/d.py": "",
                "a/b/c/e.py": ""
            }, check)

    with_directory_contents_completing_project_file(dict(), archivetest)


def test_archive_unlocked_warning():
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.zip")

        def check(dirname):
            project = project_no_dedicated_env(dirname)
            assert [] == project.problems
            assert project.env_specs['foo'].lock_set.enabled
            assert project.env_specs['bar'].lock_set.disabled
            status = project_ops.archive(project, archivefile)

            assert status
            assert os.path.exists(archivefile)

            # yapf: disable
            assert [
                '  added ' + os.path.join("archivedproj", ".projectignore"),
                '  added ' + os.path.join("archivedproj", "anaconda-project-lock.yml"),
                '  added ' + os.path.join("archivedproj", "anaconda-project.yml"),
                '  added ' + os.path.join("archivedproj", "foo.py"),
                'Warning: env specs are not locked, which means they may not work '
                'consistently for others or when deployed.',
                "  Consider using the 'anaconda-project lock' command to lock the project.",
                '  Unlocked env specs are: bar'
            ] == project.frontend.logs
            # yapf: enable

        with_directory_contents_completing_project_file(
            {
                DEFAULT_PROJECT_FILENAME: """
name: archivedproj
env_specs:
  foo:
    packages: []
  bar:
    packages: []
    """,
                DEFAULT_PROJECT_LOCK_FILENAME: """
locking_enabled: false
env_specs:
  foo:
    locked: true
    platforms: [linux-32,linux-64,osx-64,win-32,win-64]
    packages:
      all: []
             """,
                "foo.py": "print('hello')\n"
            }, check)

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
            _assert_tar_contains(
                archivefile,
                ['.projectignore', 'a/b/c/d.py', 'a/b/c/e.py', 'emptydir', 'foo.py', 'anaconda-project.yml'])

            # overwriting should work
            status = project_ops.archive(project, archivefile)

            assert status
            assert os.path.exists(archivefile)
            _assert_tar_contains(
                archivefile,
                ['.projectignore', 'a/b/c/d.py', 'a/b/c/e.py', 'emptydir', 'foo.py', 'anaconda-project.yml'])

        with_directory_contents_completing_project_file(
            {
                DEFAULT_PROJECT_FILENAME: """
name: archivedproj
services:
   REDIS_URL: redis
    """,
                "foo.py": "print('hello')\n",
                "emptydir": None,
                "a/b/c/d.py": "",
                "a/b/c/e.py": ""
            }, check)

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
            _assert_tar_contains(
                archivefile,
                ['.projectignore', 'a/b/c/d.py', 'a/b/c/e.py', 'emptydir', 'foo.py', 'anaconda-project.yml'])

            # overwriting should work
            status = project_ops.archive(project, archivefile)

            assert status
            assert os.path.exists(archivefile)
            _assert_tar_contains(
                archivefile,
                ['.projectignore', 'a/b/c/d.py', 'a/b/c/e.py', 'emptydir', 'foo.py', 'anaconda-project.yml'])

        with_directory_contents_completing_project_file(
            {
                DEFAULT_PROJECT_FILENAME: """
name: archivedproj
services:
   REDIS_URL: redis
    """,
                "foo.py": "print('hello')\n",
                "emptydir": None,
                "a/b/c/d.py": "",
                "a/b/c/e.py": ""
            }, check)

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
            _assert_tar_contains(
                archivefile,
                ['.projectignore', 'a/b/c/d.py', 'a/b/c/e.py', 'emptydir', 'foo.py', 'anaconda-project.yml'])

            # overwriting should work
            status = project_ops.archive(project, archivefile)

            assert status
            assert os.path.exists(archivefile)
            _assert_tar_contains(
                archivefile,
                ['.projectignore', 'a/b/c/d.py', 'a/b/c/e.py', 'emptydir', 'foo.py', 'anaconda-project.yml'])

        with_directory_contents_completing_project_file(
            {
                DEFAULT_PROJECT_FILENAME: """
name: archivedproj
services:
   REDIS_URL: redis
    """,
                "foo.py": "print('hello')\n",
                "emptydir": None,
                "a/b/c/d.py": "",
                "a/b/c/e.py": ""
            }, check)

    with_directory_contents_completing_project_file(dict(), archivetest)


def test_archive_cannot_write_destination_path(monkeypatch):
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.zip")

        def mock_ZipFile(*args, **kwargs):
            raise IOError("NOPE")

        monkeypatch.setattr('zipfile.ZipFile', mock_ZipFile)

        # need to mock plugins since entry_points uses zipfile.ZipFile that
        # we are mocking for this test
        monkeypatch.setattr(plugins_api, 'get_plugins', lambda x='fake': {})

        def check(dirname):
            # be sure we ignore this
            os.makedirs(os.path.join(dirname, "envs"))

            project = project_no_dedicated_env(dirname)
            status = project_ops.archive(project, archivefile)

            assert not status
            assert status.status_description == ('Failed to write project archive %s.' % archivefile)
            assert ['NOPE'] == status.errors

        with_directory_contents_completing_project_file(
            {
                DEFAULT_PROJECT_FILENAME: """
name: archivedproj
    """,
                "foo.py": "print('hello')\n"
            }, check)

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
            _assert_zip_contains(archivefile, ['foo.py', '.gitignore', 'anaconda-project.yml'])

        with_directory_contents_completing_project_file(
            _add_empty_git({
                DEFAULT_PROJECT_FILENAME: """
name: archivedproj
        """,
                "foo.py": "print('hello')\n",
                '.gitignore': "/ignored.py\n/subdir\n/subwithslash/\n",
                'ignored.py': 'print("ignore me!")',
                'subdir/foo.py': 'foo',
                'subdir/subsub/bar.py': 'bar',
                'subwithslash/something.py': 'something'
            }), check)

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
            _add_empty_git({
                DEFAULT_PROJECT_FILENAME: """
        """,
                "foo.py": "print('hello')\n"
            }), check)

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
            _add_empty_git({
                DEFAULT_PROJECT_FILENAME: """
        """,
                "foo.py": "print('hello')\n"
            }), check)

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
            _add_empty_git({
                DEFAULT_PROJECT_FILENAME: """
name: archivedproj
        """,
                "foo.py": "print('hello')\n"
            }), check)

    with_directory_contents_completing_project_file(dict(), archivetest)


def test_archive_zip_with_unreadable_projectignore(monkeypatch):
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.zip")

        def check(dirname):
            # be sure we ignore these
            os.makedirs(os.path.join(dirname, "services"))
            os.makedirs(os.path.join(dirname, "envs"))

            project = project_no_dedicated_env(dirname)

            ignorefile = os.path.join(dirname, ".projectignore")
            with codecs.open(ignorefile, 'w', 'utf-8') as f:
                f.write("\n")

            from codecs import open as real_open

            def mock_codecs_open(*args, **kwargs):
                if args[0].endswith(".projectignore"):
                    raise IOError("NOPE")
                else:
                    return real_open(*args, **kwargs)

            monkeypatch.setattr('codecs.open', mock_codecs_open)

            status = project_ops.archive(project, archivefile)

            assert not status
            assert not os.path.exists(archivefile)
            assert ["Failed to read %s: NOPE" % ignorefile] == status.errors

        with_directory_contents_completing_project_file(
            _add_empty_git({
                DEFAULT_PROJECT_FILENAME: """
name: archivedproj
        """,
                "foo.py": "print('hello')\n"
            }), check)

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
            _add_empty_git({
                DEFAULT_PROJECT_FILENAME: """
name: archivedproj
        """,
                "foo.py": "print('hello')\n"
            }), check)

    with_directory_contents_completing_project_file(dict(), archivetest)


def test_archive_with_no_project_file(monkeypatch):
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.zip")

        def check(dirname):
            project = project_no_dedicated_env(dirname)
            assert not os.path.exists(project.project_file.filename)

            status = project_ops.archive(project, archivefile)

            assert not status
            assert not os.path.exists(archivefile)
            assert status.status_description == "Can't create an archive."
            assert status.errors == ["%s does not exist." % DEFAULT_PROJECT_FILENAME]

        with_directory_contents(dict(), check)

    with_directory_contents(dict(), archivetest)


def test_archive_with_unsaved_project(monkeypatch):
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.zip")

        def check(dirname):
            project = project_no_dedicated_env(dirname)
            assert os.path.exists(project.project_file.filename)
            project.project_file.set_value(['name'], "hello")

            status = project_ops.archive(project, archivefile)

            assert not status
            assert not os.path.exists(archivefile)
            assert status.status_description == "Can't create an archive."
            assert status.errors == ["%s has been modified but not saved." % DEFAULT_PROJECT_FILENAME]

        with_directory_contents_completing_project_file(
            {DEFAULT_PROJECT_FILENAME: """
env_specs:
  default:
    packages: []
"""}, check)

    with_directory_contents(dict(), archivetest)


def test_archive_zip_with_downloaded_file():
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.zip")

        def check(dirname):
            project = project_no_dedicated_env(dirname)
            status = project_ops.archive(project, archivefile)

            assert status
            assert os.path.exists(archivefile)
            _assert_zip_contains(archivefile, ['.projectignore', 'foo.py', 'anaconda-project.yml'])

        with_directory_contents_completing_project_file(
            _add_empty_git({
                DEFAULT_PROJECT_FILENAME: """
name: archivedproj
downloads:
   MYDOWNLOAD: "http://example.com/downloaded.py"
""",
                "foo.py": "print('hello')\n",
                'downloaded.py': 'print("ignore me!")',
                'downloaded.py.part': ''
            }), check)

    with_directory_contents_completing_project_file(dict(), archivetest)


def test_archive_zip_overwrites_but_does_not_include_the_dest_zip():
    def check(dirname):
        project = project_no_dedicated_env(dirname)

        archivefile = os.path.join(dirname, "foo.zip")
        assert os.path.isfile(archivefile)

        status = project_ops.archive(project, archivefile)

        assert status
        assert os.path.exists(archivefile)

        _assert_zip_contains(archivefile, ['.projectignore', 'foo.py', 'anaconda-project.yml'])

        # re-archive to the same file
        status = project_ops.archive(project, archivefile)

        assert status
        assert os.path.exists(archivefile)

        _assert_zip_contains(archivefile, ['.projectignore', 'foo.py', 'anaconda-project.yml'])

    with_directory_contents_completing_project_file(
        _add_empty_git({
            DEFAULT_PROJECT_FILENAME: """
name: archivedproj
""",
            "foo.py": "print('hello')\n",
            'foo.zip': ""
        }), check)


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
            _assert_zip_contains(archivefile, ['foo.py', 'anaconda-project.yml', '.projectignore', 'bar/'])

        with_directory_contents_completing_project_file(
            {
                DEFAULT_PROJECT_FILENAME: """
name: archivedproj
        """,
                "foo.py": "print('hello')\n",
                "foo.pyc": "",
                ".ipynb_checkpoints/bleh": "",
                "bar/blah.pyc": ""
            }, check)

    with_directory_contents_completing_project_file(dict(), archivetest)


@pytest.mark.slow
@pytest.mark.skipif((sys.version_info.major == 2) and (platform.system() == 'Linux'),
                    reason='Something wrong with pip freeze on linux for py2')
@pytest.mark.parametrize('suffix', ['zip', 'tar.bz2', 'tar.gz'])
def test_archive_unarchive_conda_pack_with_pip(suffix):
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.{}".format(suffix))

        def check(dirname):
            project = project_ops.create(dirname)
            assert [] == project.problems

            status = prepare.prepare_without_interaction(project)
            assert status

            status = project_ops.archive(project, archivefile, pack_envs=True)

            assert status
            assert os.path.exists(archivefile)

            unpacked = os.path.join(os.path.dirname(archivefile), 'unpacked')
            status = project_ops.unarchive(archivefile, unpacked)
            assert status.errors == []
            assert status
            assert os.path.isdir(unpacked)

            unpacked_project = Project(unpacked)
            status = prepare.prepare_without_interaction(unpacked_project)
            assert status

        with_directory_contents_completing_project_file(
            {DEFAULT_PROJECT_FILENAME: """
name: archivedproj
packages:
  - python=3.8
  - pip:
    - pep8
"""}, check)

    with_directory_contents(dict(), archivetest)


@pytest.mark.slow
@pytest.mark.parametrize('suffix', ['zip', 'tar.bz2', 'tar.gz'])
def test_archive_unarchive_conda_pack(suffix):
    def archivetest(archive_dest_dir):
        archivefile = os.path.join(archive_dest_dir, "foo.{}".format(suffix))

        def check(dirname):
            project = project_ops.create(dirname)
            assert [] == project.problems

            status = prepare.prepare_without_interaction(project)
            assert status

            # a dummy file to test conda-unpack
            original_prefix = os.path.join(dirname, 'envs', 'default')
            with open(os.path.join(original_prefix, 'conda-meta', '_prefix'), 'wt') as f:
                f.write(original_prefix)

            status = project_ops.archive(project, archivefile, pack_envs=True)

            assert status
            assert os.path.exists(archivefile)

            expected_files = [
                'anaconda-project.yml', '.projectignore', 'foo.py', 'bar/blah.py', 'envs/default/conda-meta/.packed',
                'envs/default/conda-meta/history', 'envs/default/conda-meta/_prefix',
                'envs/default/conda-meta/font-ttf-ubuntu-0.83-h8b1ccd4_0.json',
                'envs/default/var/cache/anaconda-project/env-specs/7d832cfb38dabc7b1c20f98e15bfc4c601f21b62',
                'envs/default/fonts/Ubuntu-M.ttf', 'envs/default/fonts/Ubuntu-L.ttf',
                'envs/default/fonts/UbuntuMono-BI.ttf', 'envs/default/fonts/Ubuntu-BI.ttf',
                'envs/default/fonts/Ubuntu-MI.ttf', 'envs/default/fonts/Ubuntu-R.ttf',
                'envs/default/fonts/Ubuntu-LI.ttf', 'envs/default/fonts/Ubuntu-B.ttf',
                'envs/default/fonts/Ubuntu-C.ttf', 'envs/default/fonts/UbuntuMono-RI.ttf',
                'envs/default/fonts/UbuntuMono-R.ttf', 'envs/default/fonts/Ubuntu-RI.ttf',
                'envs/default/fonts/UbuntuMono-B.ttf'
            ]

            scripts_nix = ['envs/default/bin/conda-unpack', 'envs/default/bin/deactivate', 'envs/default/bin/activate']

            scripts_win = [
                'envs/default/Scripts/activate.bat', 'envs/default/Scripts/conda-unpack-script.py',
                'envs/default/Scripts/conda-unpack.exe', 'envs/default/Scripts/deactivate.bat'
            ]

            if 'win' in current_platform():
                expected_files.extend(scripts_win)
            else:
                expected_files.extend(scripts_nix)

            if suffix == 'zip':
                _assert_zip_contains(archivefile, expected_files)
            elif suffix in ['tar.bz2', 'tar.gz']:
                _assert_tar_contains(archivefile, expected_files)

            unpacked = os.path.join(os.path.dirname(archivefile), 'unpacked')
            status = project_ops.unarchive(archivefile, unpacked)
            assert status.errors == []
            assert status
            assert os.path.isdir(unpacked)

            _assert_dir_contains(unpacked, expected_files)

            if 'win' not in current_platform():
                conda_unpack = os.path.join(unpacked, 'envs', 'default', 'bin', 'conda-unpack')
                mode = os.lstat(conda_unpack)[stat.ST_MODE]
                assert mode & stat.S_IXUSR

            unpacked_project = Project(unpacked)
            status = prepare.prepare_without_interaction(unpacked_project)
            assert status

            with open(os.path.join(unpacked, 'envs', 'default', 'conda-meta', '_prefix')) as f:
                unpacked_prefix = f.read()

            assert unpacked_prefix != original_prefix

        with_directory_contents_completing_project_file(
            {
                DEFAULT_PROJECT_FILENAME: """
name: archivedproj
packages:
  - font-ttf-ubuntu=0.83=h8b1ccd4_0
        """,
                "foo.py": "print('hello')\n",
                "foo.pyc": "",
                ".ipynb_checkpoints/bleh": "",
                "bar/blah.py": "",
                "bar/blah.pyc": ""
            }, check)

    with_directory_contents(dict(), archivetest)


_CONTENTS_DIR = 1
_CONTENTS_FILE = 2
_CONTENTS_SYMLINK = 3


def _make_zip(archive_dest_dir, contents, mode_zero=False):
    archivefile = os.path.join(archive_dest_dir, "foo.zip")
    with zipfile.ZipFile(archivefile, 'w') as zf:
        for (key, what) in contents.items():
            if what is _CONTENTS_DIR:
                # create a directory
                if not key.endswith(os.sep):
                    key = key + os.sep
                zf.writestr(key, "")
            elif what is _CONTENTS_FILE:
                if mode_zero:
                    info = zipfile.ZipInfo(key)
                    info.external_attr = 16
                    zf.writestr(info, "hello")
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
        archivefile = _make_tar(archive_dest_dir, {
            'a/a.txt': _CONTENTS_FILE,
            'a/q/b.txt': _CONTENTS_FILE,
            'a/c': _CONTENTS_DIR,
            'a': _CONTENTS_DIR
        },
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
        archivefile = _make_zip(archive_dest_dir, {
            'a/a.txt': _CONTENTS_FILE,
            'a/q/b.txt': _CONTENTS_FILE,
            'a/c': _CONTENTS_DIR,
            'a': _CONTENTS_DIR
        })

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


def test_unarchive_zip_mode_zero():
    def archivetest(archive_dest_dir):
        archivefile = _make_zip(archive_dest_dir, {
            'a/a.txt': _CONTENTS_FILE,
            'a/q/b.txt': _CONTENTS_FILE,
            'a/c': _CONTENTS_DIR,
            'a': _CONTENTS_DIR
        },
                                mode_zero=True)

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
        archivefile = _make_zip(archive_dest_dir, {
            'a/a.txt': _CONTENTS_FILE,
            'a/q/b.txt': _CONTENTS_FILE,
            'a/c': _CONTENTS_DIR,
            'a': _CONTENTS_DIR
        })

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
        archivefile = _make_zip(archive_dest_dir, {
            'a/a.txt': _CONTENTS_FILE,
            'a/q/b.txt': _CONTENTS_FILE,
            'a/c': _CONTENTS_DIR
        })

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
        archivefile = _make_tar(archive_dest_dir, {
            'a/a.txt': _CONTENTS_FILE,
            'a/q/b.txt': _CONTENTS_FILE,
            'a/c': _CONTENTS_DIR
        })

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
            status = project_ops.unarchive(archivefile, unpacked)

            message = "Destination '%s' already exists and is not an empty directory." % unpacked
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
            assert status.errors[0].startswith(message)
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
        archivefile = _make_tar(archive_dest_dir, {
            'a/a.txt': _CONTENTS_FILE,
            'a/q/b.txt': _CONTENTS_FILE,
            'a/c': _CONTENTS_DIR,
            'a/link': _CONTENTS_SYMLINK
        })
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
        {
            DEFAULT_PROJECT_FILENAME: "name: foo\n",
            "foo.py": "print('hello')\n"
        }, check)


def test_upload_with_project_file_problems():
    def check(dirname):
        project = Project(dirname, frontend=FakeFrontend())
        status = project_ops.upload(project)
        assert not status
        assert [
            "%s: variables section contains wrong value type 42, should be dict or list of requirements" %
            project.project_file.basename
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
        {
            DEFAULT_PROJECT_FILENAME: "name: foo\n",
            "foo.py": "print('hello')\n"
        }, check)


def test_download(monkeypatch):
    def check(dirname):
        with fake_server(monkeypatch, expected_basename='fake_project.zip'):
            status = project_ops.download('fake_username/fake_project', unpack=False, site='unit_test')
            assert status

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: "name: foo\n",
            "foo.py": "print('hello')\n"
        }, check)


def test_download_unpack(monkeypatch):
    def check(dirname):
        with fake_server(monkeypatch, expected_basename='fake_project.zip'):
            status = project_ops.download('fake_username/fake_project', unpack=True, site='unit_test')
            assert status

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: "name: foo\n",
            "foo.py": "print('hello')\n"
        }, check)


def test_download_missing(monkeypatch):
    def check(dirname):
        with fake_server(monkeypatch, expected_basename='fake_project.zip'):
            status = project_ops.download('fake_username/missing_project', unpack=False, site='unit_test')
            assert not status

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: "name: foo\n",
            "foo.py": "print('hello')\n"
        }, check)


def _mock_build_image(path, tag, command, builder_image, build_args):
    msg = '\nDocker image {} build successful with command {}.'.format(tag, command)
    return SimpleStatus(True, description=msg)


def test_dock_default_args(monkeypatch):
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        monkeypatch.setattr('anaconda_project.project_ops.build_image', _mock_build_image)
        status = project_ops.dockerize(project)
        assert status
        assert 'Docker image dockerize-me:latest build successful' in status.status_description

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """name: dockerize-me
commands:
  default:
    unix: /usr/bin/true
    supports_http_options: false"""
        }, check)


def test_dock_name_with_spaces(monkeypatch):
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        monkeypatch.setattr('anaconda_project.project_ops.build_image', _mock_build_image)
        status = project_ops.dockerize(project)
        assert status
        assert 'Docker image dockerizeme:latest build successful' in status.status_description

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """name: Dockerize Me
commands:
  default:
    unix: /usr/bin/true
    supports_http_options: false"""
        }, check)


def test_dock_missing_command(monkeypatch):
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        monkeypatch.setattr('anaconda_project.project_ops.build_image', _mock_build_image)
        status = project_ops.dockerize(project, command='missing')
        assert not status
        assert 'The command missing is not one of the configured commands' in status.status_description

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """name: Dockerize Me
commands:
  default:
    unix: /usr/bin/true
    supports_http_options: false"""
        }, check)


def test_dock_default_command_alias(monkeypatch):
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        monkeypatch.setattr('anaconda_project.project_ops.build_image', _mock_build_image)
        status = project_ops.dockerize(project, command='default')
        assert status
        assert 'command cmd' in status.status_description

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME:
            """name: Dockerize Me
commands:
  cmd:
    unix: /usr/bin/true
    supports_http_options: false"""
        }, check)


def test_dock_without_commands(monkeypatch):
    def check(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems

        monkeypatch.setattr('anaconda_project.project_ops.build_image', _mock_build_image)
        status = project_ops.dockerize(project)
        assert not status
        assert "No known run command for this project" in status.status_description

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """name: Dockerize Me"""}, check)
