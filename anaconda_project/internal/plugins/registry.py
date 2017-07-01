# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""The plugin registry (used to locate plugins)."""
from __future__ import absolute_import, print_function

import os
from os.path import (isdir, join, exists)

from anaconda_project import verbose
from .code_runner import CodeRunner


class Plugin(object):
    """Plugins base class."""

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

    @staticmethod
    def is_plugin_candidate_path(path):
        """Return True if the path is a potential plugin path"""
        if (isdir(path) and exists(join(path, 'plugin.py'))) or path.endswith('.py'):
            return True
        return False

    @property
    def failed(self):
        """Return if True if the plugin has failed to load, False otherwise.

        Returns:

            bool
        """
        return self._runner._failed

    @property
    def error(self):
        """Return the error occurred when loading the plugin, None otherwise.

        Returns:

            str / None (if no error occurred)
        """
        return self._runner._error

    @property
    def error_detail(self):
        """Return the error defails occurred when loading the plugin.
        None otherwise

        Returns:

            str / None (if no error occurred)
        """
        return self._runner._error_detail

    @property
    def loggers(self):
        """List of activate loggers."""
        return verbose._verbose_loggers

    @property
    def ProjectCommand(self):
        # TODO: we should add a Plugin API validation check on the plugin module we get
        return self._module.ProjectCommand #noqa

    @staticmethod
    def create(path):
        """Return a plugin loaded from path.

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
                plugin_class = ModulePlugin
            else:
                log("Expected a '.py' script, got: '%s'" % path, 'error')

        plugin = plugin_class(path)
        if plugin.failed:
            msg = "Error loading %s:\n\n%s\n%s " % (path, plugin.error, plugin.error_detail)
            log(msg)
            return

        return plugin

    def init_plugin(self):
        """Specific plugin logic to be overwritten by customized plugin classes.
        This method should at least init the following attributes:

        - _source

        """
        raise NotImplementedError

    def load_plugin(self):
        """Run the plugin."""
        self._runner = CodeRunner(self._source, self.path)
        if not self._runner.failed:
            self._module = self._runner.new_module(self.name)
            self._runner.run(self._module)

    def log(self, msg, level='info'):
        """Log log to all activate loggers."""
        for logger in self.loggers:
            getattr(logger, level)(msg)


class ModulePlugin(Plugin):
    """Module (single file) plugin."""

    def init_plugin(self):
        with open(self.path, 'r') as f:
            self._source = f.read()

        self.name = os.path.basename(self.path).replace('.py', '')


class PackagePlugin(Plugin):
    """Package (directory) plugin."""

    def init_plugin(self):
        self._package_path = self.path
        self.name = os.path.basename(self.path)
        self.path = os.path.join(self._package_path, 'plugin.py')

        with open(self.path, 'r') as f:
            self._source = f.read()


class PluginRegistry(object):
    """Scans and manages plugins discoverable in a plugins path list."""

    def __init__(self, search_paths):
        self.search_paths = search_paths


def scan_paths(paths):
    """Return a list of Plugins found on the specified paths.

    Args:
        path (seq[str]) : paths to files or directories for registering
            plugins

    Returns:
        list[Plugin]

    """
    plugins = []

    for path in paths:
        plugins += scan_path(path)

    return plugins


def scan_path(path):
    """Return a list of Plugins found on the specified path.

    Args:
        path (seq[str]) : paths to files or directories for registering
            plugins

    Returns:
        list[Plugin]

    """
    plugins = []
    for plugin_path in os.listdir(path):
        plugin_path = os.path.join(path, plugin_path)
        if Plugin.is_plugin_candidate_path(plugin_path):
            plugin = Plugin.create(plugin_path)

            if plugin:
                plugins.append(plugin)
    return plugins


def log(msg, level='info'):
    """Log msg to all activate loggers."""
    for logger in verbose._verbose_loggers:
        getattr(logger, level)(msg)
