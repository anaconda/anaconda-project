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
