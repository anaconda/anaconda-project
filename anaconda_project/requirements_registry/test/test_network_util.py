# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
import anaconda_project.requirements_registry.network_util as network_util

import socket


def test_can_connect_to_socket():
    # create a listening socket just to get a port number
    # that (probably) won't be in use after we close it
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    port = s.getsockname()[1]

    try:
        assert network_util.can_connect_to_socket("127.0.0.1", port)
    finally:
        s.close()


def test_cannot_connect_to_socket():
    # create a listening socket just to get a port number
    # that (probably) won't be in use after we close it
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()

    assert not network_util.can_connect_to_socket("127.0.0.1", port)
