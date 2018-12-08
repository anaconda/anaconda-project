# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Run checks script."""

from __future__ import print_function

# Standard library imports
import argparse
import codecs
import copy
# import errno
import os
import platform
import re
import subprocess
import sys

# Local imports
from setup_atomic_replace import atomic_replace

# Constants
HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.dirname(HERE)
PY2 = sys.version_info[0] == 2
coding_utf8_header = u"# -*- coding: utf-8 -*-\n"
copyright_header = u"""
# -----------------------------------------------------------------------------
# Copyright (c) 2017, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# (See LICENSE.txt for details)
# -----------------------------------------------------------------------------
""".lstrip()
copyright_re = re.compile('# *Copyright ')

if os.getenv('TRAVIS') == "true":
    # Travis makes multiprocessing return 32 CPUs,
    # but really it's a container with 2 cores.
    print("Using CPU count of 2 because we're on Travis.", file=sys.stderr)
    CPU_COUNT = 2
else:
    try:
        import multiprocessing
        CPU_COUNT = multiprocessing.cpu_count()
    except Exception:
        print("Using fallback CPU count", file=sys.stderr)
        CPU_COUNT = 4


class Profiler(object):
    def __init__(self):
        import cProfile
        self._profiler = cProfile.Profile()

    def __exit__(self, type, value, traceback):
        self._profiler.disable()

        import pstats
        ps = pstats.Stats(self._profiler, stream=sys.stdout).sort_stats('cumulative')
        ps.print_stats()

    def __enter__(self):
        self._profiler.enable()


try:
    # Attempt to force coverage to skip_covered, which pytest-cov
    # doesn't expose as an option (.coveragerc option for this is
    # ignored by pytest-cov)
    from coverage.summary import SummaryReporter
    original_init = SummaryReporter.__init__

    def modified_init(self, coverage, config):
        config.skip_covered = True
        original_init(self, coverage, config)

    SummaryReporter.__init__ = modified_init
    print("Coverage monkeypatched to skip_covered")
except Exception as e:
    print("Failed to monkeypatch coverage: " + str(e), file=sys.stderr)


def _sort_by_mtime(filenames):
    with_mtime = [(name, os.path.getmtime(name)) for name in filenames]
    reordered = sorted(with_mtime, key=lambda x: x[1])
    return [name for (name, mtime) in reordered]


