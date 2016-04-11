# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
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
    with pytest.raises(crypto.CryptoKeyError) as excinfo:
        crypto.decrypt_string(encrypted, "foo")
    assert 'incorrect pass phrase' in repr(excinfo.value)


def test_bad_unicode():
    message = "Hello World"
    encrypted = crypto.encrypt_bytes(message.encode("utf-16"), "bar")
    with pytest.raises(crypto.CryptoError) as excinfo:
        crypto.decrypt_string(encrypted, "bar")
    assert 'invalid Unicode' in repr(excinfo.value)


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


def test_nonsense_salt():
    _check_package_mangled_field('salt', 'NOPE1', 'bcrypt error')


def test_wrong_bcrypt_algorithm_in_salt():
    _check_package_mangled_field('salt', '$2c$12$Ksvojv.81hG0Hs9.4WUglu', 'bcrypt error')


def test_wrong_bcrypt_rounds_in_salt():
    _check_package_mangled_field('salt', '$2b$14$Ksvojv.81hG0Hs9.4WUglu', 'incorrect pass phrase')


def test_wrong_random_data_in_salt():
    _check_package_mangled_field('salt', '$2b$12$Ksvojv.81hG0Hs9.4WUglu', 'incorrect pass phrase')


def test_salt_not_valid_ascii():
    _check_package_mangled_field('salt', '☠', 'salt in json not valid ascii')


def test_bad_iv_base64():
    _check_package_mangled_field('iv', 'NOPE1', 'base64 decoding error')


def test_missing_message():
    _check_package_missing_field('message', 'no message in json')


def test_short_message():
    _check_package_mangled_field('message', '', 'encrypted data was corrupted')


def test_changing_one_byte_in_message():
    def check_change_one_byte_by(n):
        def change_one_byte(json):
            message = bytearray(crypto._b64decode(json['message']))
            changed = message[3] + n
            if changed > 255:
                changed = changed - 256
            message[3] = changed
            json['message'] = crypto._b64encode(message)

        _check_modified_package(lambda p: _modified_package(p, change_one_byte), 'incorrect pass phrase')

    check_change_one_byte_by(1)
    check_change_one_byte_by(2)
    check_change_one_byte_by(3)
    check_change_one_byte_by(4)
    check_change_one_byte_by(5)
    check_change_one_byte_by(6)
    check_change_one_byte_by(7)


def test_deleting_bytes_from_message():
    def check_delete_bytes(n):
        def delete_bytes(json):
            message = crypto._b64decode(json['message'])[:-n]
            json['message'] = crypto._b64encode(message)

        _check_modified_package(lambda p: _modified_package(p, delete_bytes), 'incorrect pass phrase')

    check_delete_bytes(1)
    check_delete_bytes(2)
    check_delete_bytes(3)


def test_long_secret_matters():
    message = "Hello World"

    def check_secret_length(count):
        secret = "a" * count
        assert len(secret) == count
        encrypted = crypto.encrypt_string(message, secret)
        decrypted_ok = crypto.decrypt_string(encrypted, secret)
        assert message == decrypted_ok
        with pytest.raises(crypto.CryptoKeyError) as excinfo:
            crypto.decrypt_string(encrypted, secret + "a")
        assert 'incorrect pass phrase' in repr(excinfo.value)

    # some bcrypt implementations including the one we are using ignore after byte 72.
    # our code has to work around this.
    check_secret_length(72)
    check_secret_length(256)
