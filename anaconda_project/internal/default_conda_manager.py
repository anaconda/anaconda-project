# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Abstract high-level interface to Conda."""
from __future__ import absolute_import

import codecs
import glob
import json
import os

from anaconda_project.conda_manager import (CondaManager, CondaEnvironmentDeviations, CondaLockSet, CondaManagerError)
import anaconda_project.internal.conda_api as conda_api
import anaconda_project.internal.pip_api as pip_api
import anaconda_project.internal.makedirs as makedirs

from anaconda_project.version import version


def _extract_common(by_platform):
    """Create a new dict with entries combining common specs."""
    # We want to "promote" specs the minimum amount, to avoid
    # saying a package works more generally than we've shown that
    # it does. So if something is common to linux-64 and linux-32, we
    # promote it to "linux" not to "all"; if we only have "osx-64"
    # we don't promote that to "osx"; for something to be in "all"
    # it has to work on two different platform names.

    # Compute for example 'linux' from 'linux-64' and 'linux-32'
    promoted_by_platform_name = {}
    platform_names = set([conda_api.parse_platform(platform)[0] for platform in by_platform.keys()])
    for name in platform_names:
        platforms_with_name = [platform for platform in by_platform.keys() if platform.startswith("%s-" % name)]
        if len(platforms_with_name) > 1:
            specs_with_name = [set(by_platform[platform]) for platform in platforms_with_name]
            to_promote = set.intersection(*specs_with_name)
        else:
            to_promote = set()
        promoted_by_platform_name[name] = to_promote

    # Now compute 'all' for specs common to all platform names
    promoted_to_all = set()
    if len(promoted_by_platform_name) > 1:
        # this has to go back and intersect by_platform because osx-64 for example
        # won't have become osx, so we can't intersect promoted_by_platform_name
        # since not everything common to a fully-qualified name has been promoted
        # to a bits-less name.
        all_specs = [set(specs) for specs in by_platform.values()]
        promoted_to_all = set.intersection(*all_specs)

    # Remove the 'all' from the per-platform
    for (name, specs) in promoted_by_platform_name.items():
        promoted_by_platform_name[name] = specs - promoted_to_all

    # Now build the final result, removing promoted stuff from
    # the full platform names
    replacements = {}
    for (platform, specs) in by_platform.items():
        (platform_name, _) = conda_api.parse_platform(platform)
        promoted_to_name = promoted_by_platform_name.get(platform_name, set())
        # we leave these in original order rather than sorting (should we?)
        new_specs = []
        for spec in specs:
            if not (spec in promoted_to_all or spec in promoted_to_name):
                new_specs.append(spec)
        if len(new_specs) > 0:
            replacements[platform] = new_specs

    for (name, specs) in promoted_by_platform_name.items():
        if len(specs) > 0:
            replacements[name] = sorted(list(specs))

    if len(promoted_to_all) > 0:
        replacements['all'] = sorted(list(promoted_to_all))

    return replacements


