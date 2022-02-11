# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import codecs
import json
import os
import platform
import pytest
import time
from pprint import pprint

from anaconda_project.env_spec import EnvSpec
from anaconda_project.conda_manager import (CondaManagerError, CondaLockSet)
from anaconda_project import __version__ as version
from anaconda_project.frontend import NullFrontend

from anaconda_project.internal.default_conda_manager import (DefaultCondaManager, _extract_common)
import anaconda_project.internal.pip_api as pip_api
import anaconda_project.internal.conda_api as conda_api

from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.internal.test.test_conda_api import monkeypatch_conda_not_to_use_links

if platform.system() == 'Windows':
    PYTHON_BINARY = "python.exe"
    IPYTHON_BINARY = "Scripts\\ipython.exe"
    FLAKE8_BINARY = "Scripts\\flake8.exe"
    # Use a different package from the test env due to weird CI path/env errors
    PYINSTRUMENT_BINARY = "Scripts\\pyinstrument.exe"
else:
    PYTHON_BINARY = "bin/python"
    IPYTHON_BINARY = "bin/ipython"
    FLAKE8_BINARY = "bin/flake8"
    # Use a different package from the test env due to weird CI path/env errors
    PYINSTRUMENT_BINARY = "bin/pyinstrument"

test_spec = EnvSpec(name='myenv', conda_packages=['ipython', 'python=3.8'], pip_packages=['pyinstrument'], channels=[])


def test_current_platform_unsupported_by_env_spec(monkeypatch):
    lock_set = CondaLockSet(package_specs_by_platform={'all': []}, platforms=conda_api.default_platforms)
    spec = EnvSpec(name='myenv',
                   conda_packages=['ipython'],
                   pip_packages=['flake8'],
                   channels=[],
                   platforms=['commodore-64', 'apple-2'],
                   lock_set=lock_set)

    def do_test(dirname):
        envdir = os.path.join(dirname, spec.name)

        manager = DefaultCondaManager(frontend=NullFrontend())

        deviations = manager.find_environment_deviations(envdir, spec)

        error = "Env spec 'myenv' does not support current platform %s (it supports: apple-2, commodore-64)" % \
                conda_api.current_platform()
        assert error == deviations.summary

        with pytest.raises(CondaManagerError) as excinfo:
            manager.fix_environment_deviations(envdir, spec, deviations=deviations)
        assert str(excinfo.value).startswith("Unable to update environment at ")

    with_directory_contents(dict(), do_test)


def test_current_platform_unsupported_by_lock_set(monkeypatch):
    lock_set = CondaLockSet(package_specs_by_platform={'all': []}, platforms=[])
    spec = EnvSpec(name='myenv',
                   conda_packages=['ipython'],
                   pip_packages=['flake8'],
                   channels=[],
                   platforms=conda_api.default_platforms_with_current(),
                   lock_set=lock_set)

    def do_test(dirname):
        envdir = os.path.join(dirname, spec.name)

        manager = DefaultCondaManager(frontend=NullFrontend())

        deviations = manager.find_environment_deviations(envdir, spec)

        error = "Env spec 'myenv' does not have the current platform %s in the lock file" % conda_api.current_platform()
        assert error == deviations.summary

        with pytest.raises(CondaManagerError) as excinfo:
            manager.fix_environment_deviations(envdir, spec, deviations=deviations)
        assert str(excinfo.value).startswith("Unable to update environment at ")

    with_directory_contents(dict(), do_test)


