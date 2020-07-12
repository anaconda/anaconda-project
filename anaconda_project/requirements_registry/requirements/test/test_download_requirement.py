# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
import hashlib
import os

from anaconda_project.local_state_file import LocalStateFile
from anaconda_project.requirements_registry.registry import RequirementsRegistry
from anaconda_project.requirements_registry.requirement import UserConfigOverrides
from anaconda_project.requirements_registry.requirements.download import DownloadRequirement

from anaconda_project.internal.test.tmpfile_utils import with_directory_contents

ENV_VAR = 'DATAFILE'


def test_filename_not_set():
    def check_not_set(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        requirement = DownloadRequirement(registry=RequirementsRegistry(),
                                          env_var=ENV_VAR,
                                          url='http://example.com',
                                          filename=ENV_VAR)
        status = requirement.check_status(dict(PROJECT_DIR=dirname), local_state, 'default', UserConfigOverrides())
        assert not status
        assert "Environment variable {} is not set.".format(ENV_VAR) == status.status_description

    with_directory_contents({}, check_not_set)


def test_download_filename_missing():
    def check_missing_filename(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        filename = '/data.zip'
        requirement = DownloadRequirement(registry=RequirementsRegistry(),
                                          env_var=ENV_VAR,
                                          url='http://localhost/data.zip',
                                          filename='data.zip')
        status = requirement.check_status({
            ENV_VAR: filename,
            'PROJECT_DIR': dirname
        }, local_state, 'default', UserConfigOverrides())
        assert not status
        assert 'File not found: {}'.format(filename) == status.status_description

    with_directory_contents({}, check_missing_filename)


def make_file_with_checksum():
    datafile = ("column1,column2,column3\n"
                "value11,value12,value13\n"
                "value21,value22,value23\n"
                "value31,value32,value33")
    checksum = hashlib.md5()
    checksum.update(datafile.encode('utf-8'))
    digest = checksum.hexdigest()
    return datafile, digest


def test_download_checksum():
    datafile, digest = make_file_with_checksum()

    def verify_checksum(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        filename = os.path.join(dirname, 'data.zip')
        requirement = DownloadRequirement(registry=RequirementsRegistry(),
                                          env_var=ENV_VAR,
                                          url='http://localhost/data.zip',
                                          filename='data.zip',
                                          hash_algorithm='md5',
                                          hash_value=digest)
        status = requirement.check_status({
            ENV_VAR: filename,
            'PROJECT_DIR': dirname
        }, local_state, 'default', UserConfigOverrides())
        assert 'File downloaded to {}'.format(filename) == status.status_description
        assert status

    with_directory_contents({'data.zip': datafile}, verify_checksum)


def test_download_with_no_checksum():
    datafile, digest = make_file_with_checksum()

    def downloaded_file_valid(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        filename = os.path.join(dirname, 'data.zip')
        requirement = DownloadRequirement(registry=RequirementsRegistry(),
                                          env_var=ENV_VAR,
                                          url='http://localhost/data.zip',
                                          filename='data.zip')
        status = requirement.check_status({
            ENV_VAR: filename,
            'PROJECT_DIR': dirname
        }, local_state, 'default', UserConfigOverrides())
        assert status
        assert 'File downloaded to {}'.format(filename) == status.status_description

    with_directory_contents({'data.zip': datafile}, downloaded_file_valid)


def test_use_variable_name_for_filename():
    problems = []
    kwargs = DownloadRequirement._parse(varname='FOO', item='http://example.com/', problems=problems)
    assert [] == problems
    assert kwargs['filename'] == 'FOO'
    assert kwargs['url'] == 'http://example.com/'
    assert not kwargs['unzip']


def test_checksum_is_not_a_string():
    problems = []
    kwargs = DownloadRequirement._parse(varname='FOO', item=dict(url='http://example.com/', md5=[]), problems=problems)
    assert ['Checksum value for FOO should be a string not [].'] == problems
    assert kwargs is None


def test_description_is_not_a_string():
    problems = []
    kwargs = DownloadRequirement._parse(varname='FOO',
                                        item=dict(url='http://example.com/', description=[]),
                                        problems=problems)
    assert ["'description' field for download item FOO is not a string"] == problems
    assert kwargs is None


def test_description_property():
    problems = []
    kwargs = DownloadRequirement._parse(varname='FOO',
                                        item=dict(url='http://example.com/', description="hi"),
                                        problems=problems)
    assert [] == problems
    assert kwargs['description'] == 'hi'
    req = DownloadRequirement(RequirementsRegistry(), **kwargs)
    assert req.title == 'FOO'


def test_download_item_is_a_list_not_a_string_or_dict():
    problems = []
    kwargs = DownloadRequirement._parse(varname='FOO', item=[], problems=problems)
    assert ["Download name FOO should be followed by a URL string or a dictionary describing the download."] == problems
    assert kwargs is None


def test_download_item_is_none_not_a_string_or_dict():
    problems = []
    kwargs = DownloadRequirement._parse(varname='FOO', item=None, problems=problems)
    assert ["Download name FOO should be followed by a URL string or a dictionary describing the download."] == problems
    assert kwargs is None


def test_unzip_is_not_a_bool():
    problems = []
    kwargs = DownloadRequirement._parse(varname='FOO',
                                        item=dict(url='http://example.com/', unzip=[]),
                                        problems=problems)
    assert ["Value of 'unzip' for download item FOO should be a boolean, not []."] == problems
    assert kwargs is None


def test_use_unzip_if_url_ends_in_zip():
    problems = []
    kwargs = DownloadRequirement._parse(varname='FOO', item='http://example.com/bar.zip', problems=problems)
    assert [] == problems
    assert kwargs['filename'] == 'bar'
    assert kwargs['url'] == 'http://example.com/bar.zip'
    assert kwargs['unzip']
    req = DownloadRequirement(RequirementsRegistry(), **kwargs)
    assert req.filename == 'bar'
    assert req.url == 'http://example.com/bar.zip'
    assert req.unzip


def test_allow_manual_override_of_use_unzip_if_url_ends_in_zip():
    problems = []
    kwargs = DownloadRequirement._parse(varname='FOO',
                                        item=dict(url='http://example.com/bar.zip', unzip=False),
                                        problems=problems)
    assert [] == problems
    assert kwargs['filename'] == 'bar.zip'
    assert kwargs['url'] == 'http://example.com/bar.zip'
    assert not kwargs['unzip']

    req = DownloadRequirement(RequirementsRegistry(), **kwargs)
    assert req.filename == 'bar.zip'
    assert req.url == 'http://example.com/bar.zip'
    assert not req.unzip


def test_use_unzip_if_url_ends_in_zip_and_filename_does_not():
    problems = []
    kwargs = DownloadRequirement._parse(varname='FOO',
                                        item=dict(url='http://example.com/bar.zip', filename='something'),
                                        problems=problems)
    assert [] == problems
    assert kwargs['filename'] == 'something'
    assert kwargs['url'] == 'http://example.com/bar.zip'
    assert kwargs['unzip']


def test_no_unzip_if_url_ends_in_zip_and_filename_also_does():
    problems = []
    kwargs = DownloadRequirement._parse(varname='FOO',
                                        item=dict(url='http://example.com/bar.zip', filename='something.zip'),
                                        problems=problems)
    assert [] == problems
    assert kwargs['filename'] == 'something.zip'
    assert kwargs['url'] == 'http://example.com/bar.zip'
    assert not kwargs['unzip']
