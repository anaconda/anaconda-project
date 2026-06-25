# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Offline tests for anaconda_project.internal.pixi_lock (AENT-8881).

These are fully offline (no network, no solver, no conda index): they cover
the lock-set -> exact-package-closure reader and the fail-fast guards. The
SubdirData enrichment + pixi-install --locked acceptance are exercised
separately (Items 2/4) since those need repodata fixtures / a real pixi.
"""
from __future__ import absolute_import

import pytest

from anaconda_project.conda_manager import CondaLockSet
from anaconda_project.internal import pixi_lock


def test_parse_locked_specs_merges_buckets_incl_noarch():
    # "all" carries the cross-platform (noarch) closure; package_specs_for_platform
    # must merge it into the per-platform list, and we must preserve all of it
    # (closure completeness is the pixi --locked acceptance gate).
    lock_set = CondaLockSet(
        {
            "all": ["tzdata=2024a=h0c530f3_0"],            # noarch, shared
            "linux-64": ["python=3.12.2=hab00c5b_0", "numpy=1.26.4=py312heda63a1_0"],
        },
        platforms=["linux-64"])
    locked = pixi_lock.parse_locked_specs(lock_set, "linux-64")
    names = sorted(n for (n, _v, _b) in locked)
    assert names == ["numpy", "python", "tzdata"]            # noarch NOT dropped
    assert ("python", "3.12.2", "hab00c5b_0") in locked
    assert ("tzdata", "2024a", "h0c530f3_0") in locked


def test_parse_locked_specs_unknown_platform_fails_loud():
    lock_set = CondaLockSet({"linux-64": ["python=3.12.2=hab00c5b_0"]}, platforms=["linux-64"])
    with pytest.raises(pixi_lock.LockTranslationError) as exc:
        pixi_lock.parse_locked_specs(lock_set, "osx-arm64")
    assert "no entry for platform" in str(exc.value)


def test_parse_locked_specs_rejects_unpinned_spec():
    # A spec without an exact version=build means this platform isn't actually
    # locked; strict mode must refuse it rather than imply a re-solve.
    lock_set = CondaLockSet({"linux-64": ["python=3.12.2=hab00c5b_0", "requests"]}, platforms=["linux-64"])
    with pytest.raises(pixi_lock.LockTranslationError) as exc:
        pixi_lock.parse_locked_specs(lock_set, "linux-64")
    assert "not pinned to an exact version=build" in str(exc.value)


def test_parse_locked_specs_rejects_version_without_build():
    lock_set = CondaLockSet({"linux-64": ["python=3.12.2"]}, platforms=["linux-64"])
    with pytest.raises(pixi_lock.LockTranslationError):
        pixi_lock.parse_locked_specs(lock_set, "linux-64")


def test_assert_no_pip_packages_passes_when_conda_only():
    lock_set = CondaLockSet({"linux-64": ["python=3.12.2=hab00c5b_0"]}, platforms=["linux-64"])
    # Should not raise.
    pixi_lock.assert_no_pip_packages(lock_set)


def test_assert_no_pip_packages_fails_fast_on_pip_bucket():
    lock_set = CondaLockSet(
        {
            "linux-64": ["python=3.12.2=hab00c5b_0"],
            "pip": ["some-pypi-only-pkg==1.2.3"],
        },
        platforms=["linux-64"])
    with pytest.raises(pixi_lock.UnsupportedLockContentError) as exc:
        pixi_lock.assert_no_pip_packages(lock_set)
    assert "pip package" in str(exc.value)
    assert "phase 2" in str(exc.value)
