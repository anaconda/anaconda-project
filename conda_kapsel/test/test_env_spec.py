# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import os

from conda_kapsel.internal.test.tmpfile_utils import (with_file_contents, with_named_file_contents,
                                                      with_directory_contents)

from conda_kapsel.env_spec import (EnvSpec, _load_environment_yml, _load_requirements_txt,
                                   _find_out_of_sync_importable_spec)


def test_load_environment_yml():
    def check(filename):
        spec = _load_environment_yml(filename)

        assert spec is not None
        assert spec.name == 'foo'
        assert spec.conda_packages == ('bar=1.0', 'baz')
        assert spec.pip_packages == ('pippy', 'poppy==2.0')
        assert spec.channels == ('channel1', 'channel2')

        assert spec.channels_and_packages_hash == 'e91a2263df510c9b188b132b801ba53aa99cc407'

    with_file_contents("""
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

        assert spec.channels_and_packages_hash == 'e91a2263df510c9b188b132b801ba53aa99cc407'

    with_file_contents("""
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

        assert spec.channels_and_packages_hash == 'e91a2263df510c9b188b132b801ba53aa99cc407'

    with_file_contents("""
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

        assert spec.channels_and_packages_hash == '784ba385d4cd468756e3cbc57f33e97afdc38059'

    with_file_contents("""
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

    with_named_file_contents("environment.yml", """
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
        assert desynced.channels_and_packages_hash == spec.channels_and_packages_hash
        assert name == os.path.basename(filename)

    with_named_file_contents("environment.yaml", """
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
                   conda_packages=['a', 'b'],
                   pip_packages=['c', 'd'],
                   channels=['x', 'y'],
                   inherit_from_names=('hi', ),
                   inherit_from=(hi, ))
    json = spec.to_json()

    assert {'channels': ['x', 'y'], 'inherit_from': 'hi', 'packages': ['a', 'b', {'pip': ['c', 'd']}]} == json


def test_to_json_multiple_inheritance():
    spec = EnvSpec(name="foo",
                   conda_packages=['a', 'b'],
                   pip_packages=['c', 'd'],
                   channels=['x', 'y'],
                   inherit_from_names=('hi', 'hello'))
    json = spec.to_json()

    assert {'channels': ['x', 'y'],
            'inherit_from': ['hi', 'hello'],
            'packages': ['a', 'b', {'pip': ['c', 'd']}]} == json


def test_diff_from():
    spec1 = EnvSpec(name="foo", conda_packages=['a', 'b'], pip_packages=['c', 'd'], channels=['x', 'y'])
    spec2 = EnvSpec(name="bar", conda_packages=['a', 'b', 'q'], pip_packages=['c'], channels=['x', 'y', 'z'])
    diff = spec2.diff_from(spec1)

    assert '  channels:\n      x\n      y\n    + z\n  a\n  b\n+ q\n  pip:\n      c\n    - d' == diff
