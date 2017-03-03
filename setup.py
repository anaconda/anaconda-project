# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Setup script."""

from __future__ import print_function

import codecs
import errno
import os
import platform
import re
import shutil
import subprocess
import sys
from os.path import dirname, realpath
from distutils.core import setup, Command
from setuptools.command.test import test as TestCommand
from setup_atomic_replace import atomic_replace

ROOT = dirname(realpath(__file__))
VERSION_PY = os.path.join(ROOT, 'anaconda_project', 'version.py')


def _obtain_version():
    # if we're running on a git checkout we generate
    # version.py and if we're running from a source dist
    # we use the existing version.py
    if os.path.isdir(os.path.join(ROOT, ".git")):
        tag = os.environ.get("GIT_DESCRIBE_TAG", None)
        if tag is None or tag == "":
            out = subprocess.check_output(['git', 'describe', '--tags'])
            tag = out.decode('utf-8').strip()
            if tag == '':
                raise Exception("git describe didn't give us a tag")
        if tag is None:
            raise Exception("Could not obtain git tag")

        # the tag may be only "v2.1" or may be "v2.1-NN-ABCEFG",
        # if the latter we drop the extra stuff
        pieces = tag.replace("v", "").split("-")
        version = pieces[0]
        print("git tag is %s, version is %s" % (tag, version))
        return version
    elif os.path.isfile(VERSION_PY):
        from anaconda_project.version import version
        return version
    else:
        raise Exception("Not a git checkout and no file %s" % VERSION_PY)


VERSION = _obtain_version()

assert VERSION != ''

PY2 = sys.version_info[0] == 2

REQUIRES = ['beautifulsoup4 >= 4.3', 'tornado >= 4.2']

TEST_REQUIRES = ['coverage', 'flake8 == 2.6.2', 'pep257', 'pytest', 'pytest-cov', 'yapf == 0.6.2', 'pytest-xdist',
                 'keyring >= 9.0']

# clean up leftover trash as best we can
BUILD_TMP = os.path.join(ROOT, 'build', 'tmp')
if os.path.isdir(BUILD_TMP):
    print("Cleaning up " + BUILD_TMP)
    try:
        shutil.rmtree(BUILD_TMP, ignore_errors=True)
    except Exception as e:
        print("Failed to remove %s: %s" % (BUILD_TMP, str(e)))
    else:
        print("Done removing " + BUILD_TMP)

coding_utf8_header = u"# -*- coding: utf-8 -*-\n"

