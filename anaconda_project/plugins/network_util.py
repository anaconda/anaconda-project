# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Network utilities for use by plugins."""
import socket


def _get_urlparse():
    try:
        # py3
        import urllib.parse
        return urllib.parse  # pragma: no cover
    except ImportError:  # pragma: no cover
        # py2
        import urlparse
        return urlparse


urlparse = _get_urlparse()


def can_connect_to_socket(host, port, timeout_seconds=0.5):
    """Check whether we can connect to a server at host:port.

    Args:
        host (str): the host
        port (int): the port
        timeout_seconds (float): how long to wait for failure
    Returns:
        True if we could connect
    """
    try:
        s = socket.create_connection(address=(host, port), timeout=timeout_seconds)
        s.close()
        return True
    except IOError:
        return False
