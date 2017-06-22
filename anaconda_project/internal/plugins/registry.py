# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""The plugin registry (used to locate plugins)."""
from __future__ import absolute_import, print_function

import os

from anaconda_project import verbose
from .code_runner import CodeRunner


class Plugin(object):
    """Plugins base class"""

    def __init__(self, path):
        self.path = path
        self.name = None
        self._source = None
        # initialize plugin preparing it to run. I.e. loading code and making
        # sure the code is ready to be loaded
        self.init_plugin()

        # load the plugin by running the code and making sure that it
        # implements the plugins API requirements
        self.load_plugin()


    def init_plugin(self):
        """Specific plugin logic to be overwritten by customized plugin classes.
        This method should at least init the following attributes:

        - _source

        """
        raise NotImplementedError


    def load_plugin(self):
        """Runs the plugin"""
        self._runner = CodeRunner(self._source, self.path)
        self._runner.run(self.name)


    @property
    def failed(self):
        """Returns if True if the plugin has failed to load, False otherwise

        Returns:

            bool
        """
        return self._runner._failed

    @property
    def error(self):
        """Returns the error occurred when loading the plugin, None otherwise

        Returns:

            str / None (if no error occurred)
        """
        return self._runner._error

    @property
    def error_detail(self):
        """Returns the error defails occurred when loading the plugin,
        None otherwise

        Returns:

            str / None (if no error occurred)
        """
        return self._runner._error_detail

    @property
    def loggers(self):
        """List of activate loggers."""
        return verbose._verbose_loggers


    def log(self, log, level='info'):
        """Logs log to all activate loggers"""
        for logger in self.loggers:
            getattr(logger, level)(log)


    @staticmethod
    def create(path):
        """Return a plugin loaded from path

        Args:
            path (str) : path to a file or directory for creating a Plugin.

        Returns:
            Plugin or None (if creation fails)
        """

        path = os.path.abspath(path)

        if os.path.isdir(path):
            plugin_class = PackagePlugin
        else:
            if path.endswith(".py"):
                plugin_class = ModulePlugin(path)
            else:
                log("Expected a '.py' script, got: '%s'" % path, 'error')


        plugin = plugin_class(path)
        if plugin.failed:
            msg = "Error loading %s:\n\n%s\n%s " % (path, plugin.error, plugin.error_detail)
            log(msg)
            return

        return plugin


class ModulePlugin(Plugin):
    """Module (single file) plugin"""
    def init_plugin(self):
        with open(self.path, 'r') as f:
            self._source = f.read()

        self.name = os.path.basename(self.path).replace('.py', '')


class PackagePlugin(Plugin):
    """Package (directory) plugin"""


class PluginRegistry(object):
    """Scans and manages plugins discoverable in a plugins path list."""

    def __init__(self, search_paths):
        self.search_paths = search_paths


def scan_paths(paths):
    """Return a list of Plugins found on the specified paths

    Args:
        path (seq[str]) : paths to files or directories for registering
            plugins

    Returns:
        list[Plugin]

    """
    plugins = []

    for path in paths:
        plugin = Plugin.create(path)

        if plugin:
            plugins.append(plugin)

    return plugins


def log(msg, level='info'):
    """Logs log to all activate loggers"""
    for logger in verbose._verbose_loggers:
        getattr(logger, level)(msg)