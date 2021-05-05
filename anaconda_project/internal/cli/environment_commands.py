# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Commands related to the environments section."""
from __future__ import absolute_import, print_function

import sys
import platform
from os import execv
from os.path import join, exists

from anaconda_project.internal.cli.project_load import load_project
from anaconda_project import project_ops
from anaconda_project.internal.cli import console_utils
from anaconda_project.internal import conda_api


def _handle_status(status, success_message=None):
    if status:
        print(status.status_description)
        if success_message is not None:
            print(success_message)
        return 0
    else:
        console_utils.print_status_errors(status)
        return 1


def add_env_spec(project_dir, name, packages, channels):
    """Add an environment with packages from specified channels to the project."""
    project = load_project(project_dir)
    status = project_ops.add_env_spec(project, name=name, packages=packages, channels=channels)
    return _handle_status(status, "Added environment {} to the project file.".format(name))


def remove_env_spec(project_dir, name):
    """Remove an environment with packages from the project."""
    project = load_project(project_dir)
    status = project_ops.remove_env_spec(project, name=name)
    return _handle_status(status, "Removed environment {} from the project file.".format(name))


def export_env_spec(project_dir, name, filename):
    """Save an environment.yml file."""
    project = load_project(project_dir)
    status = project_ops.export_env_spec(project, name=name, filename=filename)
    return _handle_status(status)


def add_packages(project, environment, packages, channels, pip=False):
    """Add packages to the project."""
    project = load_project(project)
    status = project_ops.add_packages(project, env_spec_name=environment, packages=packages, channels=channels, pip=pip)
    package_list = ", ".join(packages)
    if environment is None:
        success_message = "Added packages to project file: %s." % (package_list)
    else:
        success_message = "Added packages to environment %s in project file: %s." % (environment, package_list)
    return _handle_status(status, success_message)


def remove_packages(project, environment, packages, pip):
    """Remove packages from the project."""
    project = load_project(project)
    status = project_ops.remove_packages(project, env_spec_name=environment, packages=packages, pip=pip)
    package_list = ", ".join(packages)
    if environment is None:
        success_message = "Removed packages from project file: %s." % (package_list)
    else:
        success_message = "Removed packages from environment %s in project file: %s." % (environment, package_list)
    return _handle_status(status, success_message)


def add_platforms(project, environment, platforms):
    """Add platforms to the project."""
    project = load_project(project)
    status = project_ops.add_platforms(project, env_spec_name=environment, platforms=platforms)
    package_list = ", ".join(platforms)
    if environment is None:
        success_message = "Added platforms to project file: %s." % (package_list)
    else:
        success_message = "Added platforms to environment %s in project file: %s." % (environment, package_list)
    return _handle_status(status, success_message)


def remove_platforms(project, environment, platforms):
    """Remove platforms from the project."""
    project = load_project(project)
    status = project_ops.remove_platforms(project, env_spec_name=environment, platforms=platforms)
    package_list = ", ".join(platforms)
    if environment is None:
        success_message = "Removed platforms from project file: %s." % (package_list)
    else:
        success_message = "Removed platforms from environment %s in project file: %s." % (environment, package_list)
    return _handle_status(status, success_message)


def list_env_specs(project_dir):
    """List environments in the project."""
    project = load_project(project_dir)
    if console_utils.print_project_problems(project):
        return 1
    print("Environments for project: {}\n".format(project_dir))
    console_utils.print_names_and_descriptions(project.env_specs.values())
    return 0


def list_packages(project_dir, environment):
    """List the packages for an environment in the project."""
    project = load_project(project_dir)
    if console_utils.print_project_problems(project):
        return 1
    if environment is None:
        environment = project.default_env_spec_name
    env = project.env_specs.get(environment, None)
    if env is None:
        print("Project doesn't have an environment called '{}'".format(environment), file=sys.stderr)
        return 1
    print("Conda packages for environment '{}':\n".format(env.name))
    print("\n".join(sorted(env.conda_packages)), end='\n\n')

    if env.pip_packages:
        print("Pip packages for environment '{}':\n".format(env.name))
        print("\n".join(sorted(env.pip_packages)), end='\n\n')

    return 0


