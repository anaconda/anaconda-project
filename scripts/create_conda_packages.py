# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Script to automate the creation of conda packages for a release."""

from __future__ import print_function

# Standard library imports
import argparse
import ast
import os
import subprocess
import shutil
import sys

# Constants
HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.dirname(HERE)
PYTHON_VERSIONS = ('2.7', '3.5', '3.6')


def get_version(module='anaconda_project'):
    """Get version."""
    with open(os.path.join(ROOT, module, 'version.py'), 'r') as f:
        data = f.read()
    lines = data.split('\n')
    for line in lines:
        if line.startswith('VERSION_INFO'):
            version_tuple = ast.literal_eval(line.split('=')[-1].strip())
            version = '.'.join(map(str, version_tuple))
            break
    return version


VERSION = get_version()


class CondaPackageCreator:
    "Create Conda packages"

    def __init__(self, packages_dir=None):
        "Create Conda packages"
        self.packages_dir = packages_dir
        self.clean_up()

        if self.packages_dir is None:
            self.packages_dir = os.path.join(ROOT, 'build', 'packages')
        self._safe_makedirs(self.packages_dir)

    def clean_up(self):
        # Clean up leftover trash as best we can
        BUILD_TMP = os.path.join(ROOT, 'build', 'tmp')
        if os.path.isdir(BUILD_TMP):
            print("Cleaning up " + BUILD_TMP)
            try:
                shutil.rmtree(BUILD_TMP, ignore_errors=True)
            except Exception as e:
                print("Failed to remove %s: %s" % (BUILD_TMP, str(e)))
            else:
                print("Done removing " + BUILD_TMP)

    def run(self):
        try:
            self._real_run()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print("setup.py: Failed to build packages: " + str(e), file=sys.stderr)
            sys.exit(1)

    def _real_run(self):
        recipe_dir = os.path.join(ROOT, 'conda.recipe')
        python_versions = PYTHON_VERSIONS
        all_final_package_paths = []
        for python_version in python_versions:
            out = subprocess.check_output(['conda-build', '--output', '--python', python_version, recipe_dir])
            package_path = out.decode('utf-8').strip()
            print("expected conda package path: " + package_path)
            if '--' in package_path:
                # conda build bug?
                print("package_path looks broken, contains -- in it. fixing...")
                package_path = package_path.replace("--", "-%s-" % VERSION)
                print("new conda package path: " + package_path)
            build_arch = os.path.basename(os.path.dirname(package_path))
            python_scoped_package_dir = os.path.join(self.packages_dir, "py%s" % python_version)
            final_package_path = os.path.join(python_scoped_package_dir, build_arch, os.path.basename(package_path))
            all_final_package_paths.append(final_package_path)
            if os.path.isfile(final_package_path):
                print("Package for python %s platform %s already exists: %s" % (python_version, build_arch,
                                                                                final_package_path))
            else:
                if os.path.isfile(package_path):
                    print("Already built for python %s at %s" % (python_version, package_path))
                else:
                    print("Calling conda build for %s %s" % (python_version, build_arch))
                    code = subprocess.call(
                        ['conda', 'build', '--no-binstar-upload', '--python', python_version, recipe_dir])
                    if code != 0:
                        raise Exception("Failed to build for python version " + python_version)
                    if not os.path.isfile(package_path):
                        try:
                            print("files that DO exist: " + repr(os.listdir(os.path.basename(package_path))))
                        except Exception as e:
                            print(" (failed to list files that do exist, %s)" % str(e))
                        raise Exception("conda said it would build %s but it didn't" % package_path)

                self._safe_makedirs(os.path.dirname(final_package_path))
                print("Copying %s to %s" % (package_path, final_package_path))
                shutil.copyfile(package_path, final_package_path)
                print("Created %s" % final_package_path)

            for arch in ('osx-64', 'linux-32', 'linux-64', 'win-32', 'win-64'):
                if arch == build_arch:
                    continue
                converted_output_dir = os.path.join(python_scoped_package_dir)
                converted_package_path = os.path.join(converted_output_dir, arch, os.path.basename(package_path))
                if os.path.isfile(converted_package_path):
                    print("Already converted to %s from %s for python %s" % (arch, build_arch, python_version))
                else:
                    print("Creating %s by conversion %s=>%s" % (converted_package_path, build_arch, arch))
                    self._safe_makedirs(converted_output_dir)
                    # this automatically creates the "arch" directory to put the package in
                    code = subprocess.call([
                        'conda', 'convert', '--platform', arch, final_package_path, '--output-dir', converted_output_dir
                    ])
                    if code != 0:
                        raise Exception(
                            "Failed to convert from %s to %s to create %s" % (build_arch, arch, converted_package_path))
                    all_final_package_paths.append(converted_package_path)

        print("Packages in " + self.packages_dir)

    def _safe_makedirs(self, path):
        try:
            os.makedirs(path)
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser(description='Script to create conda packages for all platforms and '
                                     'python version 2.7, 3.5 and 3.6')
    parser.add_argument(
        action="store", dest="packages_dir", default=None, help="location directory for built packages", nargs='?')

    options = parser.parse_args()
    cpc = CondaPackageCreator(packages_dir=options.packages_dir)
    cpc.run()


if __name__ == '__main__':
    main()