@pytest.mark.slow
def test_conda_create_and_install_and_remove(monkeypatch):
    monkeypatch_conda_not_to_use_links(monkeypatch)

    spec = test_spec
    assert spec.conda_packages == ('ipython', 'python=3.8')
    assert spec.pip_packages == ('pyinstrument', )

    spec_with_phony_pip_package = EnvSpec(name='myenv',
                                          conda_packages=['ipython'],
                                          pip_packages=['pyinstrument', 'nope_not_a_thing'],
                                          channels=[])
    assert spec_with_phony_pip_package.conda_packages == ('ipython', )
    assert spec_with_phony_pip_package.pip_packages == ('pyinstrument', 'nope_not_a_thing')
    assert spec_with_phony_pip_package.pip_package_names_set == set(('pyinstrument', 'nope_not_a_thing'))

    # package url is supposed to be on a nonexistent port, if it
    # causes a problem we need to mock
    spec_with_bad_url_pip_package = EnvSpec(name='myenv',
                                            conda_packages=['ipython'],
                                            pip_packages=['pyinstrument', 'https://127.0.0.1:24729/nope#egg=phony'],
                                            channels=[])
    assert spec_with_bad_url_pip_package.conda_packages == ('ipython', )
    assert spec_with_bad_url_pip_package.pip_packages == ('pyinstrument', 'https://127.0.0.1:24729/nope#egg=phony')
    assert spec_with_bad_url_pip_package.pip_package_names_set == set(('pyinstrument', 'phony'))

    spec_with_old_ipython = EnvSpec(name='myenv',
                                    conda_packages=['ipython=7.10.1'],
                                    pip_packages=['pyinstrument'],
                                    channels=[])
    assert spec_with_old_ipython.conda_packages == ('ipython=7.10.1', )

    spec_with_bokeh = EnvSpec(name='myenv', conda_packages=['bokeh'], pip_packages=['pyinstrument'], channels=[])
    assert spec_with_bokeh.conda_packages == ('bokeh', )

    spec_with_bokeh_and_old_ipython = EnvSpec(name='myenv',
                                              conda_packages=['bokeh', 'ipython=7.10.1'],
                                              pip_packages=['pyinstrument'],
                                              channels=[])
    assert spec_with_bokeh_and_old_ipython.conda_packages == (
        'bokeh',
        'ipython=7.10.1',
    )

    def do_test(dirname):
        from codecs import open as real_open

        envdir = os.path.join(dirname, spec.name)

        manager = DefaultCondaManager(frontend=NullFrontend())

        is_readonly = dict(readonly=False)

        def mock_open(*args, **kwargs):
            if is_readonly['readonly']:
                raise IOError("did not open")
            return real_open(*args, **kwargs)

        monkeypatch.setattr('codecs.open', mock_open)

        assert not os.path.isdir(envdir)
        assert not os.path.exists(os.path.join(envdir, IPYTHON_BINARY))
        assert not os.path.exists(os.path.join(envdir, FLAKE8_BINARY))
        assert not manager._timestamp_file_up_to_date(envdir, spec)

        deviations = manager.find_environment_deviations(envdir, spec)

        assert set(deviations.missing_packages) == {'python', 'ipython'}
        assert deviations.missing_pip_packages == ('pyinstrument', )

        # with create=False, we won't create the env
        with pytest.raises(CondaManagerError) as excinfo:
            manager.fix_environment_deviations(envdir, spec, deviations, create=False)
            assert 'does not exist' in str(excinfo.value)

        assert not os.path.isdir(envdir)

        # now create the env
        manager.fix_environment_deviations(envdir, spec, deviations)

        assert os.path.isdir(envdir)
        assert os.path.isdir(os.path.join(envdir, "conda-meta"))
        assert os.path.exists(os.path.join(envdir, IPYTHON_BINARY))
        assert os.path.exists(os.path.join(envdir, PYINSTRUMENT_BINARY))

        assert manager._timestamp_file_up_to_date(envdir, spec)
        assert not manager._timestamp_file_up_to_date(envdir, spec_with_phony_pip_package)

        # test bad pip package throws error
        deviations = manager.find_environment_deviations(envdir, spec_with_phony_pip_package)

        assert deviations.missing_packages == ()
        assert deviations.wrong_version_packages == ()
        assert deviations.missing_pip_packages == ('nope_not_a_thing', )

        with pytest.raises(CondaManagerError) as excinfo:
            manager.fix_environment_deviations(envdir, spec_with_phony_pip_package, deviations)
        assert 'Failed to install missing pip packages' in str(excinfo.value)
        assert not manager._timestamp_file_up_to_date(envdir, spec_with_phony_pip_package)

        # test bad url package throws error
        deviations = manager.find_environment_deviations(envdir, spec_with_bad_url_pip_package)

        assert deviations.missing_packages == ()
        assert deviations.wrong_version_packages == ()
        assert deviations.missing_pip_packages == ('phony', )

        with pytest.raises(CondaManagerError) as excinfo:
            manager.fix_environment_deviations(envdir, spec_with_bad_url_pip_package, deviations)
        assert 'Failed to install missing pip packages' in str(excinfo.value)
        assert not manager._timestamp_file_up_to_date(envdir, spec_with_bad_url_pip_package)

        # test we notice wrong ipython version AND missing bokeh AND readonly environment
        is_readonly['readonly'] = True
        deviations = manager.find_environment_deviations(envdir, spec_with_bokeh_and_old_ipython)

        assert deviations.missing_packages == ('bokeh', )
        assert deviations.wrong_version_packages == ('ipython', )
        assert deviations.unfixable
        is_readonly['readonly'] = False

        # test we notice only missing bokeh
        deviations = manager.find_environment_deviations(envdir, spec_with_bokeh)

        assert deviations.missing_packages == ('bokeh', )
        assert deviations.wrong_version_packages == ()
        assert not deviations.unfixable

        # test we notice wrong ipython version and can downgrade
        deviations = manager.find_environment_deviations(envdir, spec_with_old_ipython)

        assert deviations.missing_packages == ()
        assert deviations.wrong_version_packages == ('ipython', )
        assert not deviations.unfixable

        manager.fix_environment_deviations(envdir, spec_with_old_ipython, deviations)

        assert manager._timestamp_file_up_to_date(envdir, spec_with_old_ipython)

        deviations = manager.find_environment_deviations(envdir, spec_with_old_ipython)
        assert deviations.missing_packages == ()
        assert deviations.wrong_version_packages == ()

        # update timestamp; this doesn't re-upgrade because `spec` doesn't
        # specify an ipython version
        assert not manager._timestamp_file_up_to_date(envdir, spec)

        deviations = manager.find_environment_deviations(envdir, spec)

        assert deviations.missing_packages == ()
        assert deviations.wrong_version_packages == ()

        # fix_environment_deviations should be a no-op on readonly envs
        # with no deviations, in particular the time stamp file should
        # not be changed and therefore not be up to date
        is_readonly['readonly'] = True
        manager.fix_environment_deviations(envdir, spec, deviations)
        assert not manager._timestamp_file_up_to_date(envdir, spec)

        # when the environment is readwrite, the timestamp file should
        # be updated
        is_readonly['readonly'] = False
        manager.fix_environment_deviations(envdir, spec, deviations)
        assert manager._timestamp_file_up_to_date(envdir, spec)

        deviations = manager.find_environment_deviations(envdir, spec)
        assert deviations.missing_packages == ()
        assert deviations.wrong_version_packages == ()

        # test that we can remove a package
        assert manager._timestamp_file_up_to_date(envdir, spec)
        time.sleep(1)  # removal is fast enough to break our timestamp resolution
        manager.remove_packages(prefix=envdir, packages=['ipython'])
        assert not os.path.exists(os.path.join(envdir, IPYTHON_BINARY))
        assert not manager._timestamp_file_up_to_date(envdir, spec)

        # test for error removing
        with pytest.raises(CondaManagerError) as excinfo:
            manager.remove_packages(prefix=envdir, packages=['ipython'])
        # different versions of conda word this differently
        message = str(excinfo.value)
        valid_strings = ('no packages found to remove', 'Package not found', "named 'ipython' found to remove",
                         'PackagesNotFoundError:', "is missing from the environment")
        assert any(s in message for s in valid_strings)
        assert not manager._timestamp_file_up_to_date(envdir, spec)

        # test failure to exec pip
        def mock_call_pip(*args, **kwargs):
            raise pip_api.PipError("pip fail")

        monkeypatch.setattr('anaconda_project.internal.pip_api._call_pip', mock_call_pip)

        with pytest.raises(CondaManagerError) as excinfo:
            deviations = manager.find_environment_deviations(envdir, spec)
        assert 'pip failed while listing' in str(excinfo.value)

    with_directory_contents(dict(), do_test)