def list_platforms(project_dir, environment):
    """List the platforms for an environment in the project."""
    project = load_project(project_dir)
    if console_utils.print_project_problems(project):
        return 1
    if environment is None:
        environment = project.default_env_spec_name
    env = project.env_specs.get(environment, None)
    if env is None:
        print("Project doesn't have an environment called '{}'".format(environment), file=sys.stderr)
        return 1
    print("Platforms for environment '{}':\n".format(env.name))
    print("\n".join(sorted(env.platforms)), end='\n\n')
    return 0


def lock(project_dir, env_spec_name):
    """Lock dependency versions."""
    project = load_project(project_dir)
    if console_utils.print_project_problems(project):
        return 1
    status = project_ops.lock(project, env_spec_name=env_spec_name)
    return _handle_status(status)


def update(project_dir, env_spec_name):
    """Update dependency versions."""
    project = load_project(project_dir)
    if console_utils.print_project_problems(project):
        return 1
    status = project_ops.update(project, env_spec_name=env_spec_name)
    return _handle_status(status)


def unlock(project_dir, env_spec_name):
    """Unlock dependency versions."""
    project = load_project(project_dir)
    if console_utils.print_project_problems(project):
        return 1
    status = project_ops.unlock(project, env_spec_name=env_spec_name)
    return _handle_status(status)


def main_add(args):
    """Start the add-environment command and return exit status code."""
    return add_env_spec(args.directory, args.name, args.packages, args.channel)


def main_remove(args):
    """Start the remove-environment command and return exit status code."""
    return remove_env_spec(args.directory, args.name)


def main_export(args):
    """Start the export env spec command and return exit status code."""
    return export_env_spec(args.directory, args.name, args.filename)


def main_add_packages(args):
    """Start the add-packages command and return exit status code."""
    return add_packages(args.directory, args.env_spec, args.packages, args.channel, args.pip)


def main_remove_packages(args):
    """Start the remove-packages command and return exit status code."""
    return remove_packages(args.directory, args.env_spec, args.packages, args.pip)


def main_add_platforms(args):
    """Start the add-platforms command and return exit status code."""
    return add_platforms(args.directory, args.env_spec, args.platforms)


def main_remove_platforms(args):
    """Start the remove-platforms command and return exit status code."""
    return remove_platforms(args.directory, args.env_spec, args.platforms)


def main_list_env_specs(args):
    """Start the list environments command and return exit status code."""
    return list_env_specs(args.directory)


def main_list_packages(args):
    """Start the list packages command and return exit status code."""
    return list_packages(args.directory, args.env_spec)


def main_list_platforms(args):
    """Start the list platforms command and return exit status code."""
    return list_platforms(args.directory, args.env_spec)


def main_lock(args):
    """Lock dependency versions and return exit status code."""
    return lock(args.directory, args.name)


def main_update(args):
    """Update dependency versions and return exit status code."""
    return update(args.directory, args.name)


def main_unlock(args):
    """Unlock dependency versions and return exit status code."""
    return unlock(args.directory, args.name)


def create_bootstrap_env(project):
    """Create a project bootstrap env, if it doesn't exist.

    Input:
        project(project.Project): project
    """
    if not exists(project.bootstrap_env_prefix):
        env_spec = project.env_specs['bootstrap-env']
        command_line_packages = list(env_spec.conda_packages + env_spec.pip_packages)
        conda_api.create(prefix=project.bootstrap_env_prefix, pkgs=command_line_packages, channels=env_spec.channels)


def run_on_bootstrap_env(project):
    """Run the current command in a project bootstrap env.

    Input:
        project(project.Project): project
    """
    if platform.system() == 'Windows':
        script_dir = "Scripts"
    else:
        script_dir = "bin"

    anaconda_project_exec = join(project.bootstrap_env_prefix, script_dir, 'anaconda-project')
    execv(anaconda_project_exec, sys.argv)
