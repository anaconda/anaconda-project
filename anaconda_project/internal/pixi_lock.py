# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Translate an anaconda-project lock set into a pixi.lock by DIRECT
translation (no solver).

Why this exists (AENT-8881): ``export_pixi`` emits ``pixi.toml`` only; the
lock is otherwise (re)created later by ``pixi install`` *re-solving*. A
re-solve — even when every package is pinned to an exact version — does NOT
reproduce a complex environment: it re-evaluates transitive constraints
against *today's* repodata under strict channel priority, and package
metadata / channel availability drift after the lock was made, so the solver
rejects a combination that demonstrably worked at lock time (proven live on
the holoviz ``census`` project: 251 pkgs, both loose and fully-pinned
re-solve fail). Writing ``pixi.lock`` directly from the recorded packages and
``pixi install --locked`` (never invoking the solver) is the only path that
reproduces such environments.

Scope of this module (v1):

* ``strict`` mode only — every recorded build is reproduced exactly, or the
  translation fails loud. (A ``best-effort`` nearest-build substitution mode
  was deliberately deferred: doing it correctly requires re-deriving
  cross-package constraints, which is a solver by another name.)
* conda packages only. The anaconda-project lock does not carry pip packages
  in a form we can faithfully lock, and ``pixi.lock`` pip entries need PyPI
  enrichment; a ``pip:`` bucket therefore fails fast rather than being
  silently dropped.
* Provenance is trust-on-first-use against the configured channels/mirror:
  the anaconda-project lock format records only ``name=version=build`` (see
  ``conda_api.ParsedSpec`` — there is no per-package hash), so there is no
  lock-time hash to validate the enriched ``sha256`` against. Integrity rests
  on the channels being trusted/pinned (in AE5: the airgap mirror).

