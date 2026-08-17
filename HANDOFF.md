# Handoff: download counts for main-x packages — feedback for the anaconda.org team

**Prepared 17 Aug 2026 for Lilly Winfree (anaconda.org data/UX) — cc Jose Mesa (packaging-data sources).**
Framing per Lilly's #packaging guidance (17 Aug): anaconda.org is the public source of truth for downloads. Nothing below proposes a competing source — the internal notebook/xlsx snapshot stays private and defers to .org via per-figure source+date stamps. This is a what-doesn't-work-on-.org report, which Lilly asked for.

## The underlying need (Ville Tuulos, #packaging, 12 Aug)

Finding a conda package without knowing its name. anaconda.org search currently surfaces the right package without ranking it by usage — Ville's `q=snowflake` search buried `snowflake-connector-python` under packages with far lower download counts. Our private snapshot proved the data answers it: once sorted by .org's own `ndownloads`, the heavyweights (python/pip/openssl-class) land on top and the snowflake family separates cleanly from the noise. Ville confirmed the right package became the first hit.

Concrete numbers (17 Aug .org data): snowflake-snowpark-python 36,845 > snowflake-connector-python 31,111 > snowflake-ml-python 29,956 > snowflake.core 4,418. Note for the thread: by pure download count snowpark edges out the connector — Ville's "first hit" was driven by textual match, not by count. If .org search gets download-aware ranking, this ordering difference is worth knowing before anyone quotes it.

## What doesn't work on .org today (all probed live, 17 Aug)

| Surface | Result |
|---|---|
| `api.anaconda.org/package/{owner}/{name}` | Works for **main** (owner `anaconda`; top-level `ndownloads` = server-side aggregate across all files/versions/platforms). Coverage 5,388/5,463 packages (98.6%); 75 main packages have no .org entry (404) — e.g. internal repacks. Queryable per-package only; bulk search/exports don't expose counts. |
| main packages **not on .org** (75) | e.g. `__anaconda_core_depends` — fine for internal repacks, but worth a label policy. Also 32 packages lack summaries in `channeldata.json` upstream. |
| `api.anaconda.org/package/...` for **main-x** | **HTTP 404 under every namespace tried** (`main-x`, `anaconda`, `main_x`). main-x is invisible to the package API. |
| `api.anaconda.org/channels/main-x[/packages]` | **HTTP 401** even with a valid org repo token (Bearer or token auth) — endpoint exists, our tokens don't unlock it. Entitlement? Different token type (e.g. the anaconda-auth unified repo API key, `ANACONDA_AUTH_API_KEY`)? |
| `anaconda.org/channels/main-x` | 200 HTML — main-x is a first-class channel concept on the site, and yet has no data presence in the API. |
| `repo.anaconda.cloud/repo/main-x/` (with valid org token) | `channeldata.json` is a deliberate stub (`packages: {}`, `subdirs: ["noarch"]`); real data only in `noarch/repodata.json` (19,646 records → 14,234 unique names). Repodata records carry no summary and no download fields. |
| main-x summaries | Also absent everywhere on Anaconda surfaces — we backfilled from PyPI (14,047/14,234, 98.7%) because every main-x build is a `pypi_*` noarch repack. If .org wants main-x to be a real citizen, summaries and downloads are the two missing halves. |

## The ask, in .org terms

1. **Decide whether main-x deserves .org package presence** (summaries + downloads), same as main. If yes, one ingestion covers both halves above.
2. **Unlock or document the channel API** for org tokens — today an org-authenticated user still gets 401 on `/channels/main-x/packages`.
3. **Search ranking by download/relevance** — the memo's original complaint; Albert Defusco's hybrid-search work and Alaap Murali's MCP semantic-search work are already in this lane; the snapshot defers to them.
4. Community signal on exactly this: Ville (thread), us (catalog), and "hundreds of pages on anaconda.com/app" pain in the same thread.

## Why nothing was published against .org

Per the no-proxy rule ("a wrong download count published into a sales conversation is worse than a blank column"), we did **not** fake main-x downloads from PyPI stats (pepy/pypistats measure upstream popularity, not channel downloads). The main-x sheet says "not available" in words, per sheet, with the probe trail above. Repo is private; a live hosted version was floated and is off the table per Lilly.