class DefaultCondaManager(CondaManager):
    def _timestamp_file(self, prefix, spec):
        return os.path.join(prefix, "var", "cache", "anaconda-project", "env-specs", spec.channels_and_packages_hash)

    def _timestamp_comparison_directories(self, prefix):
        # this is a little bit heuristic; we are trying to detect
        # if any packages are installed or removed. This may need
        # to become more comprehensive.  We don't want to check
        # directories that would change at runtime like /var/run,
        # and we need this to be reasonably fast (so we can't do a
        # full directory walk or something). Remember that on
        # Linux at least a new mtime on a directory means
        # _immediate_ child directory entries were added or
        # removed, changing the files themselves or the files in
        # subdirs will not affect mtime. Windows may be a bit
        # different.

        # Linux
        dirs = list(glob.iglob(os.path.join(prefix, "lib", "python*", "site-packages")))
        dirs.append(os.path.join(prefix, "bin"))
        dirs.append(os.path.join(prefix, "lib"))
        # Windows
        dirs.append(os.path.join(prefix, "Lib", "site-packages"))
        dirs.append(os.path.join(prefix, "Library", "bin"))
        dirs.append(os.path.join(prefix, "Scripts"))
        # conda-meta
        dirs.append(os.path.join(prefix, "conda-meta"))

        return dirs

    def _timestamp_file_up_to_date(self, prefix, spec):
        # The goal here is to return False if 1) the env spec
        # has changed (different hash) or 2) the environment has
        # been modified (e.g. by pip or conda).

        filename = self._timestamp_file(prefix, spec)
        try:
            stamp_mtime = os.path.getmtime(filename)
        except OSError:
            return False

        dirs = self._timestamp_comparison_directories(prefix)

        for d in dirs:
            try:
                d_mtime = os.path.getmtime(d)
            except OSError:
                d_mtime = 0
            # When we write the timestamp, we put it 1s in the
            # future, so we want >= here (if the d_mtime has gone
            # into the future from when we wrote the timestamp,
            # the directory has changed).
            if d_mtime >= stamp_mtime:
                return False

        return True

    def _write_timestamp_file(self, prefix, spec):
        filename = self._timestamp_file(prefix, spec)
        makedirs.makedirs_ok_if_exists(os.path.dirname(filename))

        try:
            with codecs.open(filename, 'w', encoding='utf-8') as f:
                # we don't read the contents of the file for now, but
                # recording the version in it in case in the future
                # that is useful. We need to write something to the
                # file to bump its mtime if it already exists...
                f.write(json.dumps(dict(anaconda_project_version=version)) + "\n")
            # set the timestamp 1s in the future, which guarantees
            # it doesn't have the same mtime as any files in the
            # environment changed by us; if another process
            # changes some files during the current second, then
            # we would not notice those changes. The alternative
            # is that we falsely believe we changed things
            # ourselves. Ultimately clock resolution keeps us from
            # perfection here without some sort of cross-process
            # locking.
            actual_time = os.path.getmtime(filename)
            next_tick_time = actual_time + 1
            os.utime(filename, (next_tick_time, next_tick_time))
        except (IOError, OSError):
            # ignore errors because this is just an optimization, if we
            # fail we will survive
            pass

    def resolve_dependencies(self, package_specs):
        by_platform = {}

        # This has no reason to be a loop now, but it will
        # soon when we do multi-platform resolve
        current = conda_api.current_platform()
        resolve_for_platforms = set((current, ) + conda_api.popular_platforms)
        for conda_platform in resolve_for_platforms:
            try:
                deps = conda_api.resolve_dependencies(pkgs=package_specs, platform=conda_platform)
            except conda_api.CondaError as e:
                raise CondaManagerError("Error resolving for {}: {}".format(conda_platform, str(e)))
            locked_specs = ["%s=%s=%s" % dep for dep in deps]
            by_platform[conda_platform] = sorted(locked_specs)

        by_platform = _extract_common(by_platform)

        lock_set = CondaLockSet(package_specs_by_platform=by_platform)
        return lock_set

    def _find_conda_deviations(self, prefix, env_spec):
        try:
            installed = conda_api.installed(prefix)
        except conda_api.CondaError as e:
            raise CondaManagerError("Conda failed while listing installed packages in %s: %s" % (prefix, str(e)))

        missing = set()
        wrong_version = set()

        for spec_string in env_spec.conda_packages_for_create:
            spec = conda_api.parse_spec(spec_string)
            name = spec.name

            if name not in installed:
                missing.add(name)
            else:
                # The only constraint we are smart enough to understand is
                # the one we put in the lock file, which is plain =.
                # We can't do version comparisons, which is a bug.
                # We won't notice if non-= constraints are unmet.
                (_, installed_version, installed_build) = installed[name]
                if spec.exact_version is not None and spec.exact_version != installed_version:
                    wrong_version.add(name)
                elif spec.exact_build_string is not None and spec.exact_build_string != installed_build:
                    wrong_version.add(name)

        return (sorted(list(missing)), sorted(list(wrong_version)))

    def _find_pip_missing(self, prefix, spec):
        # this is an important optimization to avoid a slow "pip
        # list" operation if the project has no pip packages
        if len(spec.pip_package_names_set) == 0:
            return []

        try:
            installed = pip_api.installed(prefix)
        except pip_api.PipError as e:
            raise CondaManagerError("pip failed while listing installed packages in %s: %s" % (prefix, str(e)))

        # TODO: we don't verify that the environment contains the right versions
        # https://github.com/Anaconda-Server/anaconda-project/issues/77

        missing = set()

        for name in spec.pip_package_names_set:
            if name not in installed:
                missing.add(name)

        return sorted(list(missing))

    def find_environment_deviations(self, prefix, spec):
        if not os.path.isdir(os.path.join(prefix, 'conda-meta')):
            return CondaEnvironmentDeviations(
                summary="'%s' doesn't look like it contains a Conda environment yet." % (prefix),
                missing_packages=tuple(spec.conda_package_names_set),
                wrong_version_packages=(),
                missing_pip_packages=tuple(spec.pip_package_names_set),
                wrong_version_pip_packages=(),
                broken=True)

        if self._timestamp_file_up_to_date(prefix, spec):
            conda_missing = []
            conda_wrong_version = []
            pip_missing = []
            timestamp_ok = True
        else:

            (conda_missing, conda_wrong_version) = self._find_conda_deviations(prefix, spec)
            pip_missing = self._find_pip_missing(prefix, spec)
            timestamp_ok = False

        all_missing_string = ", ".join(conda_missing + pip_missing)
        all_wrong_version_string = ", ".join(conda_wrong_version)

        if all_missing_string != "" and all_wrong_version_string != "":
            summary = "Conda environment is missing packages: %s and has wrong versions of: %s" % (
                all_missing_string, all_wrong_version_string)
        elif all_missing_string != "":
            summary = "Conda environment is missing packages: %s" % all_missing_string
        elif all_wrong_version_string != "":
            summary = "Conda environment has wrong versions of: %s" % all_wrong_version_string
        elif not timestamp_ok:
            summary = "Conda environment needs to be marked as up-to-date"
        else:
            summary = "OK"
        return CondaEnvironmentDeviations(summary=summary,
                                          missing_packages=conda_missing,
                                          wrong_version_packages=conda_wrong_version,
                                          missing_pip_packages=pip_missing,
                                          wrong_version_pip_packages=(),
                                          broken=(not timestamp_ok))

    def fix_environment_deviations(self, prefix, spec, deviations=None, create=True):
        if deviations is None:
            deviations = self.find_environment_deviations(prefix, spec)

        if os.path.isdir(os.path.join(prefix, 'conda-meta')):
            to_update = list(set(deviations.missing_packages + deviations.wrong_version_packages))
            if len(to_update) > 0:
                specs = spec.specs_for_conda_package_names(to_update)
                assert len(specs) == len(to_update)
                try:
                    conda_api.install(prefix=prefix, pkgs=specs, channels=spec.channels)
                except conda_api.CondaError as e:
                    raise CondaManagerError("Failed to install packages: {}: {}".format(", ".join(specs), str(e)))
        elif create:
            # Create environment from scratch

            command_line_packages = set(spec.conda_packages_for_create)
            # conda won't let us create a completely empty environment
            if len(command_line_packages) == 0:
                command_line_packages = set(['python'])

            try:
                conda_api.create(prefix=prefix, pkgs=list(command_line_packages), channels=spec.channels)
            except conda_api.CondaError as e:
                raise CondaManagerError("Failed to create environment at %s: %s" % (prefix, str(e)))
        else:
            raise CondaManagerError("Conda environment at %s does not exist" % (prefix))

        # now add pip if needed
        missing = list(deviations.missing_pip_packages)
        if len(missing) > 0:
            specs = spec.specs_for_pip_package_names(missing)
            assert len(specs) == len(missing)
            try:
                pip_api.install(prefix=prefix, pkgs=specs)
            except pip_api.PipError as e:
                raise CondaManagerError("Failed to install missing pip packages: {}: {}".format(", ".join(missing), str(
                    e)))

        # write a file to tell us we can short-circuit next time
        self._write_timestamp_file(prefix, spec)

    def remove_packages(self, prefix, packages):
        try:
            conda_api.remove(prefix, packages)
        except conda_api.CondaError as e:
            raise CondaManagerError("Failed to remove packages from %s: %s" % (prefix, str(e)))
