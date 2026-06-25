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


# --- Item 4: assemble v6 doc + atomic write + pixi --locked acceptance -------

def test_build_pixi_lock_v6_structure_and_noarch_dedup():
    # tzdata is noarch -> shared across both subdirs; it must appear ONCE in
    # the top-level packages list but be referenced from each subdir.
    tz = {"name": "tzdata", "version": "2024a", "build": "h0c530f3_0",
          "url": "https://m/noarch/tzdata-2024a-h0c530f3_0.conda",
          "sha256": "tzsha", "md5": "tzmd5", "depends": []}
    py64 = {"name": "python", "version": "3.12.2", "build": "x64",
            "url": "https://m/linux-64/python-3.12.2-x64.conda",
            "sha256": "p64", "md5": "m64", "depends": ["tzdata"]}
    pyarm = {"name": "python", "version": "3.12.2", "build": "arm",
             "url": "https://m/linux-aarch64/python-3.12.2-arm.conda",
             "sha256": "parm", "md5": "marm", "depends": ["tzdata"]}
    doc = pixi_lock.build_pixi_lock(
        {"linux-64": [tz, py64], "linux-aarch64": [tz, pyarm]},
        channels=["https://m"], env_name="default")

    assert doc["version"] == 6
    env = doc["environments"]["default"]
    assert env["channels"] == [{"url": "https://m"}]
    # each subdir references its own packages by url
    assert {"conda": tz["url"]} in env["packages"]["linux-64"]
    assert {"conda": py64["url"]} in env["packages"]["linux-64"]
    assert {"conda": pyarm["url"]} in env["packages"]["linux-aarch64"]
    # top-level packages: tzdata once (deduped), both pythons present = 3 total
    urls = [p["conda"] for p in doc["packages"]]
    assert urls.count(tz["url"]) == 1
    assert len(doc["packages"]) == 3
    # minimal 4-field schema only (no license/size/timestamp)
    rec = next(p for p in doc["packages"] if p["conda"] == py64["url"])
    assert set(rec.keys()) <= {"conda", "sha256", "md5", "depends"}
    assert rec["sha256"] == "p64" and rec["depends"] == ["tzdata"]


def test_write_pixi_lock_is_atomic_and_roundtrips(tmpdir):
    import os
    from ruamel.yaml import YAML
    doc = {"version": 6, "environments": {}, "packages": []}
    target = str(tmpdir.join("pixi.lock"))
    pixi_lock.write_pixi_lock(doc, target)
    assert os.path.exists(target)
    # no leftover temp files in the dir
    leftovers = [f for f in os.listdir(str(tmpdir)) if f.startswith(".pixi.lock.")]
    assert leftovers == []
    # reads back as the same document
    with open(target) as f:
        loaded = YAML().load(f)
    assert loaded["version"] == 6


def test_write_pixi_lock_failure_leaves_no_partial_file(tmpdir, monkeypatch):
    import os
    target = str(tmpdir.join("pixi.lock"))
    # Force the serialize step to blow up AFTER the temp file is opened.
    import anaconda_project.internal.pixi_lock as plmod

    class _BoomYAML(object):
        def dump(self, *a, **k):
            raise RuntimeError("disk full mid-dump")
    # monkeypatch the YAML class used inside write_pixi_lock
    monkeypatch.setattr("ruamel.yaml.YAML", lambda *a, **k: _BoomYAML())
    with pytest.raises(RuntimeError):
        plmod.write_pixi_lock({"version": 6}, target)
    assert not os.path.exists(target)                       # no partial target
    assert [f for f in os.listdir(str(tmpdir)) if f.startswith(".pixi.lock.")] == []  # temp cleaned


def test_translate_lock_set_end_to_end_with_injected_query(tmpdir):
    import os
    lock_set = CondaLockSet(
        {"all": ["tzdata=2024a=h0c530f3_0"], "linux-64": ["python=3.12.2=x64"]},
        platforms=["linux-64"])
    recs = {
        "tzdata": [_FakeRecord("tzdata", "2024a", "h0c530f3_0", "linux-64",
                               "https://m/noarch/tzdata-2024a-h0c530f3_0.conda", "s", "m", [])],
        "python": [_FakeRecord("python", "3.12.2", "x64", "linux-64",
                               "https://m/linux-64/python-3.12.2-x64.conda", "s2", "m2", ["tzdata"])],
    }
    target = str(tmpdir.join("pixi.lock"))
    doc = pixi_lock.translate_lock_set(lock_set, channels=["https://m"], path=target,
                                       query=_fake_query_factory(recs))
    assert os.path.exists(target)
    assert len(doc["packages"]) == 2
    assert "linux-64" in doc["environments"]["default"]["packages"]


