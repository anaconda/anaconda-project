from __future__ import absolute_import, print_function

import base64
import hashlib
import json

from Crypto.Cipher import AES
from Crypto import Random

import bcrypt


class CryptoError(Exception):
    pass


def _b64decode(s):
    try:
        return base64.b64decode(s)
    except Exception as e:
        # very unclear what all b64decode can throw, but one thing is
        # binascii.Error("incorrect padding")
        raise CryptoError("base64 decoding error: " + str(e))


def _b64encode(s):
    return base64.b64encode(s).decode('ascii')


def _key_from_secret(secret, salt):
    # we bcrypt to make it hard to brute-force-attack. We have to bcrypt
    # every 72 bytes because it ignores bytes after the first 72.
    encoded_secret = secret.encode('utf-8')
    bcrypted = "".encode("utf-8")
    while len(encoded_secret) > 0:
        (head, tail) = (encoded_secret[:72], encoded_secret[72:])
        encoded_secret = tail
        bcrypted = bcrypted + bcrypt.hashpw(head, salt)

    # then we sha256 to force the length to 32 bytes
    m = hashlib.sha256()
    m.update(bcrypted)
    key = m.digest()
    assert len(key) == 32
    return key


def encrypt_bytes(message, secret):
    salt = bcrypt.gensalt()
    key = _key_from_secret(secret, salt)
    iv = Random.new().read(AES.block_size)
    cipher = AES.new(key, AES.MODE_CFB, iv)
    encrypted = cipher.encrypt(message)
    dumped = json.dumps(dict(iv=_b64encode(iv), cipher='AES-CFB', salt=_b64encode(salt), message=_b64encode(encrypted)))
    single_string = _b64encode(dumped.encode('utf-8'))
    return single_string


def decrypt_bytes(package, secret):
    json_string = _b64decode(package).decode('utf-8')
    try:
        loaded = json.loads(json_string)
    except ValueError as e:
        raise CryptoError("encrypted package had bad json: " + str(e))

    if 'cipher' not in loaded or loaded['cipher'] != 'AES-CFB':
        raise CryptoError("bad cipher in json")

    if 'iv' not in loaded:
        raise CryptoError("bad iv in json")

    iv = _b64decode(loaded['iv'])

    if len(iv) != AES.block_size:
        raise CryptoError("bad iv length in json")

    if 'salt' not in loaded:
        raise CryptoError("bad salt in json")

    salt = _b64decode(loaded['salt'])

    if 'message' not in loaded:
        raise CryptoError("no message in json")

    message = _b64decode(loaded['message'])

    key = _key_from_secret(secret, salt)
    cipher = AES.new(key, AES.MODE_CFB, iv)
    decrypted = cipher.decrypt(message)
    return decrypted


def encrypt_string(message, secret):
    return encrypt_bytes(message.encode('utf-8'), secret)


def decrypt_string(package, secret):
    decrypted = decrypt_bytes(package, secret)
    try:
        return decrypted.decode('utf-8')
    except UnicodeDecodeError:
        # bad UTF-8 in encrypted message, probably means wrong
        # secret...  return an empty string for this rather than
        # raising, since we can't consistently raise when the
        # secret is wrong (sometimes we might happen to get valid
        # utf-8)
        return ""
