import codecs
import os

import pytest

from project.internal.test.tmpfile_utils import with_directory_contents
from project.local_state_file import (LocalStateFile, LOCAL_STATE_FILENAME, LOCAL_STATE_DIRECTORY,
                                      SERVICE_RUN_STATES_SECTION)

LOCAL_STATE_FILENAME_WITH_DIR = os.path.join(LOCAL_STATE_DIRECTORY, LOCAL_STATE_FILENAME)


def test_create_missing_local_state_file():
    def create_file(dirname):
        filename = os.path.join(dirname, LOCAL_STATE_FILENAME_WITH_DIR)
        assert not os.path.exists(filename)
        local_state_file = LocalStateFile.load_for_directory(dirname)
        assert local_state_file is not None
        assert not os.path.exists(filename)
        local_state_file.save()
        assert os.path.exists(filename)
        with codecs.open(filename, 'r', 'utf-8') as file:
            contents = file.read()
            # this is sort of annoying that the default empty file
            # has {} in it, but in our real usage we should only
            # save the file if we set something in it probably.
            assert "# Anaconda local project state\n{}\n" == contents

    with_directory_contents(dict(), create_file)


def test_use_existing_local_state_file():
    def check_file(dirname):
        filename = os.path.join(dirname, LOCAL_STATE_FILENAME_WITH_DIR)
        assert os.path.exists(filename)
        local_state_file = LocalStateFile.load_for_directory(dirname)
        state = local_state_file.get_service_run_state("foobar")
        assert dict(port=42, shutdown_commands=[["foo"]]) == state

    sample_run_states = SERVICE_RUN_STATES_SECTION + ":\n  foobar: { port: 42, shutdown_commands: [[\"foo\"]] }\n"
    with_directory_contents({LOCAL_STATE_FILENAME_WITH_DIR: sample_run_states}, check_file)


def test_use_empty_existing_local_state_file():
    def check_file(dirname):
        filename = os.path.join(dirname, LOCAL_STATE_FILENAME_WITH_DIR)
        assert os.path.exists(filename)
        local_state_file = LocalStateFile.load_for_directory(dirname)
        state = local_state_file.get_service_run_state("foobar")
        assert dict() == state

    with_directory_contents({LOCAL_STATE_FILENAME_WITH_DIR: ""}, check_file)


def test_modify_run_state():
    def check_file(dirname):
        filename = os.path.join(dirname, LOCAL_STATE_FILENAME_WITH_DIR)
        assert os.path.exists(filename)
        local_state_file = LocalStateFile.load_for_directory(dirname)
        state = local_state_file.get_service_run_state("foobar")
        assert dict(port=42, shutdown_commands=[["foo"]]) == state
        local_state_file.set_service_run_state("foobar", dict(port=43, shutdown_commands=[]))
        local_state_file.save()
        changed = local_state_file.get_service_run_state("foobar")
        assert dict(port=43, shutdown_commands=[]) == changed

        # and we can reload it from scratch
        local_state_file2 = LocalStateFile.load_for_directory(dirname)
        changed2 = local_state_file2.get_service_run_state("foobar")
        assert dict(port=43, shutdown_commands=[]) == changed2

    sample_run_states = SERVICE_RUN_STATES_SECTION + ":\n  foobar: { port: 42, shutdown_commands: [[\"foo\"]] }\n"
    with_directory_contents({LOCAL_STATE_FILENAME_WITH_DIR: sample_run_states}, check_file)


def test_get_all_run_states():
    def check_file(dirname):
        filename = os.path.join(dirname, LOCAL_STATE_FILENAME_WITH_DIR)
        assert os.path.exists(filename)
        local_state_file = LocalStateFile.load_for_directory(dirname)
        state = local_state_file.get_service_run_state("foo")
        assert dict(port=42) == state
        state = local_state_file.get_service_run_state("bar")
        assert dict(port=43) == state
        states = local_state_file.get_all_service_run_states()
        assert dict(foo=dict(port=42), bar=dict(port=43)) == states

    sample_run_states = SERVICE_RUN_STATES_SECTION + ":\n  foo: { port: 42 }\n  bar: { port: 43 }\n"
    with_directory_contents({LOCAL_STATE_FILENAME_WITH_DIR: sample_run_states}, check_file)


def test_run_state_must_be_dict():
    def check_cannot_use_non_dict(dirname):
        local_state_file = LocalStateFile.load_for_directory(dirname)
        with pytest.raises(ValueError) as excinfo:
            local_state_file.set_service_run_state("foo", 42)
        assert "service state should be a dict" in repr(excinfo.value)

    with_directory_contents(dict(), check_cannot_use_non_dict)
