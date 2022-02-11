# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import os

from anaconda_project.internal.test.tmpfile_utils import (with_file_contents, with_named_file_contents,
                                                          with_directory_contents)

from anaconda_project.env_spec import (EnvSpec, _load_environment_yml, _load_requirements_txt,
                                       _find_out_of_sync_importable_spec)

from anaconda_project.conda_manager import CondaLockSet


def test_load_environment_yml():
    def check(filename):
        spec = _load_environment_yml(filename)

        assert spec is not None
        assert spec.name == 'foo'
        assert spec.conda_packages == ('bar=1.0', 'baz')
        assert spec.pip_packages == ('pippy', 'poppy==2.0')
        assert spec.channels == ('channel1', 'channel2')

        assert spec.logical_hash == 'e91a2263df510c9b188b132b801ba53aa99cc407'

    with_file_contents(
        """
name: foo
dependencies:
  - bar=1.0
  - baz
  - pip:
    - pippy
    - poppy==2.0
channels:
  - channel1
  - channel2
    """, check)


def test_load_environment_yml_with_prefix():
    def check(filename):
        spec = _load_environment_yml(filename)

        assert spec is not None
        assert spec.name == 'foo'
        assert spec.conda_packages == ('bar=1.0', 'baz')
        assert spec.pip_packages == ('pippy', 'poppy==2.0')
        assert spec.channels == ('channel1', 'channel2')

        assert spec.logical_hash == 'e91a2263df510c9b188b132b801ba53aa99cc407'

    with_file_contents(
        """
prefix: /opt/foo
dependencies:
  - bar=1.0
  - baz
  - pip:
    - pippy
    - poppy==2.0
channels:
  - channel1
  - channel2
    """, check)


def test_load_environment_yml_no_name():
    def check(filename):
        spec = _load_environment_yml(filename)

        assert spec is not None
        assert spec.name == os.path.basename(filename)
        assert spec.conda_packages == ('bar=1.0', 'baz')
        assert spec.pip_packages == ('pippy', 'poppy==2.0')
        assert spec.channels == ('channel1', 'channel2')

        assert spec.logical_hash == 'e91a2263df510c9b188b132b801ba53aa99cc407'

    with_file_contents(
        """
dependencies:
  - bar=1.0
  - baz
  - pip:
    - pippy
    - poppy==2.0
channels:
  - channel1
  - channel2
    """, check)


def test_load_environment_yml_with_broken_sections():
    def check(filename):
        spec = _load_environment_yml(filename)

        assert spec is not None
        assert spec.name == 'foo'
        assert spec.conda_packages == ()
        assert spec.pip_packages == ()
        assert spec.channels == ()

    with_file_contents("""
name: foo
dependencies: 42
channels: 57
    """, check)


def test_load_environment_yml_with_broken_pip_section():
    def check(filename):
        spec = _load_environment_yml(filename)

        assert spec is not None
        assert spec.name == 'foo'
        assert spec.conda_packages == ()
        assert spec.pip_packages == ()
        assert spec.channels == ()

    with_file_contents("""
name: foo
dependencies:
 - pip: 42
channels: 57
    """, check)


def test_load_requirements_txt():
    def check(filename):
        spec = _load_requirements_txt(filename)

        assert spec is not None
        assert spec.name == 'default'
        assert spec.conda_packages == ()
        assert spec.channels == ()
        assert spec.pip_packages == ('MyApp', 'Framework==0.9.4', 'Library>=0.2',
                                     'svn+http://myrepo/svn/MyThing#egg=MyThing')
        assert spec.pip_package_names_set == set(('MyApp', 'Framework', 'Library', 'MyThing'))

        assert spec.logical_hash == '784ba385d4cd468756e3cbc57f33e97afdc38059'

    with_file_contents(
        """
MyApp
# Comment; this is a framework
Framework==0.9.4

  # blank line above this indented comment!
 Library>=0.2
-e svn+http://myrepo/svn/MyThing#egg=MyThing
--index-url http://example.com/private-pypi/
--find-links http://example.com/private-packages/
    """, check)


def test_load_recursive_requirements_txt():
    def check(dirname):
        spec = _load_requirements_txt(os.path.join(dirname, "requirements.txt"))

        assert spec is not None
        assert spec.name == 'default'
        assert spec.pip_packages == ('a', 'b', 'c', 'd')

    with_directory_contents(
        {
            "requirements.txt": """
a
b
-r more-requirements.txt
        """,
            "more-requirements.txt": """
c
d
"""
        }, check)


