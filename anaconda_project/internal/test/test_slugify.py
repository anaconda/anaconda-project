# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function, unicode_literals

from anaconda_project.internal.slugify import slugify


def test_should_be_unchanged():
    s = "abcdefgxyz_ABCDEFGXYZ-0123456789"
    assert s == slugify(s)


def test_replace_spaces():
    assert "a-b" == slugify("a b")


def test_replace_unicode():
    assert "-" == slugify(u"🌟")


def test_replace_specials():
    assert "-----------------" == slugify("!@#$%^&*()<>\"':/\\")


def test_replace_bytes():
    assert "-" == slugify(u"🌟".encode('utf-8'))
