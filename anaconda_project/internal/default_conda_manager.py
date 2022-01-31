# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Abstract high-level interface to Conda."""
from __future__ import absolute_import

import codecs
import glob
import os
import shutil
import subprocess

from anaconda_project.conda_manager import (CondaManager, CondaEnvironmentDeviations, CondaLockSet, CondaManagerError)
import anaconda_project.internal.conda_api as conda_api
import anaconda_project.internal.pip_api as pip_api
import anaconda_project.internal.makedirs as makedirs

from anaconda_project import __version__ as version


def _refactor_common_packages(existing_sets, include_predicate, factored_name):
    # For items in existing_sets included by include_predicate,
    # try to factor out common items into factored_name.
    # include_predicate takes keys from existing_sets as param.
    factorable_names = [name for name in existing_sets.keys() if include_predicate(name)]
    unfactorable_names = [name for name in existing_sets.keys() if not include_predicate(name)]

    if len(factorable_names) < 2:
        # need at least two things to have a DRY problem; we want to
        # keep things specific unless there's a reason to refactor.
        return existing_sets

    specs = [existing_sets[name] for name in factorable_names]
    factored = set.intersection(*specs)

    if len(factored) == 0:
        # nothing in common amongst relevant things
        return existing_sets

    result = dict()
    for name in factorable_names:
        remaining = existing_sets[name] - factored
        if len(remaining) > 0:
            result[name] = remaining

    for name in unfactorable_names:
        result[name] = existing_sets[name]

    result[factored_name] = factored

    return result


def _extract_common(by_platform):
    # convert from dict of platform-to-lists to platform-to-sets
    result = {name: set(values) for (name, values) in by_platform.items()}

    # linux-64,linux-32 => linux, etc.
    platform_names = set([conda_api.parse_platform(platform)[0] for platform in by_platform.keys()])
    for name in platform_names:
        result = _refactor_common_packages(result, lambda p: p.startswith("%s-" % name), name)

    # is it a candidate for the "unix" grouping
    def is_unix(platform_or_platform_name):
        for unix_name in conda_api.unix_platform_names:
            if platform_or_platform_name.startswith(unix_name):
                return True
        return False

    # if we have "linux","linux-64","osx-64", we should consider "linux","osx-64"
    # and leave out "linux-64".
    def is_most_general(platform_or_platform_name):
        if '-' in platform_or_platform_name:
            platform_name = conda_api.parse_platform(platform_or_platform_name)[0]
            if platform_name in result:
                return False

        if 'unix' in result and is_unix(platform_or_platform_name) and platform_or_platform_name != 'unix':
            return False

        # we don't call this after adding 'all'
        assert platform_or_platform_name != 'all'

        return True

    # linux*, osx* => unix
    result = _refactor_common_packages(result, lambda p: is_unix(p) and is_most_general(p), "unix")

    # everything => all
    result = _refactor_common_packages(result, lambda p: is_most_general(p), "all")

    return {name: sorted(list(value)) for (name, value) in result.items()}


