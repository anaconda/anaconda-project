# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Convert an anaconda-project Project to pixi.toml format."""
from __future__ import absolute_import, print_function

import os
import re
import shutil
import subprocess

from anaconda_project.requirements_registry.requirement import EnvVarRequirement
from anaconda_project.requirements_registry.requirements.conda_env import CondaEnvRequirement
from anaconda_project.requirements_registry.requirements.download import DownloadRequirement
from anaconda_project.requirements_registry.requirements.service import ServiceRequirement


class CondaNotAvailableError(Exception):
    """Raised when the exporter needs `conda` for channel resolution but
    can't find or invoke it. Wraps the underlying reason so the CLI can
    surface a useful failure status."""


def _resolve_default_channels():
    """Return the list of URLs that `defaults` expands to, taken from the
    user's local ``conda config --show default_channels``.

    Pixi has no notion of a `defaults` meta-channel, so we have to rewrite
    every occurrence to the URLs it would resolve to under conda. We avoid
    `--json` because conda renders URL fields as nested urlparse dicts in
    that mode; the plain YAML-ish output is easier to parse and is what
    `conda config --show` emits by default.
    """
    if not shutil.which('conda'):
        raise CondaNotAvailableError(
            "`conda` not found on PATH; required to expand the `defaults` "
            "channel into concrete URLs.")
    try:
        proc = subprocess.run(
            ['conda', 'config', '--show', 'default_channels'],
            check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as e:
        raise CondaNotAvailableError(
            "Failed to invoke `conda config --show default_channels`: {}".format(e))

    urls = []
    in_block = False
    for line in proc.stdout.splitlines():
        if line.startswith('default_channels:'):
            in_block = True
            continue
        if in_block:
            stripped = line.strip()
            if stripped.startswith('- '):
                urls.append(stripped[2:].strip())
            elif stripped == '':
                continue
            else:
                # A non-list, non-blank line means we've fallen out of
                # the default_channels block (a sibling key, etc.).
                break
    if not urls:
        raise CondaNotAvailableError(
            "`conda config --show default_channels` returned no entries.")
    return urls


def _expand_defaults_in_channels(channels, default_channels):
    """Replace every `defaults` entry in ``channels`` with ``default_channels``.

    Order is preserved; duplicates are removed (first wins).
    """
    out = []
    seen = set()
    for ch in channels:
        if ch == 'defaults':
            for d in default_channels:
                if d not in seen:
                    seen.add(d)
                    out.append(d)
        elif ch not in seen:
            seen.add(ch)
            out.append(ch)
    return out


def _sanitize_env_name(name):
    """Pixi environment/feature names allow only lowercase letters, numbers, and dashes."""
    return re.sub(r'[^a-z0-9-]', '-', name.lower())


def _toml_string(value):
    escaped = value.replace('\\', '\\\\').replace('"', '\\"')
    escaped = escaped.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    return '"{}"'.format(escaped)


def _toml_multiline_string(value):
    """Format a multi-line shell command as a TOML triple-quoted string.

    The leading newline after ``\"\"\"`` is stripped by TOML, so we add one
    so the body starts on its own line for readability. Triple-quoted
    strings still process backslash escapes; we only need to escape any
    literal triple-quote sequence in the body.
    """
    escaped = value.replace('\\', '\\\\').replace('"""', '\\"\\"\\"')
    return '"""\n{}\n"""'.format(escaped)


def _toml_wrapped_string(parts, separator=' '):
    """Format a long single-line string as a TOML triple-quoted block where
    every line is joined with ``separator`` at parse time.

    Uses TOML's ``\\`` line-continuation: a backslash at the end of a line
    inside a multi-line basic string strips the line terminator and any
    leading whitespace on the next line. We separate the chunks with
    ``\\<newline><spaces><continuation>`` so a TOML parser reconstructs
    the original ``separator``-joined string while a human sees one chunk
    per line in the source.
    """
    if not parts:
        return _toml_string('')
    # Each chunk is escaped just like _toml_string would, but we keep
    # newlines intact (they're explicit \\<newline>s in our output, not
    # data). Triple-quoted strings interpret backslash escapes the same
    # way basic strings do.
    escaped_parts = [
        p.replace('\\', '\\\\').replace('"""', '\\"\\"\\"')
        for p in parts
    ]
    body = '{sep}\\\n'.format(sep=separator).join(escaped_parts)
    return '"""\\\n{body}\\\n"""'.format(body=body)


def _toml_inline_array(items):
    return '[{}]'.format(', '.join(_toml_string(i) for i in items))


def _conda_spec_to_pixi(spec):
    """Convert a conda package spec string to (name, version_constraint).

    Examples:
        'numpy' -> ('numpy', '*')
        'numpy>=1.20' -> ('numpy', '>=1.20')
        'numpy=1.20' -> ('numpy', '1.20.*')
        'numpy==1.20' -> ('numpy', '==1.20')
        'numpy=1.20.3=py39_0' -> ('numpy', '==1.20.3')
        'conda-forge::numpy' -> ('numpy', '*')
        'conda-forge::numpy>=1.0' -> ('numpy', '>=1.0')
    """
    # Strip channel prefix (e.g. conda-forge::numpy)
    if '::' in spec:
        spec = spec.split('::', 1)[1]

    # Match name and optional version constraint
    m = re.match(r'^([a-zA-Z0-9_][a-zA-Z0-9_.\-]*)(.*)$', spec)
    if not m:
        return spec, '*'

    name = m.group(1)
    version_part = m.group(2).strip()

    if not version_part:
        return name, '*'

    # Exact pin with build string: numpy=1.20.3=py39_0
    if re.match(r'^=[^=].*=', version_part):
        version = version_part.split('=')[1]
        return name, '=={}'.format(version)

    # Single = means glob: numpy=1.20 -> 1.20.*
    if version_part.startswith('=') and not version_part.startswith('=='):
        version = version_part.lstrip('=')
        if '*' not in version:
            version = version + '.*'
        return name, version

    # Already has operator (>=, <=, ==, !=, <, >, etc.)
    return name, version_part


def _format_dep_value(version):
    if version == '*':
        return '"*"'
    return _toml_string(version)


def _write_dependencies(lines, conda_packages, pip_packages, indent=''):
    """Write [dependencies] and [pypi-dependencies] sections."""
    if conda_packages:
        lines.append('{}[dependencies]'.format(indent))
        for spec in sorted(conda_packages, key=lambda s: _conda_spec_to_pixi(s)[0].lower()):
            name, version = _conda_spec_to_pixi(spec)
            lines.append('{}{} = {}'.format(indent, name, _format_dep_value(version)))
        lines.append('')

    if pip_packages:
        lines.append('{}[pypi-dependencies]'.format(indent))
        for spec in sorted(pip_packages):
            # pip specs are already in pip format (e.g. "package>=1.0")
            m = re.match(r'^([a-zA-Z0-9_][a-zA-Z0-9_.\-]*(?:\[[^\]]*\])?)\s*(.*)?$', spec)
            if m:
                name = m.group(1)
                version = m.group(2).strip() if m.group(2) else '*'
                lines.append('{}{} = {}'.format(indent, name, _format_dep_value(version)))
        lines.append('')


# anaconda-project sets these in the runtime environment for every task; pixi
# provides equivalents that we can substitute in command strings so that
# `pixi run <task>` resolves them the same way `anaconda-project run` does.
# Vars that pixi sets natively (CONDA_PREFIX, PATH, CONDA_DEFAULT_ENV) map to
# themselves and just need to survive the syntax conversion below.
_ANACONDA_PROJECT_ENV_VAR_MAP = {
    'PROJECT_DIR': 'PIXI_PROJECT_ROOT',
    'CONDA_ENV_PATH': 'CONDA_PREFIX',
    'CONDA_PREFIX': 'CONDA_PREFIX',
    'CONDA_DEFAULT_ENV': 'CONDA_DEFAULT_ENV',
    'PATH': 'PATH',
}

# Matches ${VAR}, $VAR, and %VAR% references in a command string. The Windows
# %VAR% form is included because anaconda-project commands routinely carry
# both unix and windows command lines, and we may emit either.
_ENV_VAR_REF_RE = re.compile(
    r'\$\{(?P<braced>[A-Za-z_][A-Za-z0-9_]*)\}'
    r'|\$(?P<bare>[A-Za-z_][A-Za-z0-9_]*)'
    r'|%(?P<windows>[A-Za-z_][A-Za-z0-9_]*)%'
)


# pixi's task activation prepends the env's executable directories to PATH:
#   * unix: ${CONDA_PREFIX}/bin
#   * windows: ${CONDA_PREFIX}, ${CONDA_PREFIX}/Scripts, ${CONDA_PREFIX}/Library/bin,
#     ${CONDA_PREFIX}/Library/usr/bin, ${CONDA_PREFIX}/Library/mingw-w64/bin
# So anything explicitly rooted at one of those locations can be reduced to
# its bare command name, and PATH resolution will find the right binary on
# whichever platform pixi is invoked on.
#
# Match either:
#   ${CONDA_PREFIX}/<known-subdir>/<name>[.ext]   — always safe to strip
#   ${CONDA_PREFIX}/<name>.<exe-ext>              — only safe with an
#     executable extension, because the conda env root is only on PATH on
#     Windows. With an .exe/.bat/.cmd/.com suffix we know it's a Windows
#     binary that PATH will find.
_CONDA_PREFIX_STRIP_RE = re.compile(
    r'(?:\$\{CONDA_PREFIX\}|\$CONDA_PREFIX)/'
    r'(?:'
    r'(?:bin|Scripts|Library/bin|Library/usr/bin|Library/mingw-w64/bin)/'
    r'(?P<sub>[A-Za-z0-9_.\-]+?)(?:\.exe|\.bat|\.cmd|\.com)?'
    r'|'
    r'(?P<root>[A-Za-z0-9_.\-]+?)(?:\.exe|\.bat|\.cmd|\.com)'
    r')'
    r'(?=\s|$|["\'])'
)


def _strip_conda_prefix_paths(command_str):
    """Drop ${CONDA_PREFIX}-rooted path prefixes from command tokens.

    Pixi puts the env's executable directories at the front of PATH, so users
    don't need to spell out ``${CONDA_PREFIX}/bin/python`` — bare ``python``
    resolves to the same binary. Folding these to the bare form makes unix
    and windows forms agree more often (so we emit one task instead of a
    divergence comment) and keeps the task portable.
    """
    def replace(m):
        return m.group('sub') or m.group('root')
    return _CONDA_PREFIX_STRIP_RE.sub(replace, command_str)


def _translate_command_env_vars(command_str, declared_vars):
    """Rewrite env-var references in a command string for execution under pixi.

    Pixi runs tasks through deno_task_shell, which only expands the bare
    ``$VAR`` form — the braced ``${VAR}`` form is a parse error. We emit the
    bare form whenever it's unambiguous (i.e. the next character can't extend
    the variable name) and the braced form otherwise so the right substring
    is taken as the var name.

    We:

    * Map well-known anaconda-project vars (``PROJECT_DIR``, ``CONDA_ENV_PATH``)
      to their pixi equivalents.
    * Pass through vars the project declares itself (they end up in
      ``[activation.env]`` or are required-from-environment).
    * Convert any Windows-style ``%VAR%`` to the deno_task_shell form.
    * Collect any reference we can't account for and return it for the caller
      to flag in a comment.

    Returns ``(translated_command, unresolved_vars)``.
    """
    unresolved = []
    seen_unresolved = set()

    def replace(match):
        name = match.group('braced') or match.group('bare') or match.group('windows')
        target = _ANACONDA_PROJECT_ENV_VAR_MAP.get(name, name)
        # If we couldn't map the name to a pixi-known var or a project-declared
        # var, flag it for the caller — the rewrite still emits the var as-is,
        # but the user needs to set it via [activation.env] or the shell.
        if name not in _ANACONDA_PROJECT_ENV_VAR_MAP and name not in declared_vars:
            if name not in seen_unresolved:
                seen_unresolved.add(name)
                unresolved.append(name)
        # deno_task_shell rejects ${VAR}; use bare $VAR unless the following
        # character would extend the var name (alphanumeric or underscore),
        # in which case fall back to a portable form. Since deno doesn't
        # accept braces at all, we wrap the var with a no-op separator —
        # there isn't one — so we accept that the bare form must be used and
        # keep the original braces only when there is no ambiguity. In
        # practice, command lines almost always have a separator after the
        # var (slash, space, dot, etc.).
        end = match.end()
        next_char = command_str[end] if end < len(command_str) else ''
        if next_char and (next_char.isalnum() or next_char == '_'):
            # Ambiguous bare form — preserve braces; deno will error here,
            # but the original command had the same problem and there's no
            # safe rewrite. Note this is rare; real commands separate the
            # var with a path/space/etc.
            return '${{{}}}'.format(target)
        return '${}'.format(target)

    return _ENV_VAR_REF_RE.sub(replace, command_str), unresolved


# Tokens are delimited by whitespace and shell metacharacters. We only rewrite
# backslashes inside tokens that look path-shaped (contain a ${VAR} reference
# or a recognizable path/extension fragment) so we don't mangle shell escapes,
# regex literals, or quoted strings that happen to contain a backslash.
_TOKEN_SPLIT_RE = re.compile(r'(\s+|[|&;<>()])')
_PATH_SHAPED_RE = re.compile(r'(\$\{[^}]+\}|\.\\|/|\.[A-Za-z]{1,5}(?:\\|$|/))')


def _windows_to_deno_shell(command_str):
    """Best-effort rewrite of a Windows command string to the unix-flavored
    form deno_task_shell understands.

    Currently this only swaps backslashes for forward slashes inside
    path-shaped tokens. Env-var translation (``%VAR%`` → ``${VAR}``) is left
    to ``_translate_command_env_vars``, which runs after this normalization.
    """
    parts = _TOKEN_SPLIT_RE.split(command_str)
    out = []
    for part in parts:
        if part and _PATH_SHAPED_RE.search(part):
            out.append(part.replace('\\', '/'))
        else:
            out.append(part)
    return ''.join(out)


_PREPARE_MARKER_ECHO = 'echo "Running migrated anaconda-project prepare task..."'

# Helper script written next to pixi.toml during conversion; see
# anaconda_project/internal/ap_download.py for the source. Prepare tasks
# invoke it via `python ap_download.py <url> <filename> [<description>]`
# rather than inlining the urllib calls — keeps the TOML readable, and the
# script can grow over time without bloating the manifest.
DOWNLOAD_HELPER_FILENAME = 'ap_download.py'


def _has_python(specs):
    """Return True if any spec in ``specs`` declares the ``python`` package.

    Specs may be channel-prefixed (``conda-forge::python``) or version-
    constrained (``python=3.11``, ``python>=3.10``) — strip the metadata
    before comparing.
    """
    for spec in specs:
        name, _ = _conda_spec_to_pixi(spec)
        if name == 'python':
            return True
    return False


def _shell_quote(value):
    """Quote a string for safe inclusion in a deno_task_shell argv.

    Wrap with double quotes and escape only the characters that have
    special meaning inside a double-quoted token: ``"``, ``\\``, ``$``,
    and backtick. Anything else (including spaces, single quotes, and
    glob characters) survives unchanged.
    """
    escaped = (value
               .replace('\\', '\\\\')
               .replace('"', '\\"')
               .replace('$', '\\$')
               .replace('`', '\\`'))
    return '"{}"'.format(escaped)


def _build_prepare_command(downloads):
    """Build a multi-line shell command that runs the download helper script
    once per anaconda-project download entry.

    The helper (``ap_download.py``) is written alongside the pixi.toml at
    conversion time; we just emit ``python ap_download.py <args>`` for each
    download. The marker echo is omitted here because the helper's own
    ``[prepare] ...`` log lines are more informative — and because pixi
    bundles the marker echo and the first python invocation onto a single
    banner line, smashing them visually. Detection of "is this a converted
    anaconda-project?" still works via the task name `prepare`.
    """
    lines = []
    for description, url, filename in downloads:
        # `python3` (not `python`) so the helper resolves to system python
        # when the env doesn't declare its own. anaconda-project's yml may
        # not include python in every env_spec, and ap_download.py is pure
        # stdlib, so we don't need a project-specific interpreter.
        lines.append('python3 {script} {url} {path} {desc}'.format(
            script=DOWNLOAD_HELPER_FILENAME,
            url=_shell_quote(url),
            path=_shell_quote(filename),
            desc=_shell_quote(description),
        ))
    return '\n'.join(lines)


# Per-mode HTTP option tables. Each entry is (jinja_var, gate, body):
#   * jinja_var: variable name declared in pixi `args` and referenced by
#     {% if %} gates and {{ }} substitutions in the body.
#   * gate: 'pos' renders body when the var is truthy ({% if var %}),
#     'neg' renders body when the var is falsy ({% if not var %}). The
#     latter is for bokeh's --show flag, which is the *inverse* of the
#     anaconda-project --no-browser semantics.
#   * body: the rendered chunk; may contain {{ var }} for value
#     substitution. Templated and gated by _wrap_gate at emit time.
#
# Each table is curated to match the per-tool transforms in
# anaconda_project/project_commands.py (_BokehArgsTransformer and
# _NotebookArgsTransformer); see HTTP_SPECS there for the source list.
_HTTP_GENERIC = (
    ('host',         'pos', '--anaconda-project-host {{ host }}'),
    ('port',         'pos', '--anaconda-project-port {{ port }}'),
    ('address',      'pos', '--anaconda-project-address {{ address }}'),
    ('url_prefix',   'pos', '--anaconda-project-url-prefix {{ url_prefix }}'),
    ('iframe_hosts', 'pos', '--anaconda-project-iframe-hosts {{ iframe_hosts }}'),
    ('no_browser',   'pos', '--anaconda-project-no-browser'),
    ('use_xheaders', 'pos', '--anaconda-project-use-xheaders'),
)

_HTTP_BOKEH = (
    ('host',         'pos', '--host {{ host }}'),
    ('port',         'pos', '--port {{ port }}'),
    ('address',      'pos', '--address {{ address }}'),
    # bokeh renames --anaconda-project-url-prefix to --prefix.
    ('url_prefix',   'pos', '--prefix {{ url_prefix }}'),
    # iframe_hosts: bokeh has no equivalent; the original transformer
    # drops it silently, so we omit it from the args declaration too.
    # `--show` is bokeh's "open browser" flag — the inverse of
    # anaconda-project's --no-browser, hence the negative gate.
    ('no_browser',   'neg', '--show'),
    ('use_xheaders', 'pos', '--use-xheaders'),
)

# Notebook iframe_hosts requires a Python dict literal embedded as a
# tornado_settings value carrying a Content-Security-Policy header. The
# original transformer prepends 'self' to the host list; we mirror that.
_NOTEBOOK_IFRAME_BODY = (
    "--NotebookApp.tornado_settings="
    "{ 'headers': { 'Content-Security-Policy': "
    "\"frame-ancestors 'self' {{ iframe_hosts }}\" } }"
)

_HTTP_NOTEBOOK = (
    # host: jupyter has no host-restrict equivalent; original drops it.
    ('port',         'pos', '--port {{ port }}'),
    ('address',      'pos', '--ip {{ address }}'),
    # url_prefix renames to --NotebookApp.base_url. The original
    # transformer comments that the two-arg (space-separated) form is
    # rejected here — only the `--key=value` form works — so we render
    # it that way.
    ('url_prefix',   'pos', '--NotebookApp.base_url={{ url_prefix }}'),
    ('iframe_hosts', 'pos', _NOTEBOOK_IFRAME_BODY),
    ('no_browser',   'pos', '--no-browser'),
    ('use_xheaders', 'pos', '--NotebookApp.trust_xheaders=True'),
)


def _wrap_gate(gate, var, body):
    """Wrap a chunk body in the appropriate Jinja conditional."""
    if gate == 'pos':
        return '{{% if {var} %}}{body}{{% endif %}}'.format(var=var, body=body)
    if gate == 'neg':
        return '{{% if not {var} %}}{body}{{% endif %}}'.format(var=var, body=body)
    return body


def _notebook_default_url_chunk(notebook_path):
    """Build the unconditional --NotebookApp.default_url=... prefix that
    anaconda-project's _NotebookArgsTransformer prepends to every jupyter
    invocation. URL-quoted basename, matching the original behavior."""
    from urllib.parse import quote
    basename = os.path.basename(notebook_path)
    return '--NotebookApp.default_url=/notebooks/{}'.format(quote(basename))

# Match `{{ name }}` / `{{name}}` Jinja variable references. Used when
# supports_http_options is false to discover which HTTP vars the user's
# templated unix line actually consumes; we only declare pixi args for
# those, not the full set.
_JINJA_VAR_RE = re.compile(r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}')


def _http_args_for_command(command):
    """Return the list of jinja var names to emit as pixi ``args``,
    plus a list of cmd chunks to append.

    Three dispatch paths, mirroring anaconda-project's per-tool
    transformers in ``project_commands.py``:

    * ``command.notebook is not None`` → the command was a converted
      ``notebook:`` shorthand (now ``jupyter notebook <file>``). Use
      the Jupyter-specific flag mapping (``--ip`` for address,
      ``--NotebookApp.*`` for prefix/iframe/xheaders, drop host).
    * ``command.bokeh_app is not None`` → converted ``bokeh_app:``
      shorthand (now ``bokeh serve <app>``). Use bokeh's bare flags
      (``--host``, ``--port``, ``--address``, ``--show`` as the
      *inverse* of ``--no-browser``, ``--use-xheaders``).
    * Otherwise (``supports_http_options: true`` on a plain
      ``unix:`` command) → pass ``--anaconda-project-X`` through
      verbatim so the underlying tool can pick up what it understands.

    For ``supports_http_options: false``, scan the user's templated
    unix line for HTTP Jinja vars and declare pixi args only for those;
    the cmd template is left unchanged.
    """
    if command.supports_http_options:
        if command.notebook is not None:
            table = _HTTP_NOTEBOOK
            preamble = [_notebook_default_url_chunk(command.notebook)]
        elif command.bokeh_app is not None:
            table = _HTTP_BOKEH
            preamble = []
        else:
            table = _HTTP_GENERIC
            preamble = []

        chunks = list(preamble)
        for var, gate, body in table:
            chunks.append(_wrap_gate(gate, var, body))
        args = [var for var, _, _ in table]
        return args, chunks

    # supports_http_options is false — only declare pixi args for vars
    # the templated unix line actually references.
    cmd = command.unix_shell_commandline or ''
    # The full superset of HTTP-related Jinja var names a user might
    # reference. Drawn from every per-tool table.
    all_http_vars = {var for var, _, _ in _HTTP_GENERIC}
    referenced = []
    seen = set()
    for match in _JINJA_VAR_RE.finditer(cmd):
        name = match.group(1)
        if name in seen or name not in all_http_vars:
            continue
        seen.add(name)
        referenced.append(name)
    return referenced, []


def _format_args_block(args):
    """Render a pixi ``args = [...]`` line. Defaults are always empty —
    the cmd template uses ``{% if var %}`` gating, so an empty value means
    the flag is omitted at run time. ``pixi run task value-for-port`` (or
    similar positional override) sets the var."""
    if not args:
        return None
    parts = ['{{ arg = "{}", default = "" }}'.format(var) for var in args]
    return 'args = [{}]'.format(', '.join(parts))


def _command_to_task(command, declared_vars):
    """Convert a ProjectCommand to a pixi task string or None.

    Pixi runs tasks under deno_task_shell, which speaks unix-style syntax on
    every platform. So we always emit a single task command — built from the
    unix line if present, or normalized from the windows line otherwise. When
    the project provides both and they disagree even after normalization, we
    keep the unix form (the deno_task_shell-native one) and surface the
    divergence in a comment so a maintainer can review.

    Returns ``(task_cmd_string, raw_cmd_string, comments, args_line)``.
    ``raw_cmd_string`` is the pre-translation form, useful for comparing
    against ``command.description``. ``args_line`` is the formatted
    pixi ``args = [...]`` declaration (or None if the command needs no
    pixi args).
    """
    comments = []
    # raw_forms holds every string that anaconda-project might use as the
    # synthesized command.description, so callers can suppress descriptions
    # that just echo the original command line.
    raw_forms = []
    raw_cmd = None
    if command.unix_shell_commandline:
        raw_cmd = command.unix_shell_commandline
        raw_forms.append(raw_cmd)
    elif command.notebook is not None:
        raw_cmd = 'jupyter notebook {}'.format(command.notebook)
        comments.append('converted from notebook command')
    elif command.bokeh_app is not None:
        raw_cmd = 'bokeh serve {}'.format(command.bokeh_app)
        comments.append('converted from bokeh_app command')
    elif command.windows_cmd_commandline:
        # No unix variant — normalize the windows form so it runs under
        # deno_task_shell on every platform pixi targets.
        raw_cmd = _windows_to_deno_shell(command.windows_cmd_commandline)
        raw_forms.append(command.windows_cmd_commandline)
        raw_forms.append(raw_cmd)
        comments.append('translated from windows-only command')
    else:
        return None, None, comments, None

    translated, unresolved = _translate_command_env_vars(raw_cmd, declared_vars)
    translated = _strip_conda_prefix_paths(translated)

    # Compose http-options support: append --anaconda-project-* flags
    # (gated by Jinja conditionals) when supports_http_options is true,
    # or just declare pixi args for whatever {{vars}} the user already
    # referenced when it's false. Append-chunks render as a wrapped
    # multi-line TOML string so the file stays readable, but parse to a
    # single shell command at run time.
    http_arg_vars, http_chunks = _http_args_for_command(command)
    if http_chunks:
        cmd_rendered = _toml_wrapped_string([translated, *http_chunks])
        # For windows-divergence comparison and any other plain-text use,
        # keep `translated` as the already-joined single-line form.
        translated = ' '.join([translated, *http_chunks])
    else:
        cmd_rendered = _toml_string(translated)
    args_line = _format_args_block(http_arg_vars)

    # If both forms exist, check that the windows line doesn't say something
    # the unix line doesn't — pixi can't run two variants of the same task,
    # so divergence is a maintainer-facing warning. We compare *after* both
    # env-var translation and conda-prefix stripping so that things like
    # ${CONDA_PREFIX}/bin/python and %CONDA_PREFIX%\python.exe collapse to
    # the same `python` and don't trigger a spurious divergence note.
    if command.unix_shell_commandline and command.windows_cmd_commandline:
        win_normalized = _windows_to_deno_shell(command.windows_cmd_commandline)
        win_translated, _ = _translate_command_env_vars(win_normalized, declared_vars)
        win_translated = _strip_conda_prefix_paths(win_translated)
        if win_translated != translated:
            comments.append(
                'windows command differs from unix; using unix form. '
                'windows would have been: {}'.format(win_translated))

    if unresolved:
        comments.append(
            'unresolved env var(s): {} — set them via [activation.env] or '
            'before running pixi'.format(', '.join(unresolved)))
    return cmd_rendered, raw_forms, comments, args_line


def export_pixi_toml(project):
    """Convert an anaconda-project Project to pixi.toml content.

    Args:
        project: an anaconda_project.project.Project instance

    Returns:
        A string containing the pixi.toml file content.
    """
    lines = []

    # -- [workspace] metadata, channels, and platforms
    # Collect channels from all env specs (union, preserving order). Pixi
    # has no `defaults` meta-channel and no notion of channel aliases that
    # match conda's, so we expand any `defaults` reference into the URLs
    # that conda would resolve it to. When the project declares no
    # channels at all, we fall back to those same default URLs rather
    # than hard-coding conda-forge — that preserves whatever the user's
    # conda environment treats as default (which may be an enterprise
    # mirror configured via .condarc).
    all_channels = []
    seen_channels = set()
    for env in project.env_specs.values():
        for ch in env.channels:
            if ch not in seen_channels:
                all_channels.append(ch)
                seen_channels.add(ch)

    needs_defaults = (not all_channels) or ('defaults' in all_channels)
    default_channels = _resolve_default_channels() if needs_defaults else None
    if not all_channels:
        all_channels = list(default_channels)
    elif 'defaults' in all_channels:
        all_channels = _expand_defaults_in_channels(all_channels, default_channels)

    # Collect platforms (union)
    all_platforms = set()
    for env in project.env_specs.values():
        all_platforms.update(env.platforms)
    if not all_platforms:
        all_platforms = {'linux-64'}

    # -- Determine if we need features (multiple env specs)
    env_specs = project.env_specs
    has_multiple_envs = len(env_specs) > 1 or (len(env_specs) == 1 and 'default' not in env_specs)

    # Placeholder for a warning prefix; populated below once we know
    # whether any download-needing env lacks python. We insert it at the
    # top of the file so it's the first thing a maintainer sees.
    warning_prefix_index = len(lines)

    lines.append('[workspace]')
    lines.append('name = {}'.format(_toml_string(project.name)))
    if project.description:
        lines.append('description = {}'.format(_toml_string(project.description)))
    lines.append('channels = {}'.format(_toml_inline_array(all_channels)))
    lines.append('platforms = {}'.format(_toml_inline_array(sorted(all_platforms))))
    lines.append('')

    # -- Collect global (inherited by all) packages
    # Find packages common to every env_spec — these go in the top-level
    # [dependencies] (i.e. pixi's default feature) and every named env
    # inherits them. Anything env-specific lands in [feature.X.dependencies]
    # below.
    if has_multiple_envs:
        all_conda = None
        all_pip = None
        for env in env_specs.values():
            conda_set = set(env.conda_packages)
            pip_set = set(env.pip_packages)
            if all_conda is None:
                all_conda = conda_set
                all_pip = pip_set
            else:
                all_conda &= conda_set
                all_pip &= pip_set
        global_conda = sorted(all_conda) if all_conda else []
        global_pip = sorted(all_pip) if all_pip else []
    elif env_specs:
        env = list(env_specs.values())[0]
        global_conda = list(env.conda_packages)
        global_pip = list(env.pip_packages)
    else:
        global_conda = []
        global_pip = []

    # If the user has an env_spec literally named `default`, fold its
    # packages into the global set — they belong to pixi's default feature,
    # not a separate `[feature.default.dependencies]` block (which would
    # be unreachable since we don't redeclare the default env below).
    if has_multiple_envs and 'default' in env_specs:
        default_env = env_specs['default']
        for spec in default_env.conda_packages:
            if spec not in global_conda:
                global_conda.append(spec)
        for spec in default_env.pip_packages:
            if spec not in global_pip:
                global_pip.append(spec)

    # Compute downloads per env now so we can both emit prepare task
    # bodies below and warn the caller about envs that lack python.
    downloads_per_env = {}
    for env_name in env_specs:
        env_downloads = []
        for req in project.requirements(env_name):
            if isinstance(req, DownloadRequirement):
                # Prefer the user-supplied description from the yml; fall
                # back to the env_var name when the user didn't write one.
                description = req.options.get('description') or req.env_var
                env_downloads.append((description, req.url, req.filename))
        if env_downloads:
            downloads_per_env[env_name] = env_downloads

    # Identify envs that need ap_download.py but don't declare python.
    # The helper is pure stdlib so it'll work with system `python3`, but
    # the user should know they're depending on something outside the
    # env. Insert a warning comment at the top of the file (above
    # [workspace]) so it's the first thing a maintainer sees.
    envs_relying_on_system_python = []
    if downloads_per_env and not _has_python(global_conda):
        for env_name in downloads_per_env:
            env = env_specs[env_name]
            if not _has_python(env.conda_packages):
                envs_relying_on_system_python.append(env_name)

    if envs_relying_on_system_python:
        warning = [
            '# WARNING: prepare task uses system python3 to run ap_download.py.',
            '# The following env(s) declare downloads but no python package:',
        ]
        for env_name in envs_relying_on_system_python:
            warning.append('#   {}'.format(env_name))
        warning.append(
            '# Add `python` to the env_spec(s) above if you want a sandboxed '
            'interpreter.')
        warning.append('')
        lines[warning_prefix_index:warning_prefix_index] = warning

    # Write global dependencies
    _write_dependencies(lines, global_conda, global_pip)

    # -- [activation] for variables
    variables_with_defaults = {}
    for req in project.requirements(project.default_env_spec_name):
        if isinstance(req, (CondaEnvRequirement, DownloadRequirement, ServiceRequirement)):
            continue
        if isinstance(req, EnvVarRequirement):
            default = req.default_as_string
            if default is not None:
                variables_with_defaults[req.env_var] = default

    if variables_with_defaults:
        lines.append('[activation.env]')
        for var_name in sorted(variables_with_defaults):
            lines.append('{} = {}'.format(var_name, _toml_string(variables_with_defaults[var_name])))
        lines.append('')

    # -- Features for non-default env specs
    if has_multiple_envs:
        global_conda_set = set(global_conda)
        global_pip_set = set(global_pip)

        for env_name, env in env_specs.items():
            # `default` is folded into the global default feature above —
            # nothing to emit as a separate [feature.default.X] block.
            if env_name == 'default':
                continue

            extra_conda = [p for p in env.conda_packages if p not in global_conda_set]
            extra_pip = [p for p in env.pip_packages if p not in global_pip_set]

            pixi_env_name = _sanitize_env_name(env_name)
            if extra_conda or extra_pip:
                if extra_conda:
                    lines.append('[feature.{}.dependencies]'.format(pixi_env_name))
                    for spec in sorted(extra_conda, key=lambda s: _conda_spec_to_pixi(s)[0].lower()):
                        name, version = _conda_spec_to_pixi(spec)
                        lines.append('{} = {}'.format(name, _format_dep_value(version)))
                    lines.append('')

                if extra_pip:
                    lines.append('[feature.{}.pypi-dependencies]'.format(pixi_env_name))
                    for spec in sorted(extra_pip):
                        m = re.match(r'^([a-zA-Z0-9_][a-zA-Z0-9_.\-]*(?:\[[^\]]*\])?)\s*(.*)?$', spec)
                        if m:
                            name = m.group(1)
                            version = m.group(2).strip() if m.group(2) else '*'
                            lines.append('{} = {}'.format(name, _format_dep_value(version)))
                    lines.append('')

        # -- [environments] section
        # Emit envs in the order they appear in anaconda-project.yml so
        # downstream tooling can identify the project's intended default
        # env_spec by reading the first entry. Common packages live in
        # top-level [dependencies] (the default feature) and every named
        # env inherits them.
        #
        # If the user happened to name one of their env_specs `default`,
        # we comment its slot rather than declare it — pixi already
        # materializes a `default` environment from the default feature,
        # and re-declaring it would either no-op or fight that machinery.
        # The comment preserves position so callers reading the first
        # uncommented entry still get the user's first non-default env.
        lines.append('[environments]')
        for env_name in env_specs:
            if env_name == 'default':
                lines.append('# default  (pixi creates this implicitly from the default feature)')
            else:
                pixi_env_name = _sanitize_env_name(env_name)
                lines.append('{name} = {{ features = ["{name}"] }}'.format(name=pixi_env_name))
        lines.append('')

    # -- Collect every env var the project declares, so command-string
    # references to them survive translation untouched. Includes
    # `variables:` (with or without defaults), `downloads:`, and `services:`.
    declared_vars = set()
    for env_name in env_specs:
        for req in project.requirements(env_name):
            if isinstance(req, CondaEnvRequirement):
                continue
            if isinstance(req, EnvVarRequirement):
                declared_vars.add(req.env_var)

    # -- [tasks] from commands
    commands = project.commands
    if commands:
        # Only emit [tasks] header if there are global (non-feature) tasks
        global_tasks = []
        feature_tasks = []
        for cmd_name, command in sorted(commands.items()):
            env_spec_name = command.default_env_spec_name
            if has_multiple_envs and env_spec_name and env_spec_name != 'default':
                feature_tasks.append((cmd_name, command))
            else:
                global_tasks.append((cmd_name, command))

        for cmd_name, command in global_tasks:
            task_cmd, raw_forms, comments, args_line = _command_to_task(
                command, declared_vars)
            if task_cmd is None:
                lines.append('# {} — could not convert (no unix command)'.format(cmd_name))
                continue
            desc = command.description
            has_desc = desc and desc != cmd_name and desc not in (raw_forms or [])
            for comment in comments:
                lines.append('# {}'.format(comment))
            # Always use the explicit [tasks.X] form. The shorthand
            # `name = "cmd"` doesn't allow args, and consistency reads
            # better than mixing two forms.
            lines.append('[tasks.{}]'.format(cmd_name))
            lines.append('cmd = {}'.format(task_cmd))
            if has_desc:
                lines.append('description = {}'.format(_toml_string(desc)))
            if args_line:
                lines.append(args_line)
            lines.append('')

        for cmd_name, command in feature_tasks:
            task_cmd, raw_forms, comments, args_line = _command_to_task(
                command, declared_vars)
            if task_cmd is None:
                lines.append('# {} — could not convert (no unix command)'.format(cmd_name))
                continue
            desc = command.description
            env_spec_name = command.default_env_spec_name
            pixi_env_name = _sanitize_env_name(env_spec_name)
            has_desc = desc and desc != cmd_name and desc not in (raw_forms or [])
            section = 'feature.{}.tasks.{}'.format(pixi_env_name, cmd_name)
            lines.append('[{}]'.format(section))
            lines.append('cmd = {}'.format(task_cmd))
            if has_desc:
                lines.append('description = {}'.format(_toml_string(desc)))
            if args_line:
                lines.append(args_line)
            for comment in comments:
                lines.append('# {}'.format(comment))
            lines.append('')

    # -- `prepare` task
    # Mirror anaconda-project's prepare semantics for the default env:
    # fetch any declared downloads. Emit exactly one `prepare` task,
    # scoped to the default env_spec's feature when there is one (so it
    # only resolves under that env), or at the top level when the manifest
    # has no [environments] table.
    #
    # The presence of `prepare` is itself the canonical signal that this
    # pixi.toml was converted from anaconda-project.yml. Other env_specs
    # don't get a prepare task — keeps the manifest small and avoids
    # pixi's env-selection prompt entirely.
    if 'default' in env_specs:
        default_source = 'default'
    elif project.default_env_spec_name in env_specs:
        default_source = project.default_env_spec_name
    elif env_specs:
        default_source = next(iter(env_specs))
    else:
        default_source = None

    if default_source in downloads_per_env:
        prepare_body = _toml_multiline_string(
            _build_prepare_command(downloads_per_env[default_source]))
    else:
        prepare_body = _toml_string(_PREPARE_MARKER_ECHO)

    # Multi-env: scope to the default env's feature so `pixi run prepare`
    # auto-resolves to that env. (When the default is the literal
    # `default`, fold to the global default feature — pixi's implicit
    # default env picks it up.)
    if has_multiple_envs and default_source and default_source != 'default':
        pixi_env_name = _sanitize_env_name(default_source)
        lines.append('[feature.{}.tasks.prepare]'.format(pixi_env_name))
    else:
        lines.append('[tasks.prepare]')
    lines.append('cmd = {}'.format(prepare_body))
    lines.append('')

    # -- Services as comments
    services = {}
    for env_name in env_specs:
        for req in project.requirements(env_name):
            if isinstance(req, ServiceRequirement):
                services[req.env_var] = req.service_type

    if services:
        lines.append('# Services from anaconda-project.yml (no pixi equivalent):')
        for var_name, svc_type in sorted(services.items()):
            lines.append('#   {} = {}'.format(var_name, svc_type))
        lines.append('')

    # -- Variables without defaults as comments
    vars_without_defaults = {}
    for req in project.requirements(project.default_env_spec_name):
        if isinstance(req, (CondaEnvRequirement, DownloadRequirement, ServiceRequirement)):
            continue
        if isinstance(req, EnvVarRequirement) and req.default_as_string is None:
            vars_without_defaults[req.env_var] = req.description or ''

    if vars_without_defaults:
        lines.append('# Required environment variables (set these before running):')
        for var_name, desc in sorted(vars_without_defaults.items()):
            if desc:
                lines.append('#   {} — {}'.format(var_name, desc))
            else:
                lines.append('#   {}'.format(var_name))
        lines.append('')

    return '\n'.join(lines).rstrip() + '\n'
