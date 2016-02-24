"""OS keychain/keyring abstraction."""
from __future__ import absolute_import, print_function

# future: get a little fancier than this :-)
_fake_in_memory_keyring = dict()


def get(name):
    return _fake_in_memory_keyring.get(name, None)


def set(name, value):
    _fake_in_memory_keyring[name] = value