class DefaultCondaManager(CondaManager):
    def __init__(self, frontend):
        """The default Conda manager."""
        self._frontend = frontend

    def _log_info(self, line):
        if self._frontend is not None:
            self._frontend.info(line)

    # uncomment this if you want to use it, not used for now.
    # def _log_error(self, line):
    #     if self._frontend is not None:
    #         self._frontend.error(line)

    def _on_stdout(self, data):
        if self._frontend is not None:
            self._frontend.partial_info(data)

    def _on_stderr(self, data):
        if self._frontend is not None:
            self._frontend.partial_error(data)

    def _cache_directory(self, prefix):
        return os.path.join(prefix, "var", "cache", "anaconda-project")

    def _test_writable_file(self, prefix):
        return os.path.join(self._cache_directory(prefix), "status")

    def _force_readonly_file(self, prefix, parent=False):
        if parent:
            prefix = os.path.dirname(prefix)
        return os.path.join(prefix, '.readonly')

    def _timestamp_file(self, prefix, spec):
        return os.path.join(self._cache_directory(prefix), "env-specs", spec.locked_hash)

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

    def _write_a_file(self, filename):
        try:
            makedirs.makedirs_ok_if_exists(os.path.dirname(filename))
            with codecs.open(filename, 'w', encoding='utf-8') as f:
                # we don't read the contents of the file for now, but
                # recording the version in it in case in the future
                # that is useful. We need to write something to the
                # file to bump its mtime if it already exists...
                f.write('{"anaconda_project_version": "%s"}\n' % version)
            return True
        except (IOError, OSError):
            # ignore errors because this is just an optimization, if we
            # fail we will survive
            return False

    def _is_environment_writable(self, prefix):
        if (os.path.exists(self._force_readonly_file(prefix))
                or os.path.exists(self._force_readonly_file(prefix, parent=True))):
            return False
        filename = self._test_writable_file(prefix)
        return self._write_a_file(filename)

    def _write_timestamp_file(self, prefix, spec):
        filename = self._timestamp_file(prefix, spec)
        if self._write_a_file(filename):
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

    def resolve_dependencies(self, package_specs, channels, platforms):
        by_platform = {}

        current = conda_api.current_platform()
        resolve_for_platforms = list(platforms)
        # always resolve "current" first because it's confusing if
        # an error says resolution failed on another platform when
        # the real issue is that resolution will fail on all platforms.
        if current in resolve_for_platforms:
            resolve_for_platforms.remove(current)
            resolve_for_platforms = [current] + resolve_for_platforms
        for conda_platform in resolve_for_platforms:
            try:
                self._log_info("Resolving conda packages for %s" % conda_platform)
                deps = conda_api.resolve_dependencies(pkgs=package_specs, platform=conda_platform, channels=channels)
            except conda_api.CondaError as e:
                raise CondaManagerError("Error resolving for {}: {}".format(conda_platform, str(e)))
            locked_specs = ["%s=%s=%s" % dep for dep in deps]
            by_platform[conda_platform] = sorted(locked_specs)

        by_platform = _extract_common(by_platform)

        lock_set = CondaLockSet(package_specs_by_platform=by_platform, platforms=resolve_for_platforms)
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

                def version_match(wanted, installed):
                    if wanted == installed:
                        return True
                    else:
                        return installed.startswith(wanted + ".")

                # The only constraint we are smart enough to understand is
                # the one we put in the lock file, which is plain =.
                # We can't do version comparisons, which is a bug.
                # We won't notice if non-= constraints are unmet.
                (_, installed_version, installed_build) = installed[name]
                if spec.exact_version is not None and not version_match(spec.exact_version, installed_version):
                    wrong_version.add(name)
                elif spec.exact_build_string is not None and not version_match(spec.exact_build_string,
                                                                               installed_build):
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

    def _broken_lock_set_error(self, spec):
        error = None
        if spec.lock_set is not None and spec.lock_set.enabled:
            # We have to check this first, because getting our package list
            # is not valid if we don't have platform support.
            current_platform = conda_api.current_platform()
            if current_platform not in spec.platforms:
                error = "Env spec '%s' does not support current platform %s (it supports: %s)" % \
                        (spec.name, current_platform, ", ".join(spec.platforms))
            elif not spec.lock_set.supports_current_platform:
                error = "Env spec '%s' does not have the current platform %s in the lock file" % \
                        (spec.name, current_platform)
        return error

    def find_environment_deviations(self, prefix, spec):
        broken_lock_set = self._broken_lock_set_error(spec)
        if broken_lock_set is not None:
            return CondaEnvironmentDeviations(summary=broken_lock_set,
                                              missing_packages=(),
                                              wrong_version_packages=(),
                                              missing_pip_packages=(),
                                              wrong_version_pip_packages=(),
                                              broken=True,
                                              unfixable=True)

        if not os.path.isdir(os.path.join(prefix, 'conda-meta')):
            return CondaEnvironmentDeviations(summary="'%s' doesn't look like it contains a Conda environment yet." %
                                              (prefix),
                                              missing_packages=tuple(spec.conda_package_names_for_create_set),
                                              wrong_version_packages=(),
                                              missing_pip_packages=tuple(spec.pip_package_names_for_create_set),
                                              wrong_version_pip_packages=(),
                                              broken=True)

        broken = unfixable = False
        if self._timestamp_file_up_to_date(prefix, spec):
            conda_missing = []
            conda_wrong_version = []
            pip_missing = []
        else:
            (conda_missing, conda_wrong_version) = self._find_conda_deviations(prefix, spec)
            pip_missing = self._find_pip_missing(prefix, spec)
            broken = self._is_environment_writable(prefix)
            # For readonly environments, do not enforce the writing of the timestamp.
            # But mark other deviations as unfixable
            unfixable = not broken and (conda_missing or conda_wrong_version or pip_missing)

        all_missing_string = ", ".join(conda_missing + pip_missing)
        all_wrong_version_string = ", ".join(conda_wrong_version)

        if all_missing_string != "" and all_wrong_version_string != "":
            summary = "Conda environment is missing packages: %s and has wrong versions of: %s" % (
                all_missing_string, all_wrong_version_string)
        elif all_missing_string != "":
            summary = "Conda environment is missing packages: %s" % all_missing_string
        elif all_wrong_version_string != "":
            summary = "Conda environment has wrong versions of: %s" % all_wrong_version_string
        elif broken:
            summary = "Conda environment needs to be marked as up-to-date"
        else:
            summary = "OK"
        if unfixable:
            summary += " and the environment is read-only"
        return CondaEnvironmentDeviations(summary=summary,
                                          missing_packages=conda_missing,
                                          wrong_version_packages=conda_wrong_version,
                                          missing_pip_packages=pip_missing,
                                          wrong_version_pip_packages=(),
                                          broken=broken,
                                          unfixable=unfixable)

    def fix_environment_deviations(self, prefix, spec, deviations=None, create=True):
        if deviations is None:
            deviations = self.find_environment_deviations(prefix, spec)

        if deviations.unfixable:
            raise CondaManagerError("Unable to update environment at %s" % prefix)

        conda_meta = os.path.join(prefix, 'conda-meta')
        packed = os.path.join(conda_meta, '.packed')
        install_pip = True

        if os.path.isdir(conda_meta) and os.path.exists(packed):
            with open(packed) as f:
                packed_arch = f.read().strip()

            matched = packed_arch == conda_api.current_platform()
            if matched:
                if 'win' in conda_api.current_platform():
                    unpack_script = ['python', os.path.join(prefix, 'Scripts', 'conda-unpack-script.py')]

                else:
                    unpack_script = os.path.join(prefix, 'bin', 'conda-unpack')

                try:
                    subprocess.check_call(unpack_script)
                    os.remove(packed)
                    install_pip = False
                except (subprocess.CalledProcessError, OSError) as e:
                    self._log_info('Warning: conda-unpack could not be run: \n{}\n'
                                   'The environment will be recreated.'.format(str(e)))
                    create = True
                    shutil.rmtree(prefix)

            else:
                self._log_info('Warning: The unpacked env does not match the current architecture. '
                               'It will be recreated.')
                create = True
                shutil.rmtree(prefix)

        if os.path.isdir(conda_meta):
            to_update = list(set(deviations.missing_packages + deviations.wrong_version_packages))
            if len(to_update) > 0:
                specs = spec.specs_for_conda_package_names(to_update)
                assert len(specs) == len(to_update)
                spec.apply_pins(prefix, specs)
                try:
                    conda_api.install(prefix=prefix,
                                      pkgs=specs,
                                      channels=spec.channels,
                                      stdout_callback=self._on_stdout,
                                      stderr_callback=self._on_stderr)
                except conda_api.CondaError as e:
                    raise CondaManagerError("Failed to install packages: {}: {}".format(", ".join(specs), str(e)))
                finally:
                    spec.remove_pins(prefix)
        elif create:
            # Create environment from scratch

            command_line_packages = set(spec.conda_packages_for_create)

            try:
                conda_api.create(prefix=prefix,
                                 pkgs=list(command_line_packages),
                                 channels=spec.channels,
                                 stdout_callback=self._on_stdout,
                                 stderr_callback=self._on_stderr)
            except conda_api.CondaError as e:
                raise CondaManagerError("Failed to create environment at %s: %s" % (prefix, str(e)))
        else:
            raise CondaManagerError("Conda environment at %s does not exist" % (prefix))

        # now add pip if needed
        missing = list(deviations.missing_pip_packages)
        if (len(missing) > 0) and install_pip:
            specs = spec.specs_for_pip_package_names(missing)
            assert len(specs) == len(missing)
            try:
                pip_api.install(prefix=prefix,
                                pkgs=specs,
                                stdout_callback=self._on_stdout,
                                stderr_callback=self._on_stderr)
            except pip_api.PipError as e:
                raise CondaManagerError("Failed to install missing pip packages: {}: {}".format(
                    ", ".join(missing), str(e)))

        # write a file to tell us we can short-circuit next time
        self._write_timestamp_file(prefix, spec)

    def remove_packages(self, prefix, packages, pip=False):
        if pip:
            try:
                pip_api.remove(prefix, packages, stdout_callback=self._on_stdout, stderr_callback=self._on_stderr)
            except pip_api.PipError as e:
                raise CondaManagerError('Failed to remove pip packages from {}: {}'.format(prefix, str(e)))
        else:
            try:
                conda_api.remove(prefix, packages, stdout_callback=self._on_stdout, stderr_callback=self._on_stderr)
            except conda_api.CondaError as e:
                raise CondaManagerError("Failed to remove packages from %s: %s" % (prefix, str(e)))
