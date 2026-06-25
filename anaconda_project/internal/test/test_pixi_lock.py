# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Offline tests for anaconda_project.internal.pixi_lock (AENT-8881).

These are fully offline (no network, no solver, no conda index): enrichment
is exercised through an injected fake query callable, so no repodata is
fetched. The pixi-install --locked acceptance (Item 4) and the live census
E2E (July) are separate.
"""
from __future__ import absolute_import

import pytest

from anaconda_project.conda_manager import CondaLockSet
from anaconda_project.internal import pixi_lock


class _FakeRecord(object):
    """Stand-in for a conda PackageRecord (only the fields we read)."""
    def __init__(self, name, version, build, subdir, url, sha256, md5, depends):
        self.name = name
        self.version = version
        self.build = build
        self.subdir = subdir
        self.url = url
        self.sha256 = sha256
        self.md5 = md5
        self.depends = depends


def _fake_query_factory(records_by_name):
    """Build an injectable query(name, channels, subdir) -> records."""
    def _query(name, channels, subdir):
        return tuple(records_by_name.get(name, ()))
    return _query


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


# --- Item 2: enrichment (offline, injected query) ---------------------------

def test_enrich_exact_match_returns_four_fields():
    recs = {
        "python": [_FakeRecord("python", "3.12.2", "hab00c5b_0", "linux-64",
                               "https://mirror/linux-64/python-3.12.2-hab00c5b_0.conda",
                               "abc123", "def456", ["libffi", "openssl"])],
    }
    enriched = pixi_lock.enrich_locked_packages(
        [("python", "3.12.2", "hab00c5b_0")],
        channels=["pkgs/main"], subdir="linux-64",
        query=_fake_query_factory(recs))
    assert len(enriched) == 1
    e = enriched[0]
    assert e["url"].endswith("python-3.12.2-hab00c5b_0.conda")
    assert e["sha256"] == "abc123"
    assert e["md5"] == "def456"
    assert e["depends"] == ["libffi", "openssl"]


def test_enrich_build_not_found_fails_loud_no_substitution():
    # Channel answers, but only a DIFFERENT build of the same name exists.
    recs = {
        "numpy": [_FakeRecord("numpy", "1.26.4", "py311_OTHER", "linux-64",
                              "u", "s", "m", [])],
    }
    with pytest.raises(pixi_lock.BuildNotFoundError) as exc:
        pixi_lock.enrich_locked_packages(
            [("numpy", "1.26.4", "py312heda63a1_0")],
            channels=["pkgs/main"], subdir="linux-64",
            query=_fake_query_factory(recs))
    assert "exact build not found" in str(exc.value)
    assert "does not substitute" in str(exc.value)


def test_enrich_transport_error_is_mirror_unavailable_not_build_gone():
    # A transient failure to READ the index must NOT look like "build gone".
    def _boom(name, channels, subdir):
        raise OSError("connection reset / HTTP 429")
    with pytest.raises(pixi_lock.MirrorUnavailableError) as exc:
        pixi_lock.enrich_locked_packages(
            [("python", "3.12.2", "hab00c5b_0")],
            channels=["pkgs/main"], subdir="linux-64", query=_boom)
    assert "could not reach" in str(exc.value)
    # And crucially NOT a BuildNotFoundError (no substitution path).
    assert not isinstance(exc.value, pixi_lock.BuildNotFoundError)


def test_enrich_foreign_subdir_matches_only_target_subdir():
    # query_all can return records for multiple subdirs; we must pick the one
    # for the TARGET subdir (aarch64 record while running on a linux-64 host),
    # not whatever happens to be first.
    recs = {
        "numpy": [
            _FakeRecord("numpy", "1.26.4", "b0", "linux-64", "u-x64", "s-x64", "m-x64", []),
            _FakeRecord("numpy", "1.26.4", "b0", "linux-aarch64", "u-arm", "s-arm", "m-arm", []),
        ],
    }
    enriched = pixi_lock.enrich_locked_packages(
        [("numpy", "1.26.4", "b0")],
        channels=["pkgs/main"], subdir="linux-aarch64",
        query=_fake_query_factory(recs))
    assert enriched[0]["url"] == "u-arm"
    assert enriched[0]["sha256"] == "s-arm"


def test_enrich_empty_channels_is_programmer_error():
    with pytest.raises(pixi_lock.LockTranslationError) as exc:
        pixi_lock.enrich_locked_packages(
            [("python", "3.12.2", "hab00c5b_0")],
            channels=[], subdir="linux-64", query=lambda *a: ())
    assert "non-empty channels" in str(exc.value)


def test_module_import_graph_never_imports_conda_solver():
    # The whole premise is NO SOLVER. Importing pixi_lock must not drag in
    # conda's solver. (Belt + suspenders to the runtime tripwire: a future
    # refactor that imports conda.core.solve at module scope fails here.)
    import sys
    import importlib

    # Drop any already-imported solver + our module so the check is real.
    for mod in list(sys.modules):
        if mod == "conda.core.solve" or mod.startswith("conda.core.solve."):
            del sys.modules[mod]
    sys.modules.pop("anaconda_project.internal.pixi_lock", None)

    importlib.import_module("anaconda_project.internal.pixi_lock")
    assert "conda.core.solve" not in sys.modules, \
        "pixi_lock must not import conda's solver at import time"
