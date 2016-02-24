from __future__ import absolute_import, print_function

from project.internal import keyring


def test_get_set():
    keyring.set("FOO", "bar")
    assert "bar" == keyring.get("FOO")
