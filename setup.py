"""Setup script."""

from __future__ import print_function

import os, sys
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
REQUIRES = ['ruamel.yaml >= ' + RUAMEL_VERSION]

TEST_REQUIRES = ['coverage', 'flake8', 'pep257', 'pytest', 'pytest-cov', 'yapf']


def _atomic_replace(path, contents, encoding):
    import codecs

    tmp = path + ".tmp"
    try:
        with codecs.open(tmp, 'w', encoding) as file:
            file.write(contents)
            file.flush()
            file.close()
        # on windows this may not work, we will see
        os.rename(tmp, path)
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
        # -rw turns on printing warnings
        self.pytest_args = ['-v', '-rw', '--cov-config', os.path.join(ROOT, ".coveragerc"), '--cov=project',
                            '--cov-report=term-missing', '--cov-report=html']
        self.pyfiles = None
        self.failed = []

    def _py_files(self):
        if self.pyfiles is None:
            pyfiles = []
            for root, dirs, files in os.walk(ROOT):
                # chop out hidden directories
                files = [f for f in files if not f[0] == '.']
                dirs[:] = [d for d in dirs if not d[0] == '.']
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
        except Exception as e:
            error = "yapf crashed on {path}: {error}".format(path=path, error=e)
            print(error, file=sys.stderr)
            self.failed.append(error)
            return

        if changed:
            _atomic_replace(path, contents, encoding)
            print("Reformatted:     " + path)
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
        errno = pytest.main(self.pytest_args)
        if errno != 0:
            print("pytest failed, code {errno}".format(errno=errno))
            self.failed.append('pytest')

    def run_tests(self):
        self._add_missing_init_py()
        self._yapf()
        self._flake8()
        self._pytest()
        self._pep257()
        if len(self.failed) > 0:
            print("Failures in: " + repr(self.failed))
            sys.exit(1)

setup(
    name='conda-project-prototype',
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
    ],
    packages=[
        'project',
        'project.internal'
    ]
)