class TestRunner:
    def __init__(self,
                 pytest_args=None,
                 format_only=False,
                 git_staged_only=False,
                 profile_formatting=False,
                 skip_slow_tests=False):
        # TestCommand.initialize_options(self)

        # -rw turns on printing warnings. To see stack trace from
        # KeyboardInterrupt, add --fulltrace but it also makes the
        # traces huge by showing source code for each frame, so not
        # adding it by default.
        # To see stdout "live" instead of capturing it, use -s.
        coverage_args = [
            '--cov-config',
            os.path.join(ROOT, ".coveragerc"), '--cov=anaconda_project', '--cov-report=term-missing',
            '--cov-report=html', '--cov-fail-under=99', '--no-cov-on-fail'
        ]
        if PY2:
            # xdist appears to lock up the test suite with python
            # 2, maybe due to an interaction with coverage
            enable_xdist = []
        else:
            # Recent conda downright explodes if run from multiple processes
            # at once, so skip xdist until we add our own locking layer or
            # something
            enable_xdist = []
            # enable_xdist = ['-n', str(CPU_COUNT)]

        self.pytest_args = ['-rfew', '--durations=10', '-v'] + enable_xdist
        if pytest_args:
            if isinstance(pytest_args, list):
                pytest_args = pytest_args[0]
            self.pytest_args = [a for a in pytest_args.split(' ') if a]

        # 100% coverage on Windows requires us to do extra mocks because
        # generally Windows can't run all the servers, such as redis-server.
        # So we relax the coverage requirement for Windows only.
        if platform.system() != 'Windows':
            self.pytest_args = self.pytest_args + coverage_args

        self.pyfiles = None
        self.git_staged_pyfiles = None
        self.failed = []
        self.format_only = format_only
        self.git_staged_only = git_staged_only
        self.profile_formatting = profile_formatting
        self.skip_slow_tests = skip_slow_tests

    def _py_files(self):
        if self.pyfiles is None:
            pyfiles = []
            for root, dirs, files in os.walk(ROOT):
                # Chop out hidden directories
                files = [f for f in files if not f[0] == '.']
                dirs[:] = [d for d in dirs if (d[0] != '.' and d not in ('build', '__pycache__', 'docs'))]

                # Now walk files
                for f in files:
                    if f.endswith(".py"):
                        pyfiles.append(os.path.join(root, f))
            self.pyfiles = _sort_by_mtime(pyfiles)

        return self.pyfiles

    def _git_staged_py_files(self):
        if self.git_staged_pyfiles is None:
            # --diff-filter=AM means "added" and "modified"
            # -z means nul-separated names
            out = subprocess.check_output(['git', 'diff', '--cached', '--name-only', '--diff-filter=AM', '-z'])
            git_changed = set(out.decode('utf-8').split('\x00'))
            # There's an empty line or something in the git output
            git_changed.discard('')
            print("Found %d added/modified files: %r" % (len(git_changed), git_changed))
            git_changed = {os.path.join(ROOT, filename) for filename in git_changed}
            self.git_staged_pyfiles = [filename for filename in self._py_files() if filename in git_changed]
        return self.git_staged_pyfiles

    def _git_staged_or_all_py_files(self):
        if self.git_staged_only:
            return self._git_staged_py_files()
        else:
            return self._py_files()

    def _add_missing_init_py(self):
        root_modules = ['anaconda_project']
        for srcdir in root_modules:
            for root, dirs, files in os.walk(os.path.join(ROOT, srcdir)):
                dirs[:] = [d for d in dirs if not (d[0] == '.' or d == '__pycache__')]
                for d in dirs:
                    init_py = os.path.join(root, d, "__init__.py")
                    if not os.path.exists(init_py):
                        print("Creating " + init_py)
                        with codecs.open(init_py, 'w', 'utf-8') as handle:
                            handle.flush()

    def _headerize_file(self, path):
        with codecs.open(path, 'r', 'utf-8') as file:
            old_contents = file.read()
        have_coding = (coding_utf8_header in old_contents)
        have_copyright = (copyright_re.search(old_contents) is not None)
        if have_coding and have_copyright:
            return

        if not have_coding:
            print("No encoding header comment in " + path)
            if "encoding_header" not in self.failed:
                self.failed.append("encoding_header")
        if not have_copyright:
            print("No copyright header comment in " + path)
            if "copyright_header" not in self.failed:
                self.failed.append("copyright_header")

        # Note: do NOT automatically change the copyright owner or
        # date.  The copyright owner/date is a statement of legal
        # reality, not a way to create legal reality. All we do
        # here is add an owner/date if there is none; if it's
        # incorrect, the person creating/reviewing the pull
        # request will need to fix it. If there's already an
        # owner/date then we leave it as-is assuming someone
        # has manually chosen it.
        contents = old_contents

        if not have_copyright:
            print("Adding copyright header to: " + path)
            contents = copyright_header + contents

        if not have_coding:
            print("Adding encoding header to: " + path)
            contents = coding_utf8_header + contents

        atomic_replace(path, contents, 'utf-8')

    def _headers(self):
        print("Checking file headers...")
        for pyfile in self._git_staged_or_all_py_files():
            # don't force headers on the examples.
            if "/examples/" in pyfile or "\\examples\\" in pyfile:
                continue
            self._headerize_file(pyfile)

    def _start_format_files(self, paths):
        import subprocess
        proc = subprocess.Popen([sys.executable, os.path.join(HERE, 'setup_yapf_task.py')] + paths)
        return proc

    def _yapf(self):
        print("Formatting files...")

        # this uses some silly multi-process stuff because Yapf is
        # very very slow and CPU-bound.
        # Not using a multiprocessing because not sure how its "magic"
        # (pickling, __main__ import) really works.
        print("%d CPUs to run yapf processes" % CPU_COUNT)
        processes = []

        def await_one_process():
            if processes:
                # we pop(0) because the first process is the oldest
                proc = processes.pop(0)
                proc.wait()
                if proc.returncode != 0:
                    # we fail the tests if we reformat anything, because
                    # we want CI to complain if a PR didn't run yapf
                    if len(self.failed) == 0 or self.failed[-1] != 'yapf':
                        self.failed.append("yapf")

        def await_all_processes():
            while processes:
                await_one_process()

        def take_n(items, n):
            result = []
            while n > 0 and items:
                result.append(items.pop())
                n = n - 1
            return result

        all_files = list(self._git_staged_or_all_py_files())
        while all_files:
            # we send a few files to each process to try to reduce
            # per-process setup time
            some_files = take_n(all_files, 3)
            processes.append(self._start_format_files(some_files))
            while len(processes) > CPU_COUNT:
                await_one_process()
        assert [] == all_files
        await_all_processes()
        assert [] == processes

    def _flake8(self):
        try:
            from flake8.engine import get_style_guide
        except ImportError:
            from flake8.api.legacy import get_style_guide
        ignore = [
            'W503',  # line break before binary op
            'W504',  # line break after binary op
            'E126',  # continuation line over-indented
        ]
        flake8_style = get_style_guide(paths=self._git_staged_or_all_py_files(), max_line_length=120, ignore=ignore)
        print("running flake8...")
        report = flake8_style.check_files()
        if report.total_errors > 0:
            print(str(report.total_errors) + " flake8 errors, see above to fix them")
            self.failed.append('flake8')
        else:
            print("flake8 passed!")

    def _pep257(self):
        from pep257 import (run_pep257, NO_VIOLATIONS_RETURN_CODE, VIOLATIONS_RETURN_CODE, INVALID_OPTIONS_RETURN_CODE)
        from pep257 import log as pep257_log

        # hack pep257 not to spam enormous amounts of debug logging if you
        # use pytest -s.
        # run_pep257() below calls log.setLevel
        def ignore_set_level(level):
            pass

        pep257_log.setLevel = ignore_set_level

        # hack alert (replacing argv temporarily because pep257 looks at it)
        old_argv = sys.argv
        try:
            sys.argv = ['pep257', os.path.join(ROOT, 'anaconda_project')]
            code = run_pep257()
        finally:
            sys.argv = old_argv
        if code == INVALID_OPTIONS_RETURN_CODE:
            print("pep257 found invalid configuration.")
            self.failed.append('pep257')
        elif code == VIOLATIONS_RETURN_CODE:
            print("pep257 reported some violations.")
            self.failed.append('pep257')
        elif code == NO_VIOLATIONS_RETURN_CODE:
            print("pep257 says docstrings look good.")
        else:
            raise RuntimeError("unexpected code from pep257: " + str(code))

    def _pytest(self):
        import pytest
        from pytest_cov.plugin import CoverageError

        pytest_args = copy.copy(self.pytest_args)
        if self.skip_slow_tests:
            pytest_args.append("-k-slow")
            print("Skipping slow tests")

        try:
            errno = pytest.main(pytest_args)
            if errno != 0:
                print("pytest failed, code {errno}".format(errno=errno))
                self.failed.append('pytest')
        except CoverageError as e:
            print("Test coverage failure: " + str(e))
            self.failed.append('pytest-coverage')

    def run_tests(self):
        if os.path.exists(os.path.join(ROOT, '.eggs')):
            print(".eggs directory exists which means some dependency was " "not installed via conda/pip")
            print("  (if this happens on CI, this may need fixing in " ".travis.yml or appveyor.xml)")
            print("  (if this happens on your workstation, try conda/pip " "installing the deps and deleting .eggs")
            self.failed.append("eggs-directory-exists")

        if self.git_staged_only:
            print("Only formatting %d git-staged python files, skipping "
                  "%d files" % (len(self._git_staged_py_files()), len(self._py_files())))

        self._add_missing_init_py()

        # _update_version_file()
        self._headers()

        # only yapf is slow enough to really be worth profiling
        if self.profile_formatting:
            with Profiler():
                self._yapf()
        else:
            self._yapf()
        self._flake8()
        if not self.format_only:
            self._pytest()
        self._pep257()

        if len(self.failed) > 0:
            print("Failures in: " + repr(self.failed))
            sys.exit(1)
        else:
            if self.git_staged_only:
                print("Skipped some files (only checked %d added/modified "
                      "files)." % len(self._git_staged_py_files()))
            if self.format_only:
                print("Formatting looks good, but didn't run tests.")
            else:
                import platform
                if platform.system() == 'Windows':
                    # Windows console defaults to crap encoding so they get
                    # no flair
                    print("All tests passed!")
                else:
                    print("All tests passed! 💯 🌟")


def main():
    parser = argparse.ArgumentParser(description='Run tests')
    parser.add_argument(
        '--pytest-args',
        action="store",
        dest="pytest_args",
        default=None,
        nargs='*',
        help="Pass custom pytests arguments",
    )
    parser.add_argument(
        '--format-only',
        action="store_true",
        dest="format_only",
        default=None,
        help="Only run the linters and formatters not the actual tests",
    )
    parser.add_argument(
        '--git-staged-only',
        action="store_true",
        dest="git_staged_only",
        default=None,
        help="Only run the linters and formatters on files added to the commit",
    )
    parser.add_argument(
        '--skip-slow-tests',
        action="store_true",
        dest="skip_slow_tests",
        default=None,
        help="Skip tests marked slow",
    )
    parser.add_argument(
        '--profile-formatting',
        action="store_true",
        dest="profile_formatting",
        default=None,
        help="Profile the linter and formatter steps",
    )

    options = parser.parse_args()
    tr = TestRunner(
        pytest_args=options.pytest_args,
        format_only=options.format_only,
        git_staged_only=options.git_staged_only,
        skip_slow_tests=options.skip_slow_tests,
        profile_formatting=options.profile_formatting)
    tr.run_tests()


if __name__ == '__main__':
    main()
