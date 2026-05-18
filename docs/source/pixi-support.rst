============
Pixi support
============

Anaconda Project ships two pieces of tooling aimed at converting
existing ``anaconda-project.yml`` projects into a form that can be
managed by `pixi <https://pixi.sh/>`_ (and, by extension,
`conda-workspaces <https://github.com/conda-incubator/conda-workspaces>`_,
which consumes the same ``pixi.toml`` format).

These are the focus of recent maintenance on this repository:

* The ``anaconda-project export-pixi`` command, which writes a
  ``pixi.toml`` (and a sibling ``ap_download.py`` helper when needed)
  alongside an existing ``anaconda-project.yml``.
* A ``publication_info`` function in
  ``anaconda_project.project_info`` that can read either
  ``anaconda-project.yml`` or ``pixi.toml`` and return a uniform
  dictionary describing the project's commands, environments, and
  variables. Downstream deployment tooling that ingests both formats
  uses this as its single integration point.
* The ``anaconda-project info`` command, a human-readable view of the
  same data — modeled on ``pixi info`` — that works on either
  manifest format.

The rest of this page documents the conventions the conversion uses
to preserve as much of the original project's behavior as possible.

Export goals
============

The conversion is best-effort but tries to satisfy three contracts:

* The resulting ``pixi.toml`` should be installable and runnable
  without further manual editing for the common project shapes
  (``unix:`` commands, ``notebook:``, ``bokeh_app:``, ``downloads:``,
  ``variables:``, single or multi-environment).
* Tasks invoked under pixi should mirror the runtime behavior of
  ``anaconda-project run`` as closely as the underlying tools allow,
  including HTTP options, environment selection, and download fetching.
* The converted manifest should be readable for a maintainer who
  inspects it later — comments mark anything that couldn't be
  translated faithfully, and warnings appear at the top of the file
  when a downstream consumer needs to act.

Environment layout
==================

