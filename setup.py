"""Setup script."""

from __future__ import print_function

import os, sys
from os.path import dirname, realpath
from distutils.core import setup, Command
from setuptools.command.test import test as TestCommand

ROOT = dirname(realpath(__file__))

REQUIRES = ['ruamel.yaml >= 0.10.13']

TEST_REQUIRES = ['coverage', 'flake8', 'pytest', 'yapf']


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
        self.pytest_args = []

    def _format_file(self, path):
        from yapf.yapflib.yapf_api import FormatFile

        (contents, encoding, changed) = FormatFile(path)

        if changed:
            _atomic_replace(path, contents, encoding)
            print("Reformatted:     " + path)
        else:
            pass
            #print("No reformatting: " + path)

    def _yapf(self):
        pyfiles = []
        for root, dirs, files in os.walk(ROOT):
            for f in files:
                if f.endswith(".py"):
                    pyfiles.append(os.path.join(root, f))
        for pyfile in pyfiles:
            self._format_file(pyfile)

    def _pytest(self):
        import pytest
        errno = pytest.main(self.pytest_args)
        if errno != 0:
            print("pytest failed, code {errno}".format(errno=errno))
            sys.exit(errno)

    def run_tests(self):
        self._yapf()
        self._pytest()

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
    test_requires=TEST_REQUIRES,
    cmdclass=dict(test=AllTestsCommand),
    scripts=[
    ],
    packages=[
        'project',
        'project.internal'
    ]
)
