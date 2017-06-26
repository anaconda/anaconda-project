# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2017, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Code Runner."""

# NOTE: This code is inspired on the bokeh.application code runner.
# Source: https://github.com/bokeh/bokeh/blob/a97e615c039a8813ae651d9276586766a6eb5553/bokeh/application/handlers/code_runner.py # flake8: noqa

from __future__ import absolute_import, print_function

from types import ModuleType
import os
import sys
import traceback
import ast


class CodeRunner(object):
    """Compile and run a Python source code."""

    def __init__(self, source, path, argv=None):
        if argv is None:
            argv = []
        self._failed = False
        self._error = None
        self._error_detail = None

        self._code = None

        try:
            nodes = ast.parse(source, path)
            self._code = compile(nodes, filename=path, mode='exec', dont_inherit=True)
        except SyntaxError as e:
            self._failed = True
            self._error = ("Invalid syntax in \"%s\" on line %d:\n%s" %
                           (os.path.basename(e.filename), e.lineno, e.text))
            import traceback
            self._error_detail = traceback.format_exc()

        self._path = path
        self._source = source
        self._argv = argv
        self.ran = False

    @property
    def source(self):
        """Return the plugin source code."""
        return self._source

    @property
    def path(self):
        """Return the plugin file path."""
        return self._path

    @property
    def failed(self):
        """True if the handler failed to modify the doc."""
        return self._failed

    @property
    def error(self):
        """Error message if the handler failed."""
        return self._error

    @property
    def error_detail(self):
        """Traceback or other details if the handler failed."""
        return self._error_detail

    def new_module(self, name):
        """Make a fresh module to run in."""
        if self.failed:
            return None

        module = ModuleType(name)
        module.__dict__['__file__'] = os.path.abspath(self._path)

        return module

    def run(self, module, post_check=None):
        # TODO(fpliger): should we raise an error or maybe log something
        #                when trying to run a source that failed already?
        if not self._failed:
            try:
                # Simulate the sys.path behaviour decribed here:
                #
                # https://docs.python.org/2/library/sys.html#sys.path
                _cwd = os.getcwd()
                _sys_path = list(sys.path)
                _sys_argv = list(sys.argv)
                sys.path.insert(0, os.path.dirname(self._path))
                sys.argv = [os.path.basename(self._path)] + self._argv

                exec (self._code, module.__dict__)
                if callable(post_check):
                    post_check()

            except Exception as e:
                self._failed = True
                self._error_detail = traceback.format_exc()

                exc_type, exc_value, exc_traceback = sys.exc_info()
                filename, line_number, func, txt = traceback.extract_tb(exc_traceback)[-1]

                self._error = "%s\nFile \"%s\", line %d, in %s:\n%s" % (str(e), os.path.basename(filename), line_number,
                                                                        func, txt)

            finally:
                # undo sys.path, CWD fixups
                os.chdir(_cwd)
                sys.path = _sys_path
                sys.argv = _sys_argv
                self.ran = True