* When the source yml has a single ``env_specs:`` entry with a
  non-default name (for example ``sampleproj:``), packages live in
  the top-level ``[dependencies]`` table (pixi's default feature) and
  the named env inherits via ``features = ["sampleproj"]``. Pixi's
  mandatory implicit ``default`` env carries the same packages, so
  ``pixi install`` (without ``-e``) still does something useful.
* Multi-environment projects emit each ``env_specs:`` entry under
  ``[environments]`` in source order. The first uncommented entry is
  the project's intended default; downstream tools can extract it with
  one line of ``awk``.
* If one of multiple env_specs is literally named ``default``, its
  ``[environments]`` slot is rendered as a comment
  (``# default  (pixi creates this implicitly...)``) and its packages
  are folded into top-level ``[dependencies]``. Pixi auto-creates
  ``default`` from the default feature, so redeclaring it would be
  redundant.
* ``solve-group`` is intentionally not emitted. Anaconda Project does
  not assume environments solve together, and pixi shouldn't be told
  otherwise on import.

The ``--use-default`` flag
--------------------------

Projects that have no env_spec literally named ``default`` route every
dependency, task, and prepare body through ``[feature.{name}.*]``
indirection — clean for projects that need explicit fan-out, but verbose
for the common case of a single env (or a default command bound to one
specific env in a multi-env project). Passing ``--use-default`` to
``export-pixi`` collapses that:

* The exporter picks one env_spec to promote to ``default``: the env_spec
  attached to the project's default command (the one a bare
  ``anaconda-project run`` would invoke), or — if there are no commands —
  the first ``env_specs:`` entry declared.
* That env_spec's packages, tasks, and prepare body land in top-level
  ``[dependencies]`` / ``[tasks.X]`` / ``[tasks.prepare]`` instead of
  inside ``[feature.{name}.*]`` blocks. Other env_specs (in a multi-env
  project) keep their ``[feature.{name}.*]`` scoping unchanged.
* The flag is a no-op when an env_spec literally named ``default``
  already exists — there's nothing to rename.
* Under ``--use-default`` the no-op ``prepare`` task is dropped. When
  there are no ``downloads:`` to fetch, the unflagged export emits an
  ``echo`` placeholder in ``[feature.{name}.tasks.prepare]`` so
  ``pixi run prepare`` resolves to the project's intended env even
  when that env's name isn't ``default``. Under ``--use-default`` the
  promoted env *is* the implicit default, so the placeholder loses
  its purpose; ``prepare`` is only emitted when there's real work to
  do.

When the user runs ``export-pixi`` without the flag and the project would
benefit, the CLI prints a recommendation naming the env that would be
promoted. With the flag on, the CLI confirms which env was renamed.
The renaming applies only to the exported ``pixi.toml``; the source
``anaconda-project.yml`` is not modified.

The ``--add-current-platform`` flag
-----------------------------------

Pixi rejects an env that doesn't list the host platform; anaconda-project
is more forgiving, so it's common to find a ported project with a
``platforms:`` list that worked under conda but breaks at pixi install
time on the developer's machine. Passing ``--add-current-platform`` to
``export-pixi`` widens the converted manifest's ``platforms`` list to
include the host's conda subdir (e.g. ``osx-arm64``) when it isn't
already declared.

Behavior mirrors ``--use-default``:

* Off by default. The exporter does not silently mutate the user's
  platforms list — the user explicitly chose what to support.
* When omitted, the CLI prints a recommendation if the host platform
  is missing.
* When passed, the CLI prints a confirmation listing the platform
  that was added — or stays quiet when the platform was already
  present.

The change applies only to the exported ``pixi.toml``; the source
``anaconda-project.yml`` is not modified.

Channel handling
================

Pixi has no ``defaults`` meta-channel and no equivalent of conda's
``default_channels`` configuration. Two cases are handled explicitly:

* If the source yml lists no channels at all, the converted manifest
  is populated from ``conda config --show default_channels`` rather
  than a hard-coded ``conda-forge`` fallback. This preserves
  enterprise users' ``.condarc``-configured mirrors.
* If the source yml includes ``defaults`` alongside other channels,
  only the ``defaults`` entry is expanded; the rest are preserved in
  source order with duplicate URLs removed.

If ``conda`` is not on PATH (or fails to invoke) and ``defaults``
expansion is required, the conversion fails fast — no partial output
is written.

Tasks and command translation
=============================

* ``unix:`` command lines are translated to a form compatible with
  pixi's ``deno_task_shell`` task runner. ``${VAR}`` and ``%VAR%``
  references are normalized to ``$VAR``; ``${PROJECT_DIR}`` becomes
  ``$PIXI_PROJECT_ROOT``.
* When both ``unix:`` and ``windows:`` command lines are present, the
  converter normalizes the windows form (path separators, env vars)
  and compares to the unix form. Matching forms collapse to a single
  task; divergent forms emit the unix variant plus a comment noting
  what the windows form would have rendered.
* ``${CONDA_PREFIX}/bin/<name>``, ``${CONDA_PREFIX}/Scripts/<name>``,
  and similar prefix-rooted paths are stripped to the bare command
  name. Pixi's task activation already prepends the env's executable
  directories to ``PATH``, so explicit prefix paths are redundant and
  hurt cross-platform portability.

The ``prepare`` task
====================

Every converted project gets a ``prepare`` task. It does double duty:

* When the source yml declared ``downloads:``, ``prepare`` runs a
  helper script (``ap_download.py``, written next to ``pixi.toml``)
  once per download. The helper is pure stdlib and uses ``python3``,
  so it works whether or not the env declares its own python.
* Even when there are no downloads, ``prepare`` is emitted as a no-op
  ``echo``. Its presence serves two purposes:

  - Acts as a marker that downstream deployment tooling can use to
    detect that this ``pixi.toml`` was converted from
    ``anaconda-project.yml``.
  - When scoped to a non-default env's feature (e.g.
    ``[feature.sampleproj.tasks.prepare]``), forces
    ``pixi run prepare`` to resolve to that env automatically — useful
    when the project's default env_spec is named something other than
    ``default``.

If a download-needing env doesn't declare ``python``, the converted
``pixi.toml`` carries a ``# WARNING:`` comment block at the top
listing the affected envs, and the same warning is printed to stderr
at conversion time. The conversion does not silently mutate the
user's package list.