def test_find_in_sync_environment_yml():
    def check(filename):
        spec = _load_environment_yml(filename)

        assert spec is not None

        (desynced, name) = _find_out_of_sync_importable_spec([spec], os.path.dirname(filename))
        assert desynced is None
        assert name is None

    with_named_file_contents(
        "environment.yml", """
name: foo
dependencies:
  - bar=1.0
  - baz
  - pip:
    - pippy
    - poppy==2.0
channels:
  - channel1
  - channel2
    """, check)


def test_find_out_of_sync_environment_yml():
    def check(filename):
        spec = _load_environment_yml(filename)

        assert spec is not None

        changed = EnvSpec(name=spec.name,
                          conda_packages=spec.conda_packages[1:],
                          pip_packages=spec.pip_packages,
                          channels=spec.channels)

        (desynced, name) = _find_out_of_sync_importable_spec([changed], os.path.dirname(filename))
        assert desynced is not None
        assert desynced.logical_hash == spec.logical_hash
        assert name == os.path.basename(filename)

    with_named_file_contents(
        "environment.yaml", """
name: foo
dependencies:
  - bar=1.0
  - baz
  - pip:
    - pippy
    - poppy==2.0
channels:
  - channel1
  - channel2
    """, check)


def test_load_environment_yml_does_not_exist():
    spec = _load_environment_yml("nopenopenope")
    assert spec is None


def test_find_out_of_sync_does_not_exist():
    (spec, name) = _find_out_of_sync_importable_spec([], "nopenopenope")
    assert spec is None
    assert name is None


def test_to_json():
    # the stuff from this parent env spec should NOT end up in the JSON
    hi = EnvSpec(name="hi",
                 conda_packages=['q', 'r'],
                 pip_packages=['zoo', 'boo'],
                 channels=['x1', 'y1'],
                 inherit_from_names=(),
                 inherit_from=())
    spec = EnvSpec(name="foo",
                   description="The Foo Spec",
                   conda_packages=['a', 'b'],
                   pip_packages=['c', 'd'],
                   channels=['x', 'y'],
                   inherit_from_names=('hi', ),
                   inherit_from=(hi, ))
    json = spec.to_json()

    assert {
        'description': "The Foo Spec",
        'channels': ['x', 'y'],
        'inherit_from': 'hi',
        'packages': ['a', 'b', {
            'pip': ['c', 'd']
        }]
    } == json


def test_to_json_no_description_no_pip_no_inherit():
    # should be able to jsonify a spec with no description
    spec = EnvSpec(name="foo",
                   conda_packages=['a', 'b'],
                   pip_packages=[],
                   channels=['x', 'y'],
                   inherit_from_names=(),
                   inherit_from=())
    json = spec.to_json()

    assert {'channels': ['x', 'y'], 'packages': ['a', 'b']} == json


def test_to_json_multiple_inheritance():
    spec = EnvSpec(name="foo",
                   conda_packages=['a', 'b'],
                   pip_packages=['c', 'd'],
                   channels=['x', 'y'],
                   inherit_from_names=('hi', 'hello'))
    json = spec.to_json()

    assert {
        'channels': ['x', 'y'],
        'inherit_from': ['hi', 'hello'],
        'packages': ['a', 'b', {
            'pip': ['c', 'd']
        }]
    } == json


def test_diff_from():
    spec1 = EnvSpec(name="foo", conda_packages=['a', 'b'], pip_packages=['c', 'd'], channels=['x', 'y'])
    spec2 = EnvSpec(name="bar", conda_packages=['a', 'b', 'q'], pip_packages=['c'], channels=['x', 'y', 'z'])
    diff = spec2.diff_from(spec1)

    assert '  channels:\n      x\n      y\n    + z\n  a\n  b\n+ q\n  pip:\n      c\n    - d' == diff