This module is intentionally host-agnostic — it lives in anaconda-project and
shells out to nothing AE5-specific, so any consumer of anaconda-project (the
launcher in any JupyterLab host, CI, the CLI) gets it.
"""
from __future__ import absolute_import

from anaconda_project.internal import conda_api


# anaconda-project lock files group package specs into "buckets" keyed by
# platform OR by a cross-platform selector ("all", "unix", "linux", "osx",
# "win"). CondaLockSet.package_specs_for_platform() already merges the right
# buckets for a concrete platform (all -> unix -> <platform_name> ->
# <platform>); we lean on it rather than re-implementing bucket precedence
# (anaconda-project owns that logic; re-forking it is exactly the mistake
# AENT-8833 / standalone_export taught us to avoid).


class LockTranslationError(Exception):
    """A lock set could not be faithfully translated to a pixi.lock.

    Always raised loud and never swallowed: a half-translated or
    silently-degraded lock defeats the entire reproducibility purpose.
    """


class UnsupportedLockContentError(LockTranslationError):
    """The lock set contains content this translator cannot faithfully
    reproduce in v1 (e.g. pip packages)."""


class BuildNotFoundError(LockTranslationError):
    """A locked build is authoritatively absent from the channel's repodata.

    This is the AUTHORITATIVE "the exact build is gone" case (the channel
    answered, and the build is not in it) — distinct from a transport
    failure. In strict mode this is fatal: we will not substitute.
    """


class MirrorUnavailableError(LockTranslationError):
    """Enrichment could not reach the channel/mirror (transport error,
    429, timeout, connection reset).

    CRITICAL: this is NOT "the build is gone." A transient mirror failure
    must never be mistaken for an absent build and must never trigger
    substitution. Surfaced loud with the cause so an operator can retry,
    rather than silently producing a wrong or partial lock.
    """


def parse_locked_specs(lock_set, platform):
    """Return the exact locked conda packages for ``platform`` as a list of
    ``(name, version, build)`` tuples.

    ``lock_set`` is an ``anaconda_project.conda_manager.CondaLockSet``.
    ``package_specs_for_platform`` yields the merged, bucket-expanded
    ``name=version=build`` strings (the full closure for that platform,
    including the cross-platform ``all``/``unix`` buckets, which carry
    noarch packages — completeness of that closure is what ``pixi install
    --locked`` verifies, so we must not drop any of it).

    Raises ``LockTranslationError`` if any spec is not pinned to an exact
    version AND build (strict mode requires a fully-resolved lock; a loose
    spec means the lock was never actually locked for this platform).
    """
    if platform not in lock_set.platforms:
        raise LockTranslationError("lock set has no entry for platform %r (has %r)" %
                                   (platform, list(lock_set.platforms)))

    locked = []
    for spec in lock_set.package_specs_for_platform(platform):
        parsed = conda_api.parse_spec(spec)
        if parsed is None:
            raise LockTranslationError("could not parse locked spec %r for platform %r" % (spec, platform))
        if parsed.exact_version is None or parsed.exact_build_string is None:
            # A real lock pins name=version=build. A spec missing the version
            # or build means this platform isn't actually locked -> a re-solve
            # would be required, which is precisely what we refuse to do.
            raise LockTranslationError(
                "locked spec %r for platform %r is not pinned to an exact version=build; "
                "the lock set is not fully resolved for this platform" % (spec, platform))
        locked.append((parsed.name, parsed.exact_version, parsed.exact_build_string))
    return locked


def assert_no_pip_packages(lock_set):
    """Fail fast if the lock set carries pip packages.

    v1 is conda-only. Pip entries in a pixi.lock need PyPI enrichment (a
    separate, phase-2 concern). Silently dropping them would yield a lock
    that installs but is missing packages -> a delayed runtime ImportError,
    the exact silent-degradation we refuse. So we surface it as an explicit,
    actionable error instead.
    """
    # CondaLockSet stores the pip bucket under the "pip" platform key.
    pip_specs = lock_set._package_specs_by_platform.get('pip', [])
    if pip_specs:
        raise UnsupportedLockContentError(
            "lock set contains %d pip package(s) (%s%s); pip enrichment is not supported in v1 "
            "(AENT-8881 phase 2). Translating without them would silently drop packages." %
            (len(pip_specs), ", ".join(pip_specs[:3]), " ..." if len(pip_specs) > 3 else ""))


class CondaIndexAPIError(LockTranslationError):
    """conda's in-process index API (SubdirData.query_all) is not importable
    or not callable in the way this module needs.

    SubdirData.query_all is a conda INTERNAL/private API; this module is the
    only place anaconda-project imports conda as a library rather than
    shelling out to it. A conda upgrade could move/rename/resignature it. We
    surface that loud and diagnosably (with the installed conda version)
    rather than letting an opaque ImportError/AttributeError leak, and a CI
    canary (test_default_query_backend_shape) exercises the import+shape
    against the pinned conda so a breaking bump is caught in CI, not at a
    user's convert-time.
    """


def _resolve_subdir_data():
    """Return conda's SubdirData class, or raise CondaIndexAPIError with the
    conda version if the private import path moved.

    Imported locally (never at module import) so importing pixi_lock never
    imports conda's solver — see test_module_import_graph_never_imports_conda_solver.
    """
    try:
        from conda.core.subdir_data import SubdirData
    except Exception as e:  # noqa: BLE001
        try:
            import conda
            ver = getattr(conda, "__version__", "unknown")
        except Exception:  # noqa: BLE001
            ver = "unknown"
        raise CondaIndexAPIError(
            "could not import conda.core.subdir_data.SubdirData (conda %s); the conda index "
            "API this module relies on may have moved. %s" % (ver, e))
    if not hasattr(SubdirData, "query_all"):
        import conda
        raise CondaIndexAPIError(
            "conda.core.subdir_data.SubdirData has no query_all (conda %s); the conda index "
            "API this module relies on changed." % getattr(conda, "__version__", "unknown"))
    return SubdirData


def _default_query(name, channels, subdir):
    """Real enrichment backend: conda's repodata index reader.

    Returns a tuple of PackageRecord-like objects for ``name`` on the given
    channels+subdir, reading repodata with ZERO solver invocation
    (SubdirData.query_all does an index lookup, not a solve). Imported
    locally so importing this module never imports conda's solver, and a conda
    that moved/renamed the API surfaces as a typed CondaIndexAPIError (with the
    version) at call time, not an opaque error.
    """
    subdir_data = _resolve_subdir_data()
    return subdir_data.query_all(name, channels=list(channels), subdirs=[subdir])


def enrich_locked_packages(locked, channels, subdir, query=None):
    """Enrich each ``(name, version, build)`` with its exact url/sha256/md5/
    depends from repodata, by EXACT match. No solver, no substitution.

    Parameters
    ----------
    locked : list of (name, version, build) tuples (from parse_locked_specs)
    channels : iterable of channel names/URLs (pass the project's configured
        channels with `defaults` already expanded to the mirror via the
        AENT-8838 default_channels= seam — never None; query_all silently
        falls back to context.channels when channels is empty, which would
        read the wrong source).
    subdir : the conda subdir these records target (e.g. "linux-64",
        "noarch"). Passed EXPLICITLY so a lock targeting a foreign subdir
        (aarch64 records translated on a linux-64 host) queries the right
        repodata rather than the host's.
    query : injectable callable(name, channels, subdir) -> records, for
        offline testing. Defaults to the real conda index reader.

    Returns a list of dicts: {name, version, build, url, sha256, md5, depends}.

    Raises
    ------
    MirrorUnavailableError : the channel/mirror could not be reached
        (transport error). NEVER treated as "build gone" — no substitution.
    BuildNotFoundError : the channel answered but the exact build is absent
        (strict mode: fatal, we do not substitute).
    LockTranslationError : programmer error (empty channels).
    """
    if not channels:
        raise LockTranslationError("enrich_locked_packages requires explicit non-empty channels "
                                   "(passing none lets conda fall back to the wrong source)")
    if query is None:
        query = _default_query

    enriched = []
    for (name, version, build) in locked:
        try:
            records = query(name, channels, subdir)
        except Exception as e:  # noqa: BLE001 - we re-raise as a typed transport error
            # Any failure to READ the index is a transport/mirror problem, not
            # evidence the build is gone. Distinguish it loud; never fall
            # through to substitution or to a BuildNotFound.
            raise MirrorUnavailableError(
                "could not reach channel(s) %r for %s=%s=%s on subdir %r: %s" %
                (list(channels), name, version, build, subdir, e))

        match = None
        for rec in records or ():
            # Exact identity: name+version+build, and the record must be for
            # the requested subdir (query_all can return multiple subdirs).
            if (rec.name == name and rec.version == version and rec.build == build
                    and getattr(rec, "subdir", subdir) == subdir):
                match = rec
                break

        if match is None:
            raise BuildNotFoundError(
                "exact build not found in channel(s) %r: %s=%s=%s on subdir %r "
                "(strict mode does not substitute)" % (list(channels), name, version, build, subdir))

        enriched.append({
            "name": name,
            "version": version,
            "build": build,
            # Trust-on-first-use: the lock carries no hash, so we record the
            # channel's CURRENT sha256/md5. Integrity rests on a trusted/pinned
            # channel (the airgap mirror in AE5).
            "url": match.url,
            "sha256": getattr(match, "sha256", None),
            "md5": getattr(match, "md5", None),
            "depends": list(getattr(match, "depends", ()) or ()),
        })
    return enriched


def build_pixi_lock(enriched_by_subdir, channels, env_name="default"):
    """Assemble a pixi.lock (schema version 6) dict from enriched packages.

    Parameters
    ----------
    enriched_by_subdir : {subdir: [enriched-pkg-dict, ...]} where each dict is
        the output of enrich_locked_packages (name/version/build/url/sha256/
        md5/depends). Every subdir's full closure must be present (pixi
        rejects an incomplete closure with "lock-file not up-to-date").
    channels : ordered channel URLs for the environment.
    env_name : the pixi environment name (default "default").

    Returns a plain dict matching pixi.lock v6:
      version: 6
      environments: {<env>: {channels: [{url}], packages: {<subdir>: [{conda: url}]}}}
      packages: [{conda: url, sha256, md5, depends}]   # deduped, by url

    The per-environment `packages.<subdir>` entries REFERENCE packages by url;
    the top-level `packages` list holds each unique record once. We emit only
    the minimal 4 fields (conda/sha256/md5/depends) which pixi accepts for
    `pixi install --locked` (verified: pixi's own lock stripped to these still
    installs). license/size/timestamp are intentionally omitted — not needed
    for a faithful locked install, and we don't have authoritative values.
    """
    # Per-subdir reference lists for the environment.
    env_packages = {}
    # Top-level package records, deduped by url (a noarch package shared across
    # subdirs appears once in `packages` but is referenced from each subdir).
    records_by_url = {}
    for subdir in sorted(enriched_by_subdir):
        refs = []
        for pkg in enriched_by_subdir[subdir]:
            url = pkg["url"]
            refs.append({"conda": url})
            if url not in records_by_url:
                rec = {"conda": url}
                if pkg.get("sha256") is not None:
                    rec["sha256"] = pkg["sha256"]
                if pkg.get("md5") is not None:
                    rec["md5"] = pkg["md5"]
                if pkg.get("depends"):
                    rec["depends"] = list(pkg["depends"])
                records_by_url[url] = rec
        env_packages[subdir] = refs

    document = {
        "version": 6,
        "environments": {
            env_name: {
                "channels": [{"url": c} for c in channels],
                "packages": env_packages,
            }
        },
        # Stable order: sort the top-level package list by url for a
        # deterministic lock (pixi doesn't require a particular order, but a
        # stable emit makes diffs/tests reproducible).
        "packages": [records_by_url[u] for u in sorted(records_by_url)],
    }
    return document


def write_pixi_lock(document, path):
    """Write the pixi.lock dict to ``path`` ATOMICALLY.

    Full closure is already assembled in memory by build_pixi_lock; we
    serialize to a temp file in the same directory and os.replace() it into
    place, so a crash/interruption mid-write can never leave a half-written
    (incomplete-closure) pixi.lock that pixi would reject with a confusing
    "lock-file not up-to-date" error. Either the complete lock appears, or the
    previous file is untouched.
    """
    import os
    import tempfile
    from ruamel.yaml import YAML

    directory = os.path.dirname(os.path.abspath(path))
    yaml = YAML()
    # Package URLs are long; ruamel's default 80-col wrap folds them onto a
    # continuation line ("conda:\n    https://...") which, while pixi tolerates
    # it, is fragile for diffs/other readers and looks broken. Disable wrapping
    # so each url stays on one line (matches how pixi writes its own lock).
    yaml.width = 4096
    fd, tmp_path = tempfile.mkstemp(prefix=".pixi.lock.", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.dump(document, f)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def translate_lock_set(lock_set, channels, path, env_name="default", query=None):
    """End-to-end: anaconda-project CondaLockSet -> faithful pixi.lock on disk.

    Ties Items 1+2+4 together: fail-fast on pip, parse the exact closure for
    every platform, enrich each via repodata (no solver), assemble the v6
    document, and write it atomically. Strict mode throughout — any missing
    build (BuildNotFoundError) or unreachable mirror (MirrorUnavailableError)
    aborts BEFORE any file is written.
    """
    assert_no_pip_packages(lock_set)
    enriched_by_subdir = {}
    for platform in lock_set.platforms:
        locked = parse_locked_specs(lock_set, platform)
        enriched_by_subdir[platform] = enrich_locked_packages(locked, channels, platform, query=query)
    document = build_pixi_lock(enriched_by_subdir, channels, env_name=env_name)
    write_pixi_lock(document, path)
    return document
