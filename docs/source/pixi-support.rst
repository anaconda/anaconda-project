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
