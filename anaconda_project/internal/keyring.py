# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""OS keychain/keyring abstraction."""
from __future__ import absolute_import, print_function

import sys

try:
    from urllib.parse import quote_plus
except ImportError:  # pragma: no cover (py2 only)
    from urllib import quote_plus  # pragma: no cover (py2 only)

_fallback_keyring = 0
_fake_in_memory_keyring = dict()


def enable_fallback_keyring():
    global _fallback_keyring
    _fallback_keyring = _fallback_keyring + 1


def disable_fallback_keyring():
    global _fallback_keyring
    global _fake_in_memory_keyring
    assert _fallback_keyring > 0
    _fallback_keyring = _fallback_keyring - 1
    if _fallback_keyring == 0:
        # forget everything whenever the fallback gets disabled
        _fake_in_memory_keyring = dict()


def _use_fallback_keyring():
    global _fallback_keyring
    return _fallback_keyring > 0


def _onetime_keyring_complain_and_disable(complaint):
    if not _use_fallback_keyring():
        # Printing to console here is a hack; we may be running in a
        # GUI.  But let's live with it for now until we see how often
        # this happens.
        print("Unable to use system keyring to store passwords.", file=sys.stderr)
        print("  (%s)" % complaint, file=sys.stderr)
        enable_fallback_keyring()


def reset_keyring_module():
    global _fake_in_memory_keyring
    global _fallback_keyring
    _fake_in_memory_keyring = dict()
    _fallback_keyring = 0


def fallback_data():
    return _fake_in_memory_keyring


try:
    import keyring
except ImportError:  # pragma: no cover
    keyring = None  # pragma: no cover
    _onetime_keyring_complain_and_disable("Module 'keyring' not available, try installing the 'keyring' package.")


def _make_username(env_prefix, variable):
    assert env_prefix is not None
    assert variable is not None

    return "%s/%s" % (quote_plus(env_prefix), quote_plus(variable))


def get(env_prefix, variable):
    name = _make_username(env_prefix, variable)
    if not _use_fallback_keyring():
        try:
            got = keyring.get_password("anaconda", name)
            return got
        except Exception as e:
            # keyring throws a bare "RuntimeError" if it has no working backend;
            # not sure what else it can throw.
            _onetime_keyring_complain_and_disable("Exception getting a password: " + str(e))

    # on either exception, or disabled
    return _fake_in_memory_keyring.get(name, None)


def set(env_prefix, variable, value):
    assert value is not None

    name = _make_username(env_prefix, variable)
    if not _use_fallback_keyring():
        try:
            keyring.set_password("anaconda", name, value)
            return
        except Exception as e:
            # keyring throws a bare "RuntimeError" if it has no working backend;
            # not sure what else it can throw.
            _onetime_keyring_complain_and_disable("Exception setting a password: " + str(e))

    # on either exception, or disabled
    _fake_in_memory_keyring[name] = value


def unset(env_prefix, variable):
    name = _make_username(env_prefix, variable)
    if not _use_fallback_keyring():
        try:
            keyring.delete_password("anaconda", name)
            return
        except Exception as e:
            # keyring throws a bare "RuntimeError" if it has no working backend;
            # not sure what else it can throw.
            _onetime_keyring_complain_and_disable("Exception deleting a password: " + str(e))

    # on either exception, or disabled
    if name in _fake_in_memory_keyring:
        del _fake_in_memory_keyring[name]
