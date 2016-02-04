from __future__ import absolute_import, print_function

import json
import pytest

import project.internal.crypto as crypto


def test_round_trip():
    message = "Hello World"
    encrypted = crypto.encrypt_string(message, "bar")
    decrypted = crypto.decrypt_string(encrypted, "bar")
    assert message == decrypted


def test_wrong_secret_fails():
    message = "Hello World"
    encrypted = crypto.encrypt_string(message, "bar")
    decrypted = crypto.decrypt_string(encrypted, "foo")
    assert message != decrypted


def _modified_package(original, json_modifier):
    json_string = crypto._b64decode(original).decode('utf-8')
    loaded = json.loads(json_string)
    json_modifier(loaded)
    return crypto._b64encode(json.dumps(loaded).encode('utf-8'))


def _mangled_package(original, **kwargs):
    def json_modifier(loaded):
        for key in kwargs:
            loaded[key] = kwargs[key]

    return _modified_package(original, json_modifier)


def _incomplete_package(original, remove_field):
    def json_modifier(loaded):
        del loaded[remove_field]

    return _modified_package(original, json_modifier)


def test_invalid_json():
    with pytest.raises(crypto.CryptoError) as excinfo:
        crypto.decrypt_string(crypto._b64encode("}".encode('utf-8')), "foo")
    assert 'bad json' in repr(excinfo.value)


def _check_modified_package(modifier, expected_in_exception):
    encrypted = crypto.encrypt_string("foo", "bar")
    with pytest.raises(crypto.CryptoError) as excinfo:
        crypto.decrypt_string(modifier(encrypted), "bar")
    assert expected_in_exception in repr(excinfo.value)


def _check_package_missing_field(remove_field, expected_in_exception):
    def modifier(encrypted):
        return _incomplete_package(encrypted, remove_field)

    _check_modified_package(modifier, expected_in_exception)


def _check_package_mangled_field(mangled_field, mangled_value, expected_in_exception):
    def modifier(encrypted):
        kwargs = {mangled_field: mangled_value}
        return _mangled_package(encrypted, **kwargs)

    _check_modified_package(modifier, expected_in_exception)


def test_missing_cipher():
    _check_package_missing_field('cipher', 'bad cipher in json')


def test_bad_cipher():
    _check_package_mangled_field('cipher', 'NOPE', 'bad cipher in json')


def test_missing_iv():
    _check_package_missing_field('iv', 'bad iv in json')


def test_bad_iv():
    _check_package_mangled_field('iv', 'NOPE', 'bad iv length in json')


def test_missing_salt():
    _check_package_missing_field('salt', 'bad salt in json')


def test_bad_salt():
    _check_package_mangled_field('salt', 'NOPE1', 'base64 decoding error')


def test_bad_iv_base64():
    _check_package_mangled_field('iv', 'NOPE1', 'base64 decoding error')


def test_missing_message():
    _check_package_missing_field('message', 'no message in json')