def test_write_pixi_lock_does_not_wrap_long_urls(tmpdir):
    # Long package URLs must stay on one line (ruamel's default 80-col wrap
    # folds "conda:" onto a continuation line, which is fragile for diffs and
    # other readers). Regression for the canary finding.
    long_url = ("https://repo.anaconda.com/pkgs/main/noarch/"
                "some-rather-long-package-name-1.2.3-py312habcdef0_0.conda")
    pkg = {"name": "x", "version": "1.2.3", "build": "py312habcdef0_0",
           "url": long_url, "sha256": "s", "md5": "m", "depends": []}
    doc = pixi_lock.build_pixi_lock({"linux-64": [pkg]}, channels=["https://repo.anaconda.com/pkgs/main"])
    target = str(tmpdir.join("pixi.lock"))
    pixi_lock.write_pixi_lock(doc, target)
    with open(target) as f:
        text = f.read()
    # the full url appears on a single physical line (no fold)
    assert any(long_url in line for line in text.splitlines()), \
        "long url was wrapped onto a continuation line"


# --- Item 5: SubdirData private-API guards ----------------------------------

# conda-the-LIBRARY is not a dependency of anaconda-project (it shells out to a
# conda BINARY), so the import may be absent in this test env. pixi_lock's
# enrichment requires conda importable in-process (true in the editor image);
# tests that need the real conda module skip cleanly where it isn't present.
try:
    import conda.core.subdir_data as _conda_subdir_data  # noqa: F401
    _HAS_CONDA = True
except Exception:  # noqa: BLE001
    _HAS_CONDA = False


def test_resolve_subdir_data_raises_typed_error_when_api_missing(monkeypatch):
    # Simulate a conda where the import path moved: _resolve_subdir_data must
    # raise our typed CondaIndexAPIError (with version context), not an opaque
    # ImportError, so convert-time failure is diagnosable.
    import builtins
    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "conda.core.subdir_data":
            raise ImportError("No module named 'conda.core.subdir_data'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    with pytest.raises(pixi_lock.CondaIndexAPIError) as exc:
        pixi_lock._resolve_subdir_data()
    assert "subdir_data" in str(exc.value).lower()


@pytest.mark.skipif(not _HAS_CONDA, reason="conda library not importable in this env")
def test_resolve_subdir_data_raises_when_query_all_removed(monkeypatch):
    # conda imports fine, but query_all is gone (API renamed) -> typed error.
    class _NoQueryAll(object):
        pass
    import conda.core.subdir_data as sd
    monkeypatch.setattr(sd, "SubdirData", _NoQueryAll, raising=True)
    with pytest.raises(pixi_lock.CondaIndexAPIError) as exc:
        pixi_lock._resolve_subdir_data()
    assert "query_all" in str(exc.value)


@pytest.mark.skipif(not _HAS_CONDA or "CI_OFFLINE" in __import__("os").environ,
                    reason="repodata canary needs conda + network/mirror; skipped without them")
def test_default_query_backend_shape_against_real_conda():
    # CI CANARY (gated on editor-image build): against the installed/pinned
    # conda, SubdirData.query_all must import AND return records exposing the
    # 4 fields we read (url/sha256/md5/depends). Catches a conda bump that
    # silently breaks enrichment. Uses a tiny, stable noarch pkg on pkgs/main.
    SubdirData = pixi_lock._resolve_subdir_data()        # import must work
    assert hasattr(SubdirData, "query_all")
    try:
        recs = pixi_lock._default_query("tzdata", ["https://repo.anaconda.com/pkgs/main"], "noarch")
    except pixi_lock.CondaIndexAPIError:
        raise
    except Exception:
        pytest.skip("no network/mirror for repodata canary")
    if not recs:
        pytest.skip("tzdata not found on pkgs/main/noarch (channel/network)")
    r = recs[0]
    for field in ("url", "sha256", "md5", "depends"):
        assert hasattr(r, field), "PackageRecord missing %r (conda API changed)" % field


def test_enrich_finds_noarch_package_when_platform_subdir_empty():
    # A platform closure includes noarch packages (tzdata, pip, pure-python
    # deps). Enrichment must search noarch in addition to the platform subdir,
    # and record the package's ACTUAL subdir (noarch), not the platform.
    def _query(name, channels, subdir):
        if name == "tzdata" and subdir == "noarch":
            return (_FakeRecord("tzdata", "2024a", "h0", "noarch",
                                "https://m/noarch/tzdata-2024a-h0.conda", "s", "m", []),)
        return ()   # nothing under the platform subdir
    enriched = pixi_lock.enrich_locked_packages(
        [("tzdata", "2024a", "h0")], channels=["pkgs/main"], subdir="osx-arm64", query=_query)
    assert enriched[0]["subdir"] == "noarch"
    assert "/noarch/" in enriched[0]["url"]


def test_enrich_noarch_target_does_not_double_search():
    # When the target IS noarch, don't search noarch twice; a miss is a miss.
    def _query(name, channels, subdir):
        assert subdir == "noarch"   # only ever queried for noarch
        return ()
    with pytest.raises(pixi_lock.BuildNotFoundError):
        pixi_lock.enrich_locked_packages(
            [("x", "1", "b")], channels=["pkgs/main"], subdir="noarch", query=_query)