@pytest.mark.slow
def test_timestamp_file_works(monkeypatch):
    monkeypatch_conda_not_to_use_links(monkeypatch)

    spec = test_spec

    def do_test(dirname):
        envdir = os.path.join(dirname, spec.name)

        manager = DefaultCondaManager(frontend=NullFrontend())

        def print_timestamps(when):
            newest_in_prefix = 0
            for d in manager._timestamp_comparison_directories(envdir):
                try:
                    t = os.path.getmtime(d)
                except Exception:
                    t = 0
                if t > newest_in_prefix:
                    newest_in_prefix = t
            timestamp_fname = manager._timestamp_file(envdir, spec)
            try:
                timestamp_file = os.path.getmtime(timestamp_fname)
            except Exception:
                timestamp_file = 0
            print("%s: timestamp file %d prefix %d diff %g" %
                  (when, timestamp_file, newest_in_prefix, newest_in_prefix - timestamp_file))

        print_timestamps("before env creation")

        assert not os.path.isdir(envdir)
        assert not os.path.exists(os.path.join(envdir, IPYTHON_BINARY))
        assert not os.path.exists(os.path.join(envdir, PYINSTRUMENT_BINARY))
        assert not manager._timestamp_file_up_to_date(envdir, spec)

        deviations = manager.find_environment_deviations(envdir, spec)

        assert set(deviations.missing_packages) == {'python', 'ipython'}
        assert deviations.missing_pip_packages == ('pyinstrument', )
        assert not deviations.ok

        manager.fix_environment_deviations(envdir, spec, deviations)

        print_timestamps("after fixing deviations")

        assert os.path.isdir(envdir)
        assert os.path.isdir(os.path.join(envdir, "conda-meta"))
        assert os.path.exists(os.path.join(envdir, IPYTHON_BINARY))
        assert os.path.exists(os.path.join(envdir, PYINSTRUMENT_BINARY))

        assert manager._timestamp_file_up_to_date(envdir, spec)

        called = []
        from anaconda_project.internal.pip_api import installed as real_pip_installed
        from anaconda_project.internal.conda_api import installed as real_conda_installed

        def traced_pip_installed(*args, **kwargs):
            called.append(("pip_api.installed", args, kwargs))
            return real_pip_installed(*args, **kwargs)

        monkeypatch.setattr('anaconda_project.internal.pip_api.installed', traced_pip_installed)

        def trace_conda_installed(*args, **kwargs):
            called.append(("conda_api.installed", args, kwargs))
            return real_conda_installed(*args, **kwargs)

        monkeypatch.setattr('anaconda_project.internal.conda_api.installed', trace_conda_installed)

        deviations = manager.find_environment_deviations(envdir, spec)

        assert [] == called

        assert deviations.missing_packages == ()
        assert deviations.missing_pip_packages == ()
        assert deviations.ok

        assert manager._timestamp_file_up_to_date(envdir, spec)

        # now modify conda-meta and check that we DO call the package managers
        time.sleep(1.1)  # be sure we are in a new second
        conda_meta_dir = os.path.join(envdir, "conda-meta")
        print("conda-meta original timestamp: %d" % os.path.getmtime(conda_meta_dir))
        inside_conda_meta = os.path.join(conda_meta_dir, "thing.txt")
        with codecs.open(inside_conda_meta, 'w', encoding='utf-8') as f:
            f.write(u"This file should change the mtime on conda-meta\n")
        print("file inside conda-meta %d and conda-meta itself %d" %
              (os.path.getmtime(inside_conda_meta), os.path.getmtime(conda_meta_dir)))
        os.remove(inside_conda_meta)

        print_timestamps("after touching conda-meta")

        assert not manager._timestamp_file_up_to_date(envdir, spec)

        deviations = manager.find_environment_deviations(envdir, spec)

        assert len(called) == 2

        assert deviations.missing_packages == ()
        assert deviations.missing_pip_packages == ()
        # deviations should not be ok (due to timestamp)
        assert not deviations.ok

        assert not manager._timestamp_file_up_to_date(envdir, spec)

        # we want to be sure we update the timestamp file even though
        # there wasn't any actual work to do
        manager.fix_environment_deviations(envdir, spec, deviations)

        print_timestamps("after fixing deviations 2")

        assert manager._timestamp_file_up_to_date(envdir, spec)

    with_directory_contents(dict(), do_test)