HTTP options
============

Anaconda Project's ``supports_http_options: true`` (implicit on
``notebook:`` and ``bokeh_app:`` commands) tells the underlying tool
to expect ``--anaconda-project-X`` flags for host, port, address,
url-prefix, iframe-hosts, no-browser, and use-xheaders. The exporter
translates this contract into pixi ``args`` and templated ``cmd``
strings, dispatching by command type:

* ``notebook:`` commands become ``jupyter notebook <file>`` plus
  Jupyter-native flags (``--port``, ``--ip``,
  ``--NotebookApp.base_url=...``,
  ``--NotebookApp.tornado_settings={...}`` for iframe hosts,
  ``--no-browser``, ``--NotebookApp.trust_xheaders=True``). ``host``
  is dropped because Jupyter has no host-restrict equivalent.
* ``bokeh_app:`` commands become ``bokeh serve <app>`` plus bokeh's
  bare flags (``--host``, ``--port``, ``--address``, ``--prefix``,
  ``--use-xheaders``). ``--show`` is rendered as the *inverse* of
  ``--no-browser``. ``iframe_hosts`` is dropped because bokeh has no
  Content-Security-Policy equivalent.
* Plain ``unix:`` commands with ``supports_http_options: true`` keep
  their ``--anaconda-project-X`` flags verbatim. Generic tools that
  opt in are expected to recognize the canonical names themselves
  (``panel serve`` does).
* ``unix:`` commands with ``supports_http_options: false`` are
  scanned for HTTP Jinja vars (``{{ port }}``, ``{{ host }}``, etc.)
  in their templates; pixi ``args`` are declared only for the vars
  the cmd actually references.

Each flag is wrapped in a Jinja conditional, so a blank pixi arg
omits the flag entirely (rather than passing an empty value the
underlying tool might reject).

The ``{% if var %}...{% endif %}`` and ``{{ var }}`` template syntax
inside task ``cmd`` strings is intentional, not accidental — pixi
renders task commands through MiniJinja against the positional values
passed to ``pixi run <task> <values...>`` (with ``args`` defaults
filling in the rest), and only then hands the rendered command to
``deno_task_shell`` for execution. The syntax is supported but not
prominently documented in pixi's own docs; the converted ``pixi.toml``
is exercising a real pixi feature, and editing the gates by hand is
fine.

The ``info`` command
====================

``anaconda-project info`` prints a human-readable summary of the
project, modeled on ``pixi info``::

    $ anaconda-project info --directory .
    Project
    ------------
                  Type: pixi
                  Name: Attractors
           Description: A panel dashboard using datashader ...
             Directory: /path/to/project

    Commands
    ------------
               Command: dashboard  [default, http]
                      : env_spec: sampleproj
                      : cmd: panel serve attractors.ipynb {% if host %}...
                      : args: host, port, address, url_prefix, ...

    Environments
    ------------
           Environment: default
              Channels: https://repo.anaconda.com/pkgs/main, ...
      Dependency count: 12
          Dependencies: colorcet, datashader, fiona, geoviews, ...
                Locked: yes

The command works on either manifest format — ``pixi.toml`` is
preferred when both are present.

Flags:

* ``--json`` emits the underlying ``publication_info`` dict as
  indented JSON, mirroring ``pixi info --json``.
* ``--env-paths`` includes the on-disk prefix path for each
  environment. For pixi projects this shells out to
  ``pixi info --json``; the full pixi payload is also stashed
  under an ``_pixi`` key in ``--json`` mode so callers don't have
  to repeat the subprocess.
* ``--project-type {pixi,anaconda-project}`` forces a manifest
  format when both are present in the directory (e.g. mid-conversion).

publication_info
================

``anaconda_project.project_info.publication_info(project_dir)``
returns a uniform dictionary regardless of whether the project is
managed by ``anaconda-project.yml`` or by a converted
``pixi.toml``. The shape mirrors ``Project.publication_info()`` from
the anaconda-project side; relevant additions for the pixi side:

