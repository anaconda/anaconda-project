"""Setup script."""

from __future__ import print_function

import os, sys
from os.path import dirname, realpath
from distutils.core import setup
from setuptools.command.test import test as TestCommand

ROOT = dirname(realpath(__file__))

REQUIRES = ['ruamel.yaml >= 0.10.13']

TEST_REQUIRES = ['coverage', 'flake8', 'pytest', 'pytest-cov', 'yapf']


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
        self.pytest_args = ['--cov-config', os.path.join(ROOT, ".coveragerc"),
                            '--cov=project', '--cov-report=term-missing',
                            '--cov-report=html']
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

    def _format_file(self, path):
        from yapf.yapflib.yapf_api import FormatFile

        (contents, encoding, changed) = FormatFile(path)

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
        flake8_style = get_style_guide(
            paths=self._py_files(),
            ignore=[
                'E401'  # multiple imports on one line
            ])
        print("running flake8...")
        report = flake8_style.check_files()
        if report.total_errors > 0:
            print(str(report.total_errors) +
                  " flake8 errors, see above to fix them")
            self.failed.append('flake8')
        else:
            print("flake8 passed!")

    def _pytest(self):
        import pytest
        errno = pytest.main(self.pytest_args)
        if errno != 0:
            print("pytest failed, code {errno}".format(errno=errno))
            self.failed.append('pytest')

    def run_tests(self):
        self._yapf()
        self._flake8()
        self._pytest()
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