def test_timestamp_file_ignores_failed_write(monkeypatch):
    monkeypatch_conda_not_to_use_links(monkeypatch)

    spec = test_spec

    def do_test(dirname):
        from codecs import open as real_open

        envdir = os.path.join(dirname, spec.name)

        manager = DefaultCondaManager(frontend=NullFrontend())

        counts = dict(calls=0)

        def mock_open(*args, **kwargs):
            counts['calls'] += 1
            if counts['calls'] == 1:
                raise IOError("did not open")
            else:
                return real_open(*args, **kwargs)

        monkeypatch.setattr('codecs.open', mock_open)

        # this should NOT throw but also should not write the
        # timestamp file (we ignore errors)
        filename = manager._timestamp_file(envdir, spec)
        assert filename.startswith(envdir)
        assert not os.path.exists(filename)
        manager._write_timestamp_file(envdir, spec)
        assert not os.path.exists(filename)
        # the second time we really wsrite it (this is to prove we
        # are looking at the right filename)
        manager._write_timestamp_file(envdir, spec)
        assert os.path.exists(filename)

        # check on the file contents
        with real_open(filename, 'r', encoding='utf-8') as f:
            content = json.loads(f.read())
            assert dict(anaconda_project_version=version) == content

    with_directory_contents(dict(), do_test)


