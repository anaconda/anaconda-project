# -*- coding: utf-8 -*-
"""Setup script."""

from __future__ import print_function

import errno
import os
import platform
import shutil
import sys
import uuid
from os.path import dirname, realpath
from distutils.core import setup
from setuptools.command.test import test as TestCommand

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

TEST_REQUIRES = ['coverage', 'flake8', 'pep257', 'pytest', 'pytest-cov', 'yapf']

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
    import codecs
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


class AllTestsCommand(TestCommand):
    # `py.test --durations=5` == `python setup.py test -a "--durations=5"`
    user_options = [('pytest-args=', 'a', "Arguments to pass to py.test")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        # -rw turns on printing warnings. To see stack trace from
        # KeyboardInterrupt, add --fulltrace but it also makes the
        # traces huge by showing source code for each frame, so not
        # adding it by default.
        # To see stdout "live" instead of capturing it, use -s.
        coverage_args = ['--cov-config', os.path.join(ROOT, ".coveragerc"), '--cov=project',
                         '--cov-report=term-missing', '--cov-report=html']
        self.pytest_args = ['-v', '-rw', '--durations=10']
        # 100% coverage on Windows requires us to do extra mocks because generally Windows
        # can't run all the servers, such as redis-server. So we relax the coverage requirement
        # for Windows only.
        if platform.system() != 'Windows':
            self.pytest_args = self.pytest_args + coverage_args
        self.pyfiles = None
        self.failed = []

    def _py_files(self):
        if self.pyfiles is None:
            pyfiles = []
            for root, dirs, files in os.walk(ROOT):
                # chop out hidden directories
                files = [f for f in files if not f[0] == '.']
                dirs[:] = [d for d in dirs if (d[0] != '.' and d != 'build')]
                # now walk files
                for f in files:
                    if f.endswith(".py"):
                        pyfiles.append(os.path.join(root, f))
            self.pyfiles = pyfiles
        return self.pyfiles

    def _add_missing_init_py(self):
        root_modules = ['project']
        for srcdir in root_modules:
            for root, dirs, files in os.walk(os.path.join(ROOT, srcdir)):
                dirs[:] = [d for d in dirs if not (d[0] == '.' or d == '__pycache__')]
                for d in dirs:
                    init_py = os.path.join(root, d, "__init__.py")
                    if not os.path.exists(init_py):
                        import codecs
                        print("Creating " + init_py)
                        with codecs.open(init_py, 'w', 'utf-8') as handle:
                            handle.flush()

    def _format_file(self, path):
        import platform
        import codecs
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
        for pyfile in self._py_files():
            self._format_file(pyfile)

    def _flake8(self):
        from flake8.engine import get_style_guide
        flake8_style = get_style_guide(paths=self._py_files(),
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
            sys.argv = ['pep257', os.path.join(ROOT, 'project')]
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
        self._add_missing_init_py()
        self._yapf()
        self._flake8()
        self._pytest()
        self._pep257()
        if len(self.failed) > 0:
            print("Failures in: " + repr(self.failed))
            sys.exit(1)
        else:
            import platform
            if platform.system() == 'Windows':
                # windows console defaults to crap encoding so they get no flair
                print("All tests passed!")
            else:
                print("All tests passed! 💯 🌟")


setup(name='conda-project-prototype',
      version="0.1",
      author="Continuum Analytics",
      author_email='info@continuum.io',
      url='http://github.com/Anaconda-Server/conda-project',
      description='Project support for Anaconda',
      license='New BSD',
      zip_safe=False,
      install_requires=REQUIRES,
      tests_require=TEST_REQUIRES,
      cmdclass=dict(test=AllTestsCommand),
      scripts=[
          'bin/anaconda-project'
      ],
      packages=[
          'project', 'project.internal'
      ])
