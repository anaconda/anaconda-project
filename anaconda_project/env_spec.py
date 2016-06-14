# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Environment class representing a conda environment."""
from __future__ import absolute_import

import os

from anaconda_project.internal.conda_api import parse_spec


class EnvSpec(object):
    """Represents a set of required conda packages we could potentially instantiate as a Conda environment."""

    def __init__(self, name, conda_packages, channels, description=None):
        """Construct a package set with the given name and dependencies.

        Args:
            name (str): name of the package set
            conda_packages (list): list of package specs to pass to conda install
            channels (list): list of channel names
            description (str or None): one-sentence-ish summary of what this env is
        """
        self._name = name
        self._conda_packages = tuple(conda_packages)
        self._channels = tuple(channels)
        self._description = description

    @property
    def name(self):
        """Get name of the package set."""
        return self._name

    @property
    def description(self):
        """Get the description of the environment."""
        if self._description is None:
            return self._name
        else:
            return self._description

    @property
    def conda_packages(self):
        """Get the conda packages to install in the environment as an iterable."""
        return self._conda_packages

    @property
    def channels(self):
        """Get the channels to install conda packages from."""
        return self._channels

    @property
    def conda_package_names_set(self):
        """Conda package names that we require, as a Python set."""
        names = set()
        for spec in self.conda_packages:
            names.add(parse_spec(spec).name)
        return names

    def path(self, project_dir):
        """The filesystem path to the default conda env containing our packages."""
        return os.path.join(project_dir, "envs", self.name)