def test_resolve_dependencies_with_conda_api_mock(monkeypatch):
    def mock_resolve_dependencies(pkgs, platform, channels):
        return [('bokeh', '0.12.4', '0'), ('thing', '1.0', '1')]

    monkeypatch.setattr('anaconda_project.internal.conda_api.resolve_dependencies', mock_resolve_dependencies)

    manager = DefaultCondaManager(frontend=NullFrontend())

    lock_set = manager.resolve_dependencies(['bokeh'], channels=(), platforms=(conda_api.current_platform(), ))
    assert lock_set.package_specs_for_current_platform == ('bokeh=0.12.4=0', 'thing=1.0=1')


@pytest.mark.slow
def test_resolve_dependencies_with_actual_conda():
    manager = DefaultCondaManager(frontend=NullFrontend())

    lock_set = manager.resolve_dependencies(['bokeh'], channels=(), platforms=(conda_api.current_platform(), ))
    specs = lock_set.package_specs_for_current_platform
    pprint(specs)
    names = [conda_api.parse_spec(spec).name for spec in specs]
    assert 'bokeh' in names
    assert len(specs) > 5  # 5 is an arbitrary number of deps that surely bokeh has


def test_resolve_dependencies_with_conda_api_mock_raises_error(monkeypatch):
    def mock_resolve_dependencies(pkgs, platform, channels):
        raise conda_api.CondaError("nope")

    monkeypatch.setattr('anaconda_project.internal.conda_api.resolve_dependencies', mock_resolve_dependencies)

    manager = DefaultCondaManager(frontend=NullFrontend())

    with pytest.raises(CondaManagerError) as excinfo:
        manager.resolve_dependencies(['bokeh'], channels=(), platforms=(conda_api.current_platform(), ))

    assert 'Error resolving for' in str(excinfo.value)