* ``commands[name]['args']`` — ordered list of pixi arg names
  declared for the task. Empty for tasks without args. Lets
  downstream tooling drive ``pixi run <task> *args`` to supply
  positional values.
* ``commands[name]['env_spec']`` — resolves to the name of an env
  that supports the task. Top-level tasks resolve to the project's
  default env (literal ``default`` if declared, otherwise the first
  declared env). Feature-scoped tasks resolve to whichever env
  actually includes the feature.
* ``env_specs[name]['locked']`` — ``True`` when ``pixi.lock`` has an
  ``environments[<name>]`` entry. Best-effort: any read or parse
  failure silently falls back to ``False``.

Optional arguments:

* ``project_type='pixi' | 'anaconda-project'`` forces a specific
  manifest format. Default behavior is auto-detect, with ``pixi.toml``
  winning when both are present. It is an error to ask for a format
  whose manifest is not in the directory.
* ``env_paths=True`` populates ``env_specs[name]['path']`` with the
  on-disk prefix for each declared environment. For anaconda-project
  this is derived from each ``EnvSpec``; for pixi it requires a
  ``pixi info --json`` subprocess (so it is opt-in). Failure to
  invoke pixi or parse its output raises ``RuntimeError``. When the
  source is pixi, the full ``pixi info --json`` payload is also
  stored under the top-level ``_pixi`` key so callers that want
  richer pixi-specific data don't pay for a second subprocess.

Programmatic export API
=======================

For tools that wrap the conversion (launchers, IDE plugins, custom CLIs),
the export pipeline is exposed so downstream code never has to scrape
generated TOML or re-implement the conversion rules.

* ``project_ops.export_pixi(project, filename, use_default=False,
  add_current_platform=False)`` writes ``pixi.toml`` to disk and returns
  a ``PixiExportStatus``. On success the status carries:

  - ``default_rename_from`` — the env_spec promoted to ``default`` by
    ``use_default``, or ``None`` when the flag was off, no-op'd
    (because ``default`` already existed), or the export failed.
  - ``current_platform_added`` — the platform string added to the
    ``platforms`` list by ``add_current_platform``, or ``None`` when
    the flag was off, no-op'd (the platform was already declared), or
    the export failed.

  Callers use these to surface "Renamed env X → default" or "Added
  platform Y" in their success notification without re-querying the
  project.
* ``project_ops.preview_pixi_export(project, use_default=False,
  add_current_platform=False)`` runs the conversion in memory and
  returns a dict
  ``{pixi_toml, default_rename_from, current_platform_addition_target,
  warnings}``. The ``pixi_toml`` entry is the would-be file content;
  the rename / platform-addition fields report the *candidates*
  (whether or not their flag was passed), so a confirmation dialog
  can offer "re-render with --use-default" or "re-render with
  --add-current-platform" as actions; ``warnings`` is the leading
  ``# WARNING:`` block already extracted from the rendered TOML, so
  callers don't have to grep for it themselves. Raises
  ``CondaNotAvailableError`` if the conversion needs ``conda config
  --show default_channels`` and conda isn't reachable.
* ``anaconda_project.internal.pixi_export.default_rename_target(project)``
  returns the env_spec name that ``--use-default`` would promote, or
  ``None`` when promotion is a no-op (project already has a
  ``default`` env_spec, or has no env_specs at all). Stable contract;
  the underlying selection rule (default-command's env, else first
  declared env_spec) lives in this one function.
* ``anaconda_project.internal.pixi_export.current_platform_addition_target(project)``
  returns the host's conda subdir if it would be added by
  ``--add-current-platform``, or ``None`` when it's already in the
  union of declared platforms. Same shape as
  ``default_rename_target`` so callers can decide both flags
  symmetrically.

Limitations
===========

A few aspects of ``anaconda-project.yml`` cannot be translated
faithfully. The exporter surfaces them as comments rather than
silently dropping them:

* ``services:`` (e.g. Redis) — pixi has no equivalent service-launch
  primitive. The converted manifest carries a comment listing the
  required services so a maintainer can wire them up out of band.
* Variables without defaults — anaconda-project would prompt; pixi
  cannot. The converted manifest emits a comment listing variables
  that must be set in the environment before running.