def test_save_environment_yml():
    def check_save(spec, dirname):
        saved = os.path.join(dirname, 'saved.yml')
        spec.save_environment_yml(saved)

        spec2 = _load_environment_yml(saved)

        assert spec2 is not None
        assert spec2.name == 'foo'
        assert spec2.conda_packages == ('xyz', 'bar=1.0', 'baz', 'abc')
        assert spec2.pip_packages == ('pippy', 'poppy==2.0')
        assert spec2.channels == ('channel1', 'channel2')

        assert spec2.logical_hash == 'ee1be9dc875857a69ccabb96cb45b5b828a6dff9'

    def check(filename):
        spec = _load_environment_yml(filename)

        assert spec is not None
        assert spec.name == 'foo'
        assert spec.conda_packages == ('xyz', 'bar=1.0', 'baz', 'abc')
        assert spec.pip_packages == ('pippy', 'poppy==2.0')
        assert spec.channels == ('channel1', 'channel2')

        assert spec.logical_hash == 'ee1be9dc875857a69ccabb96cb45b5b828a6dff9'

        with_directory_contents({}, lambda dirname: check_save(spec, dirname))

    with_file_contents(
        """
name: foo
dependencies:
  - xyz
  - bar=1.0
  - baz
  - abc
  - pip:
    - pippy
    - poppy==2.0
channels:
  - channel1
  - channel2
    """, check)


def test_overwrite_packages_with_lock_set():
    lock_set = CondaLockSet({'all': ['a=1.0=1']},
                            platforms=['linux-32', 'linux-64', 'osx-64', 'osx-arm64', 'win-32', 'win-64'])
    spec = EnvSpec(name="foo",
                   conda_packages=['a', 'b'],
                   pip_packages=['c', 'd'],
                   channels=['x', 'y'],
                   lock_set=lock_set)

    # package "b" is now ignored
    assert ('a=1.0=1', ) == spec.conda_packages_for_create


def test_lock_set_affects_name_sets():
    lock_set = CondaLockSet({'all': ['a=1.0=1', 'q=2.0=2']},
                            platforms=['linux-32', 'linux-64', 'osx-64', 'osx-arm64', 'win-32', 'win-64'])
    spec = EnvSpec(name="foo",
                   conda_packages=['a', 'b'],
                   pip_packages=['c', 'd'],
                   channels=['x', 'y'],
                   lock_set=lock_set)

    assert ('a', 'b') == spec.conda_packages
    assert ('a=1.0=1', 'q=2.0=2') == spec.conda_packages_for_create
    assert set(['a', 'b']) == spec.conda_package_names_set
    assert set(['a', 'q']) == spec.conda_package_names_for_create_set


def test_lock_set_affects_hash():
    lock_set = CondaLockSet({'all': ['a=1.0=1']},
                            platforms=['linux-32', 'linux-64', 'osx-64', 'osx-arm64', 'win-32', 'win-64'])
    with_lock_spec = EnvSpec(name="foo",
                             conda_packages=['a', 'b'],
                             pip_packages=['c', 'd'],
                             channels=['x', 'y'],
                             lock_set=lock_set)
    without_lock_spec = EnvSpec(name=with_lock_spec.name,
                                conda_packages=with_lock_spec.conda_packages,
                                pip_packages=with_lock_spec.pip_packages,
                                channels=with_lock_spec.channels,
                                lock_set=None)

    assert with_lock_spec.conda_packages != with_lock_spec.conda_packages_for_create
    assert without_lock_spec.conda_packages == without_lock_spec.conda_packages_for_create

    assert without_lock_spec.logical_hash == without_lock_spec.locked_hash
    assert with_lock_spec.logical_hash != with_lock_spec.locked_hash
    assert with_lock_spec.logical_hash == without_lock_spec.logical_hash

    assert without_lock_spec.locked_hash == without_lock_spec.import_hash
    assert with_lock_spec.locked_hash != with_lock_spec.import_hash


def test_platforms_affect_hash():
    with_platforms_spec = EnvSpec(name="foo",
                                  conda_packages=['a', 'b'],
                                  pip_packages=['c', 'd'],
                                  channels=['x', 'y'],
                                  platforms=('linux-64', ))
    without_platforms_spec = EnvSpec(name=with_platforms_spec.name,
                                     conda_packages=with_platforms_spec.conda_packages,
                                     pip_packages=with_platforms_spec.pip_packages,
                                     channels=with_platforms_spec.channels,
                                     platforms=())

    assert with_platforms_spec.logical_hash != with_platforms_spec.locked_hash
    assert with_platforms_spec.logical_hash != with_platforms_spec.import_hash

    assert without_platforms_spec.logical_hash == without_platforms_spec.locked_hash
    assert without_platforms_spec.logical_hash == without_platforms_spec.import_hash
