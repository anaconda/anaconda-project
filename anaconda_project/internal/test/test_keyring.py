# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from anaconda_project.internal import keyring


def _with_fallback_keyring(f):
    try:
        keyring.enable_fallback_keyring()
        f()
    finally:
        keyring.disable_fallback_keyring()


def _monkeypatch_keyring(monkeypatch):
    keyring.reset_keyring_module()
    passwords = dict(anaconda=dict())

    def mock_set_password(system, username, password):
        passwords[system][username] = password

    monkeypatch.setattr('keyring.set_password', mock_set_password)

    def mock_get_password(system, username):
        return passwords[system].get(username, None)

    monkeypatch.setattr('keyring.get_password', mock_get_password)

    def mock_delete_password(system, username):
        if username in passwords[system]:
            del passwords[system][username]

    monkeypatch.setattr('keyring.delete_password', mock_delete_password)

    return passwords


def _monkeypatch_broken_keyring(monkeypatch):
    keyring.reset_keyring_module()

    def mock_set_password(system, username, password):
        raise RuntimeError("keyring system is busted")

    monkeypatch.setattr('keyring.set_password', mock_set_password)

    def mock_get_password(system, username):
        raise RuntimeError("keyring system is busted")

    monkeypatch.setattr('keyring.get_password', mock_get_password)

    def mock_delete_password(system, username):
        raise RuntimeError("keyring system is busted")

    monkeypatch.setattr('keyring.delete_password', mock_delete_password)


def test_get_set_using_fallback():
    def check():
        keyring.set("abc", "FOO", "bar")
        assert "bar" == keyring.get("abc", "FOO")

    _with_fallback_keyring(check)

    keyring.reset_keyring_module()


def test_get_set_using_mock(monkeypatch):
    passwords = _monkeypatch_keyring(monkeypatch)

    keyring.set("abc", "FOO", "bar")
    assert "bar" == keyring.get("abc", "FOO")

    assert dict(anaconda={'abc/FOO': 'bar'}) == passwords

    keyring.reset_keyring_module()


def test_unset_using_fallback():
    def check():
        keyring.set("abc", "FOO", "bar")
        assert "bar" == keyring.get("abc", "FOO")
        keyring.unset("abc", "FOO")
        assert keyring.get("abc", "FOO") is None

    _with_fallback_keyring(check)

    keyring.reset_keyring_module()


def test_unset_using_mock(monkeypatch):
    passwords = _monkeypatch_keyring(monkeypatch)

    keyring.set("abc", "FOO", "bar")
    assert "bar" == keyring.get("abc", "FOO")
    keyring.unset("abc", "FOO")
    assert keyring.get("abc", "FOO") is None

    assert dict(anaconda=dict()) == passwords

    keyring.reset_keyring_module()


expected_broken_message = ("Unable to use system keyring to store passwords.\n" +
                           "  (Exception %s a password: keyring system is busted)\n")


def test_set_get_using_broken(monkeypatch, capsys):
    _monkeypatch_broken_keyring(monkeypatch)

    keyring.set("abc", "FOO", "bar")
    assert "bar" == keyring.get("abc", "FOO")

    (out, err) = capsys.readouterr()
    assert '' == out
    assert (expected_broken_message % "setting") == err

    keyring.reset_keyring_module()


def test_get_using_broken(monkeypatch, capsys):
    _monkeypatch_broken_keyring(monkeypatch)

    assert keyring.get("abc", "FOO") is None

    (out, err) = capsys.readouterr()
    assert '' == out
    assert (expected_broken_message % "getting") == err

    keyring.reset_keyring_module()


def test_unset_using_broken(monkeypatch, capsys):
    _monkeypatch_broken_keyring(monkeypatch)

    keyring.unset("abc", "FOO")

    (out, err) = capsys.readouterr()
    assert '' == out
    assert (expected_broken_message % "deleting") == err

    keyring.reset_keyring_module()
