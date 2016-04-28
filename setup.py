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
import uuid
from os.path import dirname, realpath
from distutils.core import setup
from setuptools.command.test import test as TestCommand

VERSION = '0.1'

ROOT = dirname(realpath(__file__))

PY2 = sys.version_info[0] == 2

# ruamel.yaml has a Py3 bug when saving files, fixed in 0.10.14;
# Py2 conda only has 0.10.13.  this hack can go away when
# everything is on 0.10.14 anyway.
if PY2:
    RUAMEL_VERSION = "0.10.13"
else:
    RUAMEL_VERSION = "0.10.14"
REQUIRES = ['beautifulsoup4 >= 4.3', 'ruamel.yaml >= ' + RUAMEL_VERSION, 'tornado >= 4.3', 'pycrypto', 'bcrypt >= 2.0']

TEST_REQUIRES = ['coverage', 'flake8', 'pep257', 'pytest', 'pytest-cov', 'yapf == 0.6.2']

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


def _rename_over_existing(src, dest):
    try:
        # On Windows, this will throw EEXIST, on Linux it won't.
        os.rename(src, dest)
    except IOError as e:
        if e.errno == errno.EEXIST:
            # Clearly this song-and-dance is not in fact atomic,
            # but if something goes wrong putting the new file in
            # place at least the backup file might still be
            # around.
            backup = dest + ".bak-" + str(uuid.uuid4())
            os.rename(dest, backup)
            try:
                os.rename(src, dest)
            except Exception as e:
                os.rename(backup, dest)
                raise e
            finally:
                try:
                    os.remove(backup)
                except Exception as e:
                    pass


def _atomic_replace(path, contents, encoding):
    import uuid

    tmp = path + "tmp-" + str(uuid.uuid4())
    try:
        with codecs.open(tmp, 'w', encoding) as file:
            file.write(contents)
            file.flush()
            file.close()
        _rename_over_existing(tmp, path)
    finally:
        try:
            os.remove(tmp)
        except (IOError, OSError):
            pass


coding_utf8_header = "# -*- coding: utf-8 -*-\n"

copyright_header = """
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
""".lstrip()

copyright_re = re.compile('# *Copyright ')


class AllTestsCommand(TestCommand):
    # `py.test --durations=5` == `python setup.py test -a "--durations=5"`
    user_options = [('pytest-args=', 'a', "Arguments to pass to py.test"),
                    ('format-only', None, "Only run the linters and formatters not the actual tests"),
                    ('git-staged-only', None, "Only run the linters and formatters on files added to the commit")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        # -rw turns on printing warnings. To see stack trace from
        # KeyboardInterrupt, add --fulltrace but it also makes the
        # traces huge by showing source code for each frame, so not
        # adding it by default.
        # To see stdout "live" instead of capturing it, use -s.
        coverage_args = ['--cov-config', os.path.join(ROOT, ".coveragerc"), '--cov=anaconda_project',
                         '--cov-report=term-missing', '--cov-report=html']
        self.pytest_args = ['-v', '-rw', '--durations=10']
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

    def _py_files(self):
        if self.pyfiles is None:
            pyfiles = []
            for root, dirs, files in os.walk(ROOT):
                # chop out hidden directories
                files = [f for f in files if not f[0] == '.']
                dirs[:] = [d for d in dirs if (d[0] != '.' and d != 'build' and d != '__pycache__')]
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

    def _update_version_file(self):
        version_code = (
            '"""Version information."""\n\n' + '# Note: this is a generated file, edit setup.py not here.\n' +
            ('version = "%s"\n' % VERSION))
        content = coding_utf8_header + copyright_header + version_code
        version_py = os.path.join(ROOT, 'anaconda_project', 'version.py')
        old_content = codecs.open(version_py, 'r', 'utf-8').read()
        if old_content != content:
            print("Updating " + version_py)
            _atomic_replace(version_py, content, 'utf-8')
            self.failed.append('version-file-updated')

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

        _atomic_replace(path, contents, 'utf-8')

    def _headers(self):
        print("Checking file headers...")
        for pyfile in self._git_staged_or_all_py_files():
            self._headerize_file(pyfile)

    def _format_file(self, path):
        import platform
        from yapf.yapflib.yapf_api import FormatFile
        config = """{
column_limit : 120
}"""

        try:
            # It might be tempting to use the "inplace" option to
            # FormatFile, but it doesn't do an atomic replace, which
            # is dangerous, so don't use it unless you submit a fix to
            # yapf.
            (contents, encoding, changed) = FormatFile(path, style_config=config)
            if platform.system() == 'Windows':
                # yapf screws up line endings on windows
                with codecs.open(path, 'r', encoding) as file:
                    old_contents = file.read()
                contents = contents.replace("\r\n", "\n")
                if len(old_contents) == 0:
                    # windows yapf seems to force a newline? I dunno
                    contents = ""
                changed = (old_contents != contents)
        except Exception as e:
            error = "yapf crashed on {path}: {error}".format(path=path, error=e)
            print(error, file=sys.stderr)
            self.failed.append(error)
            return

        if changed:
            _atomic_replace(path, contents, encoding)
            print("Reformatted:     " + path)
            # we fail the tests if we reformat anything, because
            # we want CI to complain if a PR didn't run yapf
            if len(self.failed) == 0 or self.failed[-1] != 'yapf':
                self.failed.append("yapf")
        else:
            pass
            # print("No reformatting: " + path)

    def _yapf(self):
        print("Formatting files...")
        for pyfile in self._git_staged_or_all_py_files():
            self._format_file(pyfile)

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
        self._update_version_file()
        self._headers()
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
      cmdclass=dict(test=AllTestsCommand),
      scripts=[
          'bin/anaconda-project'
      ],
      packages=[
          'anaconda_project', 'anaconda_project.internal',
          'anaconda_project.commands', 'anaconda_project.plugins',
          'anaconda_project.plugins.providers',
          'anaconda_project.plugins.requirements'
      ])
