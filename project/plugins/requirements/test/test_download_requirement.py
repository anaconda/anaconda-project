import hashlib
import os

from project.local_state_file import LocalStateFile
from project.plugins.registry import PluginRegistry
from project.plugins.requirements.download import DownloadRequirement

from project.internal.test.tmpfile_utils import with_directory_contents

ENV_VAR = 'DATAFILE'


def test_filename_not_set():
    def check_not_set(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        requirement = DownloadRequirement(registry=PluginRegistry(),
                                          env_var=ENV_VAR,
                                          url='http://example.com',
                                          filename=ENV_VAR)
        status = requirement.check_status(dict(PROJECT_DIR=dirname), local_state)
        assert not status
        assert "Environment variable {} is not set.".format(ENV_VAR) == status.status_description

    with_directory_contents({}, check_not_set)


def test_download_filename_missing():
    def check_missing_filename(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        filename = '/data.zip'
        requirement = DownloadRequirement(registry=PluginRegistry(),
                                          env_var=ENV_VAR,
                                          url='http://localhost/data.zip',
                                          filename='data.zip')
        status = requirement.check_status({ENV_VAR: filename, 'PROJECT_DIR': dirname}, local_state)
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
        requirement = DownloadRequirement(registry=PluginRegistry(),
                                          env_var=ENV_VAR,
                                          url='http://localhost/data.zip',
                                          filename='data.zip',
                                          hash_algorithm='md5',
                                          hash_value=digest)
        status = requirement.check_status({ENV_VAR: filename, 'PROJECT_DIR': dirname}, local_state)
        assert status
        assert 'File downloaded to {}'.format(filename) == status.status_description

    with_directory_contents({'data.zip': datafile}, verify_checksum)


def test_download_with_no_checksum():
    datafile, digest = make_file_with_checksum()

    def downloaded_file_valid(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        filename = os.path.join(dirname, 'data.zip')
        requirement = DownloadRequirement(registry=PluginRegistry(),
                                          env_var=ENV_VAR,
                                          url='http://localhost/data.zip',
                                          filename='data.zip')
        status = requirement.check_status({ENV_VAR: filename, 'PROJECT_DIR': dirname}, local_state)
        assert status
        assert 'File downloaded to {}'.format(filename) == status.status_description

    with_directory_contents({'data.zip': datafile}, downloaded_file_valid)


def test_download_wrong_checksum():
    datafile, digest = make_file_with_checksum()
    digest += '1'

    def downloaded_file_valid(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        filename = os.path.join(dirname, 'data.zip')
        requirement = DownloadRequirement(registry=PluginRegistry(),
                                          env_var=ENV_VAR,
                                          url='http://localhost/data.zip',
                                          filename='data.zip',
                                          hash_algorithm='md5',
                                          hash_value=digest)
        status = requirement.check_status({ENV_VAR: filename, 'PROJECT_DIR': dirname}, local_state)
        assert not status
        assert 'File download checksum error for {}'.format(filename) == status.status_description

    with_directory_contents({'data.zip': datafile}, downloaded_file_valid)


def test_download_error_readfile(monkeypatch):
    datafile, digest = make_file_with_checksum()
    digest += '1'

    def checksum_mock(self, fp):
        raise OSError()

    def downloaded_file_valid(dirname):
        local_state = LocalStateFile.load_for_directory(dirname)
        filename = os.path.join(dirname, 'data.zip')
        requirement = DownloadRequirement(registry=PluginRegistry(),
                                          env_var=ENV_VAR,
                                          url='http://localhost/data.zip',
                                          filename='data.zip',
                                          hash_algorithm='md5',
                                          hash_value=digest)
        monkeypatch.setattr('project.plugins.requirements.download.DownloadRequirement._checksum', checksum_mock)
        status = requirement.check_status({ENV_VAR: filename, 'PROJECT_DIR': dirname}, local_state)
        assert not status
        assert 'File referenced by: {} cannot be read ({})'.format(ENV_VAR, filename) == status.status_description

    with_directory_contents({'data.zip': datafile}, downloaded_file_valid)


def test_use_variable_name_for_filename():
    problems = []
    requirements = []
    DownloadRequirement.parse(PluginRegistry(),
                              varname='FOO',
                              item='http://example.com/',
                              problems=problems,
                              requirements=requirements)
    assert [] == problems
    assert len(requirements) == 1
    assert requirements[0].filename == 'FOO'
    assert requirements[0].url == 'http://example.com/'


def test_checksum_is_not_a_string():
    problems = []
    requirements = []
    DownloadRequirement.parse(PluginRegistry(),
                              varname='FOO',
                              item=dict(url='http://example.com/',
                                        md5=[]),
                              problems=problems,
                              requirements=requirements)
    assert ['Checksum value for FOO should be a string not [].'] == problems
    assert len(requirements) == 0