copyright_header = u"""
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
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


def _update_version_file():
    version_code = ('"""Version information."""\n\n' + '# Note: this is a generated file, edit setup.py not here.\n' +
                    ('version = "%s"\n' % VERSION))
    content = coding_utf8_header + copyright_header + version_code
    try:
        old_content = codecs.open(VERSION_PY, 'r', 'utf-8').read()
    except IOError as e:
        if e.errno == errno.ENOENT:
            old_content = ""
        else:
            raise e
    if old_content != content:
        print("Updating " + VERSION_PY + " with version " + VERSION)
        atomic_replace(VERSION_PY, content, 'utf-8')


class AllTestsCommand(TestCommand):
    # `py.test --durations=5` == `python setup.py test -a "--durations=5"`
    user_options = [('pytest-args=', 'a', "Arguments to pass to py.test"),
                    ('format-only', None, "Only run the linters and formatters not the actual tests"),
                    ('git-staged-only', None, "Only run the linters and formatters on files added to the commit"),
                    ('profile-formatting', None, "Profile the linter and formatter steps")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        # -rw turns on printing warnings. To see stack trace from
        # KeyboardInterrupt, add --fulltrace but it also makes the
        # traces huge by showing source code for each frame, so not
        # adding it by default.
        # To see stdout "live" instead of capturing it, use -s.
        coverage_args = ['--cov-config', os.path.join(ROOT, ".coveragerc"), '--cov=anaconda_project',
                         '--cov-report=term-missing', '--cov-report=html', '--cov-fail-under=100', '--no-cov-on-fail']
        if PY2:
            # xdist appears to lock up the test suite with python
            # 2, maybe due to an interaction with coverage
            enable_xdist = []
        else:
            # Recent conda downright explodes if run from multiple processes at once,
            # so skip xdist until we add our own locking layer or something.
            enable_xdist = []
            # enable_xdist = ['-n', str(CPU_COUNT)]
        self.pytest_args = ['-rfew', '--durations=10'] + enable_xdist
        # 100% coverage on Windows requires us to do extra mocks because generally Windows
        # can't run all the servers, such as redis-server. So we relax the coverage requirement
        # for Windows only.
        if platform.system() != 'Windows':
            self.pytest_args = self.pytest_args + coverage_args
        self.pyfiles = None
        self.git_staged_pyfiles = None
        self.failed = []
        self.format_only = False
        self.git_staged_only = False
        self.profile_formatting = False

    def _py_files(self):
        if self.pyfiles is None:
            pyfiles = []
            for root, dirs, files in os.walk(ROOT):
                # chop out hidden directories
                files = [f for f in files if not f[0] == '.']
                dirs[:] = [d for d in dirs if (d[0] != '.' and d not in ('build', '__pycache__', 'docs'))]
                # now walk files
                for f in files:
                    if f.endswith(".py"):
                        pyfiles.append(os.path.join(root, f))
            self.pyfiles = pyfiles
        return self.pyfiles

    def _git_staged_py_files(self):
        if self.git_staged_pyfiles is None:
            # --diff-filter=AM means "added" and "modified"
            # -z means nul-separated names
            out = subprocess.check_output(['git', 'diff', '--cached', '--name-only', '--diff-filter=AM', '-z'])
            git_changed = set(out.decode('utf-8').split('\x00'))
            git_changed.discard('')  # there's an empty line or something in the git output
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
        proc = subprocess.Popen([sys.executable, os.path.join(ROOT, 'setup_yapf_task.py')] + paths)
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
            # don't run too many at once, this is a goofy algorithm
            if len(processes) > (CPU_COUNT * 3):
                while len(processes) > CPU_COUNT:
                    await_one_process()
        assert [] == all_files
        await_all_processes()
        assert [] == processes

    def _flake8(self):
        from flake8.engine import get_style_guide
        flake8_style = get_style_guide(paths=self._git_staged_or_all_py_files(),
                                       max_line_length=120,
                                       ignore=[
                                           'E126',  # complains about this list's indentation
                                           'E401'  # multiple imports on one line
                                       ])
        print("running flake8...")
        report = flake8_style.check_files()
        if report.total_errors > 0:
            print(str(report.total_errors) + " flake8 errors, see above to fix them")
            self.failed.append('flake8')
        else:
            print("flake8 passed!")

    def _pep257(self):
        from pep257 import run_pep257, NO_VIOLATIONS_RETURN_CODE, VIOLATIONS_RETURN_CODE, INVALID_OPTIONS_RETURN_CODE
        from pep257 import log as pep257_log

        # hack pep257 not to spam enormous amounts of debug logging if you use pytest -s.
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
        try:
            errno = pytest.main(self.pytest_args)
            if errno != 0:
                print("pytest failed, code {errno}".format(errno=errno))
                self.failed.append('pytest')
        except CoverageError as e:
            print("Test coverage failure: " + str(e))
            self.failed.append('pytest-coverage')

    def run_tests(self):
        if self.git_staged_only:
            print("Only formatting %d git-staged python files, skipping %d files" %
                  (len(self._git_staged_py_files()), len(self._py_files())))
        self._add_missing_init_py()
        _update_version_file()
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

        if os.path.exists(os.path.join(ROOT, '.eggs')):
            print(".eggs directory exists which means some dependency was not installed via conda/pip")
            print("  (if this happens on binstar, this may need fixing in .binstar.yml)")
            print("  (if this happens on your workstation, try conda/pip installing the deps and deleting .eggs")
            self.failed.append("eggs-directory-exists")

        if len(self.failed) > 0:
            print("Failures in: " + repr(self.failed))
            sys.exit(1)
        else:
            if self.git_staged_only:
                print("Skipped some files (only checked %d added/modified files)." % len(self._git_staged_py_files()))
            if self.format_only:
                print("Formatting looks good, but didn't run tests.")
            else:
                import platform
                if platform.system() == 'Windows':
                    # windows console defaults to crap encoding so they get no flair
                    print("All tests passed!")
                else:
                    print("All tests passed! 💯 🌟")


class VersionModuleCommand(Command):
    description = "Write out version.py"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        _update_version_file()


def _safe_makedirs(path):
    try:
        os.makedirs(path)
    except OSError:
        pass


class CondaPackageCommand(Command):
    description = "Create Conda packages"
    user_options = [('packages-dir=', None, "Where to put the packages"), ]

    def initialize_options(self):
        self.packages_dir = None

    def finalize_options(self):
        if self.packages_dir is None:
            self.packages_dir = os.path.join(ROOT, 'build', 'packages')
        _safe_makedirs(self.packages_dir)

    def run(self):
        try:
            self._real_run()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print("setup.py: Failed to build packages: " + str(e), file=sys.stderr)
            sys.exit(1)

    def _real_run(self):
        recipe_dir = os.path.join(ROOT, 'conda.recipe')
        python_versions = ('2.7', '3.4', '3.5', '3.6')
        all_final_package_paths = []
        for python_version in python_versions:
            out = subprocess.check_output(['conda', 'build', '--output', '--python', python_version, recipe_dir])
            package_path = out.decode('utf-8').strip()
            print("expected conda package path: " + package_path)
            if '--' in package_path:
                # conda build bug?
                print("package_path looks broken, contains -- in it. fixing...")
                package_path = package_path.replace("--", "-%s-" % VERSION)
                print("new conda package path: " + package_path)
            build_arch = os.path.basename(os.path.dirname(package_path))
            python_scoped_package_dir = os.path.join(self.packages_dir, "py%s" % python_version)
            final_package_path = os.path.join(python_scoped_package_dir, build_arch, os.path.basename(package_path))
            all_final_package_paths.append(final_package_path)
            if os.path.isfile(final_package_path):
                print("Package for python %s platform %s already exists: %s" %
                      (python_version, build_arch, final_package_path))
            else:
                if os.path.isfile(package_path):
                    print("Already built for python %s at %s" % (python_version, package_path))
                else:
                    print("Calling conda build for %s %s" % (python_version, build_arch))
                    code = subprocess.call(['conda', 'build', '--no-binstar-upload', '--python', python_version,
                                            recipe_dir])
                    if code != 0:
                        raise Exception("Failed to build for python version " + python_version)
                    if not os.path.isfile(package_path):
                        try:
                            print("files that DO exist: " + repr(os.listdir(os.path.basename(package_path))))
                        except Exception as e:
                            print(" (failed to list files that do exist, %s)" % str(e))
                        raise Exception("conda said it would build %s but it didn't" % package_path)

                _safe_makedirs(os.path.dirname(final_package_path))
                print("Copying %s to %s" % (package_path, final_package_path))
                shutil.copyfile(package_path, final_package_path)
                print("Created %s" % final_package_path)

            for arch in ('osx-64', 'linux-32', 'win-32', 'win-64'):
                if arch == build_arch:
                    continue
                converted_output_dir = os.path.join(python_scoped_package_dir)
                converted_package_path = os.path.join(converted_output_dir, arch, os.path.basename(package_path))
                if os.path.isfile(converted_package_path):
                    print("Already converted to %s from %s for python %s" % (arch, build_arch, python_version))
                else:
                    print("Creating %s by conversion %s=>%s" % (converted_package_path, build_arch, arch))
                    _safe_makedirs(converted_output_dir)
                    # this automatically creates the "arch" directory to put the package in
                    code = subprocess.call(['conda', 'convert', '--platform', arch, final_package_path, '--output-dir',
                                            converted_output_dir])
                    if code != 0:
                        raise Exception("Failed to convert from %s to %s to create %s" %
                                        (build_arch, arch, converted_package_path))
                    all_final_package_paths.append(converted_package_path)

        print("Packages in " + self.packages_dir)


setup(name='anaconda-project',
      version=VERSION,
      author="Continuum Analytics",
      author_email='info@continuum.io',
      url='http://github.com/Anaconda-Server/anaconda-project',
      description='Library to load and manipulate project directories',
      license='New BSD',
      zip_safe=False,
      install_requires=REQUIRES,
      tests_require=TEST_REQUIRES,
      cmdclass=dict(test=AllTestsCommand,
                    conda_package=CondaPackageCommand,
                    version_module=VersionModuleCommand),
      scripts=[
          'bin/anaconda-project'
      ],
      packages=[
          'anaconda_project', 'anaconda_project.internal', 'anaconda_project.commands', 'anaconda_project.plugins',
          'anaconda_project.plugins.providers', 'anaconda_project.plugins.requirements'
      ])
