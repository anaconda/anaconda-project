# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function, unicode_literals

from conda_kapsel.internal.slugify import slugify


def test_should_be_unchanged():
    s = "abcdefgxyz_ABCDEFGXYZ-0123456789"
    assert s == slugify(s)


def test_replace_spaces():
    assert "a-b" == slugify("a b")


def test_replace_unicode():
    assert "-" == slugify("🌟")


def test_replace_specials():
    assert "-----------------" == slugify("!@#$%^&*()<>\"':/\\")
