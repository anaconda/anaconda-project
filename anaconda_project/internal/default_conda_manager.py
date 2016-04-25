# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Abstract high-level interface to Conda."""
from __future__ import absolute_import

import os

from anaconda_project.conda_manager import CondaManager, CondaEnvironmentDeviations, CondaManagerError
import anaconda_project.internal.conda_api as conda_api


class DefaultCondaManager(CondaManager):
    def find_environment_deviations(self, prefix, spec):
        if not os.path.isdir(os.path.join(prefix, 'conda-meta')):
            return CondaEnvironmentDeviations(
                summary="'%s' doesn't look like it contains a Conda environment yet." % (prefix),
                missing_packages=tuple(spec.conda_package_names_set),
                wrong_version_packages=(),
                broken=True)

        try:
            installed = conda_api.installed(prefix)
        except conda_api.CondaError as e:
            raise CondaManagerError("Conda failed while listing installed packages in %s: %s" % (prefix, str(e)))

        # TODO: we don't verify that the environment contains the right versions
        # https://github.com/Anaconda-Server/anaconda-project/issues/77

        missing = set()

        for name in spec.conda_package_names_set:
            if name not in installed:
                missing.add(name)

        if len(missing) > 0:
            sorted = list(missing)
            sorted.sort()
            summary = "Conda environment is missing packages: %s" % (", ".join(sorted))
            return CondaEnvironmentDeviations(summary=summary, missing_packages=sorted, wrong_version_packages=())
        else:
            return CondaEnvironmentDeviations(summary="OK", missing_packages=(), wrong_version_packages=())

    def fix_environment_deviations(self, prefix, spec, deviations=None):
        if deviations is None:
            deviations = self.find_environment_deviations(prefix, spec)

        command_line_packages = set(['python']).union(set(spec.dependencies))

        if os.path.isdir(os.path.join(prefix, 'conda-meta')):
            missing = deviations.missing_packages
            if len(missing) > 0:
                try:
                    # TODO we are ignoring package versions here
                    # https://github.com/Anaconda-Server/anaconda-project/issues/77
                    conda_api.install(prefix=prefix, pkgs=list(missing), channels=spec.channels)
                except conda_api.CondaError as e:
                    raise CondaManagerError("Failed to install missing packages: " + ", ".join(missing))
        else:
            # Create environment from scratch
            try:
                conda_api.create(prefix=prefix, pkgs=list(command_line_packages), channels=spec.channels)
            except conda_api.CondaError as e:
                raise CondaManagerError("Failed to create environment at %s: %s" % (prefix, str(e)))

    def remove_packages(self, prefix, packages):
        try:
            conda_api.remove(prefix, packages)
        except conda_api.CondaError as e:
            raise CondaManagerError("Failed to remove packages from %s: %s" % (prefix, str(e)))