def test_installed_version_comparison(monkeypatch):
    def check(dirname):
        prefix = os.path.join(dirname, "myenv")
        os.makedirs(os.path.join(prefix, 'conda-meta'))

        def mock_installed(prefix):
            return {'bokeh': ('bokeh', '0.12.4', '1')}

        monkeypatch.setattr('anaconda_project.internal.conda_api.installed', mock_installed)

        spec_with_matching_bokeh = EnvSpec(name='myenv',
                                           conda_packages=['bokeh=0.12.4=1'],
                                           pip_packages=[],
                                           channels=[])
        spec_with_more_vague_bokeh = EnvSpec(name='myenv', conda_packages=['bokeh=0.12'], pip_packages=[], channels=[])
        spec_with_unspecified_bokeh = EnvSpec(name='myenv', conda_packages=['bokeh'], pip_packages=[], channels=[])
        spec_with_wrong_version_bokeh = EnvSpec(name='myenv',
                                                conda_packages=['bokeh=0.12.3'],
                                                pip_packages=[],
                                                channels=[])
        spec_with_wrong_build_bokeh = EnvSpec(name='myenv',
                                              conda_packages=['bokeh=0.12.4=0'],
                                              pip_packages=[],
                                              channels=[])

        manager = DefaultCondaManager(frontend=NullFrontend())

        deviations = manager.find_environment_deviations(prefix, spec_with_matching_bokeh)
        assert deviations.missing_packages == ()
        assert deviations.wrong_version_packages == ()

        deviations = manager.find_environment_deviations(prefix, spec_with_more_vague_bokeh)
        assert deviations.missing_packages == ()
        assert deviations.wrong_version_packages == ()

        deviations = manager.find_environment_deviations(prefix, spec_with_unspecified_bokeh)
        assert deviations.missing_packages == ()
        assert deviations.wrong_version_packages == ()

        deviations = manager.find_environment_deviations(prefix, spec_with_wrong_version_bokeh)
        assert deviations.missing_packages == ()
        assert deviations.wrong_version_packages == ('bokeh', )

        deviations = manager.find_environment_deviations(prefix, spec_with_wrong_build_bokeh)
        assert deviations.missing_packages == ()
        assert deviations.wrong_version_packages == ('bokeh', )

    with_directory_contents(dict(), check)


def test_extract_common():
    resolve_results = {
        'linux-32': ['linux-32-only', 'linux-only', 'unix-only', 'common'],
        'linux-64': ['linux-64-only', 'linux-only', 'unix-only', 'common'],
        'win-32': ['win-32-only', 'win-only', 'common'],
        'win-64': ['win-64-only', 'win-only', 'common'],
        'osx-64': ['osx-64-only', 'osx-only', 'unix-only', 'common']
    }
    factored = _extract_common(resolve_results)

    assert {
        'all': ['common'],
        'linux': ['linux-only'],
        'unix': ['unix-only'],
        'win': ['win-only'],
        'osx-64': ['osx-64-only', 'osx-only'],
        'linux-32': ['linux-32-only'],
        'linux-64': ['linux-64-only'],
        'win-32': ['win-32-only'],
        'win-64': ['win-64-only']
    } == factored


def test_extract_common_empty_deps():
    resolve_results = {}
    factored = _extract_common(resolve_results)

    assert {} == factored


def test_extract_common_just_one_platform():
    resolve_results = {'linux-64': ['a', 'b']}
    factored = _extract_common(resolve_results)

    assert {'linux-64': ['a', 'b']} == factored


def test_extract_common_nothing_in_common():
    resolve_results = {'linux-64': ['a', 'b'], 'linux-32': ['c', 'd']}
    factored = _extract_common(resolve_results)

    assert {'linux-64': ['a', 'b'], 'linux-32': ['c', 'd']} == factored


def test_extract_common_only_bits_differ():
    resolve_results = {'linux-64': ['a', 'b'], 'linux-32': ['a', 'b', 'c']}
    factored = _extract_common(resolve_results)

    assert {'linux': ['a', 'b'], 'linux-32': ['c']} == factored


def test_extract_common_only_unix():
    resolve_results = {'linux-64': ['a', 'b'], 'linux-32': ['a', 'b', 'c'], 'osx-64': ['a', 'b']}
    factored = _extract_common(resolve_results)

    assert {'unix': ['a', 'b'], 'linux-32': ['c']} == factored


def test_extract_common_unpopular_unix():
    resolve_results = {'linux-64': ['a', 'b'], 'linux-32': ['a', 'b', 'c'], 'osx-32': ['a', 'b']}
    factored = _extract_common(resolve_results)

    assert {'unix': ['a', 'b'], 'linux-32': ['c']} == factored
