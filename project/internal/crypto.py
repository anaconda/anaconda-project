from __future__ import absolute_import, print_function

import base64
import hashlib
import json

from Crypto.Cipher import AES
from Crypto import Random

import bcrypt

# bcrypt module doesn't use bytes after the first 72
_BCRYPT_SIGNIFICANT_BYTES = 72

# SHA256 generates a hash of this many bytes
_SHA256_HASH_LENGTH = 32

# AES-256 needs a key this long
_AES256_KEY_LENGTH = 32

assert _AES256_KEY_LENGTH in AES.key_size


class CryptoError(Exception):
    pass


class CryptoKeyError(CryptoError):
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


# note that this is a hash and not a MAC.
# http://doctrina.org/Cryptographic-Hash-Vs-MAC:What-You-Need-To-Know.html
# This is believed to be OK in our two uses because if an attacker
# finds two messages that have the same hash, it doesn't matter as
# far as we know.
#  - we use it to compress the output of bcrypt
#  - the ciphertext includes a checksum of the plaintext. Since the hash
#    is encrypted with the secret key, it's effectively from a trusted source.
#    And we are only using it to say "password incorrect" or "password correct"
#    anyhow.
def _sha256(message):
    m = hashlib.sha256()
    m.update(message)
    hash = m.digest()
    return hash


def _key_from_secret(secret, salt):
    # we bcrypt to make it hard to brute-force-attack. We have to bcrypt
    # every 72 bytes because it ignores bytes after the first 72.
    encoded_secret = secret.encode('utf-8')
    bcrypted = "".encode("utf-8")
    while len(encoded_secret) > 0:
        (head, tail) = (encoded_secret[:_BCRYPT_SIGNIFICANT_BYTES], encoded_secret[_BCRYPT_SIGNIFICANT_BYTES:])
        encoded_secret = tail
        bcrypted = bcrypted + bcrypt.hashpw(head, salt)

    # then we sha256 to force the length to _AES_KEY_LENGTH bytes.
    # of course someone trying to decrypt could guess these keys
    # directly bypassing the bcrypt, but since they are 32 bytes
    # long it shouldn't be easy.
    key = _sha256(bcrypted)
    assert len(key) == _AES256_KEY_LENGTH
    assert len(key) == _SHA256_HASH_LENGTH
    return key


def encrypt_bytes(message, secret):
    salt = bcrypt.gensalt()
    key = _key_from_secret(secret, salt)
    iv = Random.new().read(AES.block_size)
    cipher = AES.new(key, AES.MODE_CFB, iv)
    encrypted = cipher.encrypt(_sha256(message) + message)
    dumped = json.dumps(dict(iv=_b64encode(iv),
                             cipher='AES-256-CFB',
                             salt=_b64encode(salt),
                             message=_b64encode(encrypted)))
    single_string = _b64encode(dumped.encode('utf-8'))
    return single_string


def decrypt_bytes(package, secret):
    json_string = _b64decode(package).decode('utf-8')
    try:
        loaded = json.loads(json_string)
    except ValueError as e:
        raise CryptoError("encrypted package had bad json: " + str(e))

    if 'cipher' not in loaded or loaded['cipher'] != 'AES-256-CFB':
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

    # In the right situation, we can reveal information by
    # integrity-checking (via cryptographic hash or Unicode
    # validation or other means) the encrypted message. An example
    # cited by
    # http://www.thoughtcrime.org/blog/the-cryptographic-doom-principle/
    # is the "Vaudenay attack" which depends on the attacker being
    # able to tell whether we failed in cipher.decrypt() above due
    # to bad padding, or below when integrity-checking.
    #
    # But even if we didn't have a checksum, we would probably get
    # invalid UTF-8 most of the time on a bad message, which (I
    # think...)  reveals the same information.
    #
    # We are hoping that doesn't matter in this case because our
    # attacker would have the full ciphertext (bits on disk) but
    # would not be talking to a computer program that has the
    # secret key, instead they would be brute-forcing the
    # key. They can make their own version of this code that does
    # whatever they want it to. So it isn't an issue for this code
    # to reveal information ... this code only has the secret when
    # a user has just typed it in.

    if len(decrypted) < _SHA256_HASH_LENGTH:
        raise CryptoError("encrypted data was corrupted")

    checksum = decrypted[:_SHA256_HASH_LENGTH]
    decrypted = decrypted[_SHA256_HASH_LENGTH:]

    if checksum != _sha256(decrypted):
        raise CryptoKeyError("incorrect pass phrase")

    return decrypted


def encrypt_string(message, secret):
    return encrypt_bytes(message.encode('utf-8'), secret)


def decrypt_string(package, secret):
    decrypted = decrypt_bytes(package, secret)
    try:
        return decrypted.decode('utf-8')
    except UnicodeDecodeError:
        raise CryptoError("invalid Unicode string in encrypted data")
