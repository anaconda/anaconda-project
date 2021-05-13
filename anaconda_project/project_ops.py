# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""High-level operations on a project."""
from __future__ import absolute_import

import contextlib
import os
import shutil
from tempfile import NamedTemporaryFile
try:
    from backports.tempfile import TemporaryDirectory
except ImportError:
    from tempfile import TemporaryDirectory

from anaconda_project.project import Project, ALL_COMMAND_TYPES
from anaconda_project import archiver
from anaconda_project import client
from anaconda_project import prepare
from anaconda_project import provide
from anaconda_project.local_state_file import LocalStateFile
from anaconda_project.frontend import _null_frontend
from anaconda_project.requirements_registry.requirement import EnvVarRequirement
from anaconda_project.requirements_registry.requirements.conda_env import CondaEnvRequirement
from anaconda_project.requirements_registry.requirements.download import DownloadRequirement
from anaconda_project.requirements_registry.requirements.download import _hash_algorithms
from anaconda_project.requirements_registry.requirements.service import ServiceRequirement
from anaconda_project.requirements_registry.providers.conda_env import _remove_env_path
from anaconda_project.internal.simple_status import SimpleStatus
import anaconda_project.conda_manager as conda_manager
from anaconda_project.internal.conda_api import (parse_spec, default_platforms_with_current)
from anaconda_project.internal import conda_api
import anaconda_project.internal.notebook_analyzer as notebook_analyzer
from anaconda_project.internal.py2_compat import is_string, is_dict
from anaconda_project.docker import build_image, DEFAULT_BUILDER_IMAGE


def create(directory_path,
           make_directory=False,
           with_anaconda_package=False,
           name=None,
           icon=None,
           description=None,
           fix_problems=None):
    """Create a project skeleton in the given directory.

    Returns a Project instance even if creation fails or the directory
    doesn't exist, but in those cases the ``problems`` attribute
    of the Project will describe the problem.

    If the anaconda-project.yml already exists, this simply loads it.

    This will not prepare the project (create environments, etc.),
    use the separate prepare calls if you want to do that.

    Args:
        directory_path (str): directory to contain anaconda-project.yml
        make_directory (bool): True to create the directory if it doesn't exist
        with_anaconda_package (bool): True to add the 'anaconda' package
        name (str): Name of the new project or None to leave unset (uses directory name)
        icon (str): Icon for the new project or None to leave unset (uses no icon)
        description (str): Description for the new project or None to leave unset
        fix_problems (bool): True to always fix problems even if project file existed

    Returns:
        a Project instance
    """
    if make_directory and not os.path.exists(directory_path):
        try:
            os.makedirs(directory_path)
        except (IOError, OSError):  # py3=IOError, py2=OSError
            # allow project.problems to report the issue
            pass

    project = Project(directory_path, scan_parents=False)

    if with_anaconda_package:
        project.project_file.set_value('packages', ['anaconda'])
    if name is not None:
        project.project_file.set_value('name', name)
    if icon is not None:
        project.project_file.set_value('icon', icon)
    if description is not None:
        project.project_file.set_value('description', description)

    # dirty the project with the above new values
    project.project_file.use_changes_without_saving()

    # if we're creating anaconda-project.yml, why not auto-fix any problems,
    # such as environment.yaml import. Obtuse to ask since there's
    # no existing anaconda-project.yml to mess up.
    if fix_problems is None:
        fix_problems = not os.path.exists(project.project_file.filename)
    if fix_problems:
        project.fix_problems_and_suggestions()

    if len(project.problems) == 0:
        # write out the anaconda-project.yml; note that this will try to create
        # the directory which we may not want... so only do it if
        # we're problem-free.
        project.project_file.save()

    return project


def _check_problems(project, description=None):
    failed = project.problems_status(description=description)
    if failed is not None:
        for error in failed.errors:
            project.frontend.error(error)
    return failed


def set_properties(project, name=None, icon=None, description=None):
    """Set simple properties on a project.

    This doesn't support properties which require prepare()
    actions to check their effects; see other calls such as
    ``add_packages()`` for those.

    This will fail if project.problems is non-empty.

    Args:
        project (``Project``): the project instance
        name (str): Name of the project or None to leave unmodified
        icon (str): Icon for the project or None to leave unmodified
        description (str): description for the project or None to leave unmodified

    Returns:
        a ``Status`` instance indicating success or failure
    """
    failed = _check_problems(project)
    if failed is not None:
        return failed

    if name is not None:
        project.project_file.set_value('name', name)

    if icon is not None:
        project.project_file.set_value('icon', icon)

    if description is not None:
        project.project_file.set_value('description', description)

    project.project_file.use_changes_without_saving()

    if len(project.problems) == 0:
        # write out the anaconda-project.yml if it looks like we're safe.
        project.project_file.save()
        return SimpleStatus(success=True, description="Project properties updated.")
    else:
        # revert to previous state (after extracting project.problems)
        status = SimpleStatus(success=False,
                              description="Failed to set project properties.",
                              errors=list(project.problems))
        project.project_file.load()
        return status


def _try_requirement_without_commit(project, env_var_or_class, env_spec_name=None):
    project.use_changes_without_saving()

    provide_whitelist = (CondaEnvRequirement, )
    if env_var_or_class not in provide_whitelist:
        provide_whitelist = provide_whitelist + (env_var_or_class, )
    result = prepare.prepare_without_interaction(project,
                                                 provide_whitelist=provide_whitelist,
                                                 env_spec_name=env_spec_name)

    status = result.status_for(env_var_or_class)
    if status is None:
        # I _think_ this is currently impossible, but if it were possible,
        # we'd need to below code and it's hard to prove it's impossible.
        status = _check_problems(project)  # pragma: no cover # no way to cause right now?
        # caller was supposed to expect env_var_or_class to still exist,
        # unless project file got mangled
        assert status is not None  # pragma: no cover

    return status


def _commit_requirement_if_it_works(project, env_var_or_class, env_spec_name):
    status = _try_requirement_without_commit(project, env_var_or_class, env_spec_name)

    if not status:
        # reload from disk, discarding our changes because they did not work
        project.load()
    else:
        # yay!
        project.save()
    return status


def _apply_lock_file_then_revert(project, env_spec_name):
    project.lock_file.use_changes_without_saving()

    result = prepare.prepare_without_interaction(project,
                                                 provide_whitelist=(CondaEnvRequirement, ),
                                                 env_spec_name=env_spec_name)

    status = result.status_for(CondaEnvRequirement)
    if status is None:
        # I _think_ this is currently impossible, but if it were possible,
        # we'd need to below code and it's hard to prove it's impossible.
        status = _check_problems(project)  # pragma: no cover # no way to cause right now?
        # caller was supposed to expect env_var_or_class to still exist,
        # unless project file got mangled
        assert status is not None  # pragma: no cover

    # reload from disk, discarding our changes
    project.lock_file.load()

    return status


def add_download(project, env_spec_name, env_var, url, filename=None, hash_algorithm=None, hash_value=None):
    """Attempt to download the URL; if successful, add it as a download to the project.

    The returned ``Status`` should be a ``RequirementStatus`` for
    the download requirement if it evaluates to True (on success),
    but may be another subtype of ``Status`` on failure. A False
    status will have an ``errors`` property with a list of error
    strings.

    Args:
        project (Project): the project
        env_spec_name (str): environment spec name or None for all environment specs
        env_var (str): env var to store the local filename
        url (str): url to download
        filename (optional, str): Name to give file or directory after downloading
        hash_algorithm (optional, str): Name of the algorithm to use for checksum verification
                                       must be present if hash_value is entered
        hash_value (optional, str): Checksum value to use for verification
                                       must be present if hash_algorithm is entered
    Returns:
        ``Status`` instance
    """
    assert ((hash_algorithm and hash_value) or (hash_algorithm is None and hash_value is None))
    failed = _check_problems(project)
    if failed is not None:
        return failed
    path = _path_to_download(env_spec_name, env_var)
    requirement = project.project_file.get_value(path)
    if requirement is None or not isinstance(requirement, dict):
        requirement = {}
        project.project_file.set_value(path, requirement)

    requirement['url'] = url
    if filename:
        requirement['filename'] = filename

    if hash_algorithm:
        for _hash in _hash_algorithms:
            requirement.pop(_hash, None)
        requirement[hash_algorithm] = hash_value

    return _commit_requirement_if_it_works(project, env_var, env_spec_name=env_spec_name)


def remove_download(project, env_spec_name, env_var, prepare_result=None):
    """Remove file or directory referenced by ``env_var`` from file system and the project.

    The returned ``Status`` will be an instance of ``SimpleStatus``. A False
    status will have an ``errors`` property with a list of error
    strings.

    Args:
        project (Project): the project
        env_spec_name (str): environment spec name or None for all environment specs
        env_var (str): env var to store the local filename
        prepare_result (PrepareResult): result of a previous prepare or None

    Returns:
        ``Status`` instance
    """
    failed = _check_problems(project)

    if failed is not None:
        return failed

    # Modify the project file _in memory only_, do not save
    requirement = project.find_requirements(env_spec_name, env_var, klass=DownloadRequirement)
    if not requirement:
        return SimpleStatus(success=False, description="Download requirement: {} not found.".format(env_var))
    assert len(requirement) == 1  # duplicate env vars aren't allowed
    requirement = requirement[0]

    if prepare_result is None:
        prepare_result = prepare.prepare_without_interaction(project,
                                                             provide_whitelist=(requirement, ),
                                                             env_spec_name=env_spec_name,
                                                             mode=provide.PROVIDE_MODE_CHECK)

    assert env_spec_name is None or prepare_result.env_spec_name == env_spec_name

    status = prepare.unprepare(project, prepare_result, whitelist=[env_var])
    if status:
        project.project_file.unset_value(_path_to_download(env_spec_name, env_var))
        project.project_file.use_changes_without_saving()
        assert project.problems == []
        project.project_file.save()

    return status


# there are lots of builtin ways to do this but they wouldn't keep
# comments properly in ruamel.yaml's CommentedSeq. We don't want to
# copy or wholesale replace "items"
def _filter_inplace(predicate, items):
    i = 0
    while i < len(items):
        if predicate(items[i]):
            i += 1
        else:
            del items[i]


def _map_inplace(f, items):
    i = 0
    while i < len(items):
        items[i] = f(items[i])
        i += 1


class _StatusHolder(object):
    def __init__(self):
        self.status = None


@contextlib.contextmanager
def _updating_project_lock_file(project):
    assert project.problems == []

    old_logical_hashes = dict()
    for env in project.env_specs.values():
        old_logical_hashes[env.name] = env.logical_hash

    status_holder = _StatusHolder()
    yield status_holder

    project.project_file.use_changes_without_saving()

    failed = _check_problems(project)
    if failed is not None:
        status_holder.status = failed
        return

    changed_or_added_envs = []
    for env in project.env_specs.values():
        if old_logical_hashes.get(env.name, None) != env.logical_hash:
            changed_or_added_envs.append(env)

    removed_env_names = []
    for name in old_logical_hashes.keys():
        if name not in project.env_specs:
            removed_env_names.append(name)

    all_env_names = [env_spec.name for env_spec in project.env_specs.values()]
    conda = conda_manager.new_conda_manager(frontend=project.frontend)
    for env in changed_or_added_envs:
        # Update now-obsolete lock set or previously-nonexistent lock set.
        # (Newly-added environments won't have a lock set yet.)
        # An unfortunate side effect is that we update everything to latest
        # versions... ideally we would try to hold constant packages
        # that are unaffected by whatever changes we are making here.
        # But that's sort of involved so let's leave it aside for the time
        # being.
        if env.lock_set.enabled:
            try:
                lock_set = conda.resolve_dependencies(env.conda_packages, env.channels, env.platforms)
                lock_set.env_spec_hash = env.logical_hash
            except conda_manager.CondaManagerError as e:
                status_holder.status = SimpleStatus(success=False,
                                                    description="Error resolving dependencies for %s: %s." %
                                                    (env.name, str(e)))
                return

            project.lock_file._set_lock_set(env.name, lock_set, all_env_names)

    for name in removed_env_names:
        project.lock_file.unset_value(['env_specs', name])

    project.project_file.use_changes_without_saving()

    failed = _check_problems(project)
    if failed is not None:
        # this can only happen if the lockset-updating code above is broken,
        # I think.
        status_holder.status = failed  # pragma: no cover # should not happen


def _update_env_spec(project, name, packages, channels, create, pip=False):
    failed = _check_problems(project)
    if failed is not None:
        return failed

    if packages is None:
        packages = []
    if channels is None:
        channels = []

    if not create and (name is not None):
        if name not in project.env_specs:
            problem = "Environment spec {} doesn't exist.".format(name)
            return SimpleStatus(success=False, description=problem)

    with _updating_project_lock_file(project) as status_holder:

        if name is None:
            env_dict = project.project_file.root
        else:
            env_dict = project.project_file.get_value(['env_specs', name])
            if env_dict is None:
                env_dict = dict()
                # if there's no global platforms list, be sure the new env
                # spec has one.
                if len(project.project_file.get_value(['platforms'], [])) == 0:
                    env_dict['platforms'] = default_platforms_with_current()
                project.project_file.set_value(['env_specs', name], env_dict)

        # packages may be a "CommentedSeq" and we don't want to lose the comments,
        # so don't convert this thing to a regular list.
        old_packages = env_dict.get('packages', [])
        if pip:
            pip_idx = None
            for idx, dep in enumerate(old_packages):
                if is_dict(dep) and list(dep.keys()) == ['pip']:
                    pip_idx = idx
                    break
            if pip_idx is None:
                old_packages_set = set()
            else:
                old_packages_set = set(parse_spec(d).name for d in old_packages[pip_idx].get('pip', []) if is_string(d))
        else:
            old_packages_set = set(parse_spec(dep).name for dep in old_packages if is_string(dep))
        bad_specs = []
        updated_specs = []
        new_specs = []
        for dep in packages:
            if dep in old_packages:
                # no-op adding the EXACT same thing (don't move it around)
                continue
            parsed = parse_spec(dep)
            if parsed is None:
                bad_specs.append(dep)
            else:
                if parsed.name in old_packages_set:
                    updated_specs.append((parsed.name, dep))
                else:
                    new_specs.append(dep)

        if len(bad_specs) > 0:
            bad_specs_string = ", ".join(bad_specs)
            return SimpleStatus(success=False,
                                description="Could not add packages.",
                                errors=[("Bad package specifications: %s." % bad_specs_string)])

        # remove everything that we are changing the spec for
        def replace_spec(old):
            if not is_string(old):
                return old

            name = parse_spec(old).name
            for (replaced_name, new_spec) in updated_specs:
                if replaced_name == name:
                    return new_spec
            return old

        _map_inplace(replace_spec, old_packages)
        # add all the new ones
        if pip:
            if pip_idx is None:
                old_packages.append({'pip': new_specs})
            else:
                old_packages[pip_idx]['pip'].extend(new_specs)
        else:
            old_packages.extend(new_specs)

        env_dict['packages'] = old_packages

        # channels may be a "CommentedSeq" and we don't want to lose the comments,
        # so don't convert this thing to a regular list.
        new_channels = env_dict.get('channels', [])
        old_channels_set = set(new_channels)
        for channel in channels:
            if channel not in old_channels_set:
                new_channels.append(channel)
        env_dict['channels'] = new_channels

    if status_holder.status is None:
        status = _commit_requirement_if_it_works(project, CondaEnvRequirement, env_spec_name=name)
    else:
        project.load()  # revert
        status = status_holder.status

    return status


def add_env_spec(project, name, packages, channels):
    """Attempt to create the environment spec and add it to anaconda-project.yml.

    The returned ``Status`` should be a ``RequirementStatus`` for
    the environment requirement if it evaluates to True (on success),
    but may be another subtype of ``Status`` on failure. A False
    status will have an ``errors`` property with a list of error
    strings.

    Args:
        project (Project): the project
        name (str): environment spec name
        packages (list of str): packages (with optional version info, as for conda install)
        channels (list of str): channels (as they should be passed to conda --channel)

    Returns:
        ``Status`` instance
    """
    assert name is not None
    name = name.strip()
    return _update_env_spec(project, name, packages, channels, create=True)


def remove_env_spec(project, name):
    """Remove the environment spec from project directory and remove from anaconda-project.yml.

    Returns a ``Status`` subtype (it won't be a
    ``RequirementStatus`` as with some other functions, just a
    plain status).

    Args:
        project (Project): the project
        name (str): environment spec name

    Returns:
        ``Status`` instance
    """
    assert name is not None

    failed = _check_problems(project)
    if failed is not None:
        return failed

    if name not in project.env_specs:
        problem = "Environment spec {} doesn't exist.".format(name)
        return SimpleStatus(success=False, description=problem)

    if len(project.env_specs) == 1:
        problem = "At least one environment spec is required; '{}' is the only one left.".format(name)
        return SimpleStatus(success=False, description=problem)

    env_path = project.env_specs[name].path(project.directory_path)

    # For remove_service and remove_download, we use unprepare()
    # to do the cleanup; for the environment, it's awkward to do
    # that because the env we want to remove may not be the one
    # that was prepared. So instead we share some code with the
    # CondaEnvProvider but don't try to go through the unprepare
    # machinery.
    status = _remove_env_path(env_path, project.directory_path)
    if status:
        with _updating_project_lock_file(project) as status_holder:
            project.project_file.unset_value(['env_specs', name])

        if status_holder.status is None:
            assert project.problems == []
            project.save()
        else:
            project.load()  # revert
            status = status_holder.status

    return status


def export_env_spec(project, name, filename):
    """Export the environment spec as an environment.yml-type file.

    Returns a ``Status`` subtype (it won't be a
    ``RequirementStatus`` as with some other functions, just a
    plain status).

    Args:
        project (Project): the project
        name (str): environment spec name or None for default
        filename (str): file to export to

    Returns:
        ``Status`` instance
    """
    failed = _check_problems(project)
    if failed is not None:
        return failed

    if name is None:
        name = project.default_env_spec_name
    assert name is not None

    if name not in project.env_specs:
        problem = "Environment spec {} doesn't exist.".format(name)
        return SimpleStatus(success=False, description=problem)

    spec = project.env_specs[name]

    try:
        spec.save_environment_yml(filename)
    except Exception as e:
        return SimpleStatus(success=False, description="Failed to save {}: {}.".format(filename, str(e)))

    return SimpleStatus(success=True, description="Exported environment spec {} to {}.".format(name, filename))


def add_packages(project, env_spec_name, packages, channels, pip=False):
    """Attempt to install packages then add them to anaconda-project.yml.

    If the env_spec_name is None rather than an env name,
    packages are added in the global packages section (to
    all environment specs).

    The returned ``Status`` should be a ``RequirementStatus`` for
    the environment requirement if it evaluates to True (on success),
    but may be another subtype of ``Status`` on failure. A False
    status will have an ``errors`` property with a list of error
    strings.

    Args:
        project (Project): the project
        env_spec_name (str): environment spec name or None for all environment specs
        packages (list of str): packages (with optional version info, as for conda install)
        channels (list of str): channels (as they should be passed to conda --channel)

    Returns:
        ``Status`` instance
    """
    return _update_env_spec(project, env_spec_name, packages, channels, create=False, pip=pip)


def remove_packages(project, env_spec_name, packages, pip=False):
    """Attempt to remove packages from an environment in anaconda-project.yml.

    If the env_spec_name is None rather than an env name,
    packages are removed from the global packages section
    (from all environments).

    The returned ``Status`` should be a ``RequirementStatus`` for
    the environment requirement if it evaluates to True (on success),
    but may be another subtype of ``Status`` on failure. A False
    status will have an ``errors`` property with a list of error
    strings.

    Args:
        project (Project): the project
        env_spec_name (str): environment spec name or None for all environment specs
        packages (list of str): packages to remove
        pip (bool): Remove packages from pip installed collection if True

    Returns:
        ``Status`` instance
    """
    # This is sort of one big ugly. What we SHOULD be able to do
    # is simply remove the package from anaconda-project.yml then re-run
    # prepare, and if the packages aren't pulled in as deps of
    # something else, they get removed. This would work if our
    # approach was to always force the env to exactly the env
    # we'd have created from scratch, given our env config.
    # But that isn't our approach right now.
    #
    # So what we do right now is remove the package from the env,
    # and then remove it from anaconda-project.yml, and then see if we can
    # still prepare the project.

    # TODO this should handle env spec inheritance in the same way
    # it handles the global packages list, that is, removing a package
    # from a spec should also remove it from its ancestors (and possibly
    # add it to other children of those ancestors).
    # Not doing it at the time of writing this comment because it might
    # be nicer to rewrite this whole thing when we add version pinning
    # anyway.

    failed = _check_problems(project)
    if failed is not None:
        return failed

    assert packages is not None
    assert len(packages) > 0

    if env_spec_name is None:
        envs = project.env_specs.values()
        unaffected_envs = []
    else:
        env = project.env_specs.get(env_spec_name, None)
        if env is None:
            problem = "Environment spec {} doesn't exist.".format(env_spec_name)
            return SimpleStatus(success=False, description=problem)
        else:
            envs = [env]
            unaffected_envs = list(project.env_specs.values())
            unaffected_envs.remove(env)
            assert len(unaffected_envs) == (len(project.env_specs) - 1)

    assert len(envs) > 0

    conda = conda_manager.new_conda_manager(frontend=project.frontend)

    for env in envs:
        prefix = env.path(project.directory_path)
        try:
            if os.path.isdir(prefix):
                conda.remove_packages(prefix, packages, pip=pip)
        except conda_manager.CondaManagerError:
            pass  # ignore errors; not all the envs will exist or have the package installed perhaps

    with _updating_project_lock_file(project) as status_holder:

        def envs_to_their_dicts(envs):
            env_dicts = []
            for env in envs:
                env_dict = project.project_file.get_value(['env_specs', env.name])
                if env_dict is not None:  # it can be None for the default environment (which doesn't have to be listed)
                    env_dicts.append(env_dict)
            return env_dicts

        env_dicts = envs_to_their_dicts(envs)
        env_dicts.append(project.project_file.root)

        unaffected_env_dicts = envs_to_their_dicts(unaffected_envs)

        assert len(env_dicts) > 0

        def _get_deps(env_dict, pip=False):
            _pkgs = env_dict.get('packages', [])
            if pip:
                pip_dicts = [dep for dep in _pkgs if is_dict(dep) and 'pip' in dep]
                assert len(pip_dicts) == 1, 'There should only be one pip: key'
                return pip_dicts[0]['pip']
            else:
                return [dep for dep in _pkgs if is_string(dep)]

        previous_global_deps = set(_get_deps(project.project_file.root, pip=pip))

        for env_dict in env_dicts:
            # packages may be a "CommentedSeq" and we don't want to lose the comments,
            # so don't convert this thing to a regular list.
            old_packages = env_dict.get('packages', [])
            removed_set = set(packages)

            if pip:
                pip_idx = None
                for idx, dep in enumerate(old_packages):
                    if is_dict(dep) and 'pip' in dep:
                        pip_idx = idx

                if pip_idx is None:
                    if len(old_packages):
                        env_dict['packages'].append({'pip': []})
                    else:
                        env_dict['packages'] = [{'pip': []}]
                else:
                    pip_packages = old_packages.pop(pip_idx)['pip']
                    _filter_inplace(lambda dep: not (is_string(dep) and dep in removed_set), pip_packages)
                    env_dict['packages'].append({'pip': pip_packages})
            else:
                _filter_inplace(lambda dep: not (is_string(dep) and dep in removed_set), old_packages)
                env_dict['packages'] = old_packages

        # if we removed any deps from global, add them to the
        # individual envs that were not supposed to be affected.
        new_global_deps = set(_get_deps(project.project_file.root, pip=pip))
        removed_from_global = (previous_global_deps - new_global_deps)
        for env_dict in unaffected_env_dicts:
            # old_packages may be a "CommentedSeq" and we don't want to lose the comments,
            # so don't convert this thing to a regular list.
            old_packages = env_dict.get('packages', [])
            if pip:
                pip_idx = None
                for idx, dep in enumerate(old_packages):
                    if is_dict(dep) and 'pip' in dep:
                        pip_idx = idx
                if pip_idx is None:
                    old_packages.append({'pip': list(removed_from_global)})
                else:
                    old_packages[pip_idx]['pip'].extend(list(removed_from_global))
            else:
                old_packages.extend(list(removed_from_global))
            env_dict['packages'] = old_packages

    if status_holder.status is not None:
        project.load()  # revert
        return status_holder.status

    status = _commit_requirement_if_it_works(project, CondaEnvRequirement, env_spec_name=env_spec_name)

    return status


def _update_and_lock(project, env_spec_name, update):
    failed = _check_problems(project)
    if failed is not None:
        return failed

    if env_spec_name is None:
        envs = sorted(project.env_specs.values(), key=lambda env: env.name)
    else:
        env = project.env_specs.get(env_spec_name, None)
        if env is None:
            problem = "Environment spec {} doesn't exist.".format(env_spec_name)
            return SimpleStatus(success=False, description=problem)
        else:
            envs = [env]

    all_env_names = [env_spec.name for env_spec in project.env_specs.values()]

    need_save = False

    # Set platforms if it hasn't been
    if not update:
        fixed_platforms = False
        no_platforms_specs = [env_spec for env_spec in project.env_specs.values() if len(env_spec.platforms) == 0]

        def all_platforms_string():
            return ", ".join(default_platforms_with_current())

        if len(no_platforms_specs) == len(project.env_specs):
            # if ALL env specs are missing platforms, set global list
            project.project_file.set_value('platforms', default_platforms_with_current())
            fixed_platforms = True
            project.frontend.info("Set project platforms list to %s" % all_platforms_string())
        else:
            # if only some env specs are missing, only modify the ones that are messed up
            # AND that we are planning to update/lock.
            for env in envs:
                if len(env.platforms) == 0:
                    project.project_file.set_value(['env_specs', env.name, 'platforms'],
                                                   default_platforms_with_current())
                    fixed_platforms = True
                    project.frontend.info("Set platforms for %s to %s" % (env.name, all_platforms_string()))

        if fixed_platforms:
            project.use_changes_without_saving()
            # we can't break the file by setting the platforms key, right?
            # at least not unless something is buggy...
            assert not project.problems

            # reload environments
            envs = list(map(lambda spec: project.env_specs[spec.name], envs))

            # we'll save later after doing all the other stuff too
            need_save = True

    conda = conda_manager.new_conda_manager(frontend=project.frontend)

    # note that "envs" are frozen from the original project state,
    # and won't update as we go through them
    for env in envs:
        if update or env.lock_set.disabled or env.lock_set.missing:
            try:
                project.frontend.info("Updating locked dependencies for env spec %s..." % env.name)
                lock_set = conda.resolve_dependencies(env.conda_packages, env.channels, env.platforms)
                lock_set.env_spec_hash = env.logical_hash
            except conda_manager.CondaManagerError as e:
                return SimpleStatus(success=False,
                                    description="Error resolving dependencies for %s: %s." % (env.name, str(e)))

            lock_set_changed = not env.lock_set.equivalent_to(lock_set)
            hash_changed = env.lock_set.env_spec_hash is not None and \
                env.lock_set.env_spec_hash != lock_set.env_spec_hash

            # if lock_set_changed is False, we may still be enabling locking
            if lock_set_changed or not update:
                project.lock_file._set_lock_set(env.name, lock_set, all_env_names)

                if update and env.lock_set.disabled:
                    # If we are doing an update and locking is not
                    # already in use, we should install the new lock
                    # set, but not save it in the lock file.
                    status = _apply_lock_file_then_revert(project, env.name)
                    if status:
                        project.frontend.info("Updated installed dependencies for %s." % (env.name))
                    # we should not have created a lock when there was none
                    assert project.env_specs[env.name].lock_set.disabled
                else:
                    # a lock, or an update when we already have locking enabled,
                    # DOES save in the lock file
                    if lock_set_changed:
                        project.frontend.info("Changes to locked dependencies for %s:" % env.name)
                        diff_string = lock_set.diff_from(env.lock_set)
                        for line in diff_string.split("\n"):
                            project.frontend.info(line)

                    status = _try_requirement_without_commit(project, CondaEnvRequirement, env.name)
                    # Pip packages can only be added to the lock file after
                    # they are installed. Pip does not have a dry-run feature
                    prefix = env.path(project.directory_path)
                    pip_pkgs = conda_api.installed_pip(prefix)
                    if pip_pkgs:
                        project.lock_file._add_pip_packages(env.name, pip_pkgs)

                    if status:
                        need_save = True
                        if update:
                            project.frontend.info("Updated locked dependencies for env spec %s in %s." %
                                                  (env.name, project.lock_file.basename))
                        else:
                            project.frontend.info("Added locked dependencies for env spec %s to %s." %
                                                  (env.name, project.lock_file.basename))

                if not status:
                    # revert our changes
                    project.load()
                    return status
            elif hash_changed:
                assert lock_set.env_spec_hash is not None
                project.lock_file._set_lock_set_hash(env.name, lock_set.env_spec_hash)
                project.frontend.info("Updated hash for env spec %s to %s in %s." %
                                      (env.name, lock_set.env_spec_hash, project.lock_file.basename))
                need_save = True
            else:
                project.frontend.info("Locked dependencies for env spec %s are already up to date." % env.name)
        else:
            assert not update
            project.frontend.info("Env spec %s is already locked." % env.name)

    # everything successful; save the project
    if need_save:
        project.save()

    if update:
        description = "Update complete."
    else:
        description = "Project dependencies are locked."
    return SimpleStatus(success=True, description=description)


def lock(project, env_spec_name):
    """Attempt to freeze dependency versions in anaconda-project-lock.yml.

    If the env_spec_name is None rather than a name,
    all env specs are frozen.

    Args:
        project (Project): the project
        env_spec_name (str): environment spec name or None for all environment specs

    Returns:
        ``Status`` instance
    """
    return _update_and_lock(project, env_spec_name, update=False)


def update(project, env_spec_name):
    """Attempt to update frozen dependency versions in anaconda-project-lock.yml.

    If the env_spec_name is None rather than a name,
    all env specs are updated.

    If an env is not locked, this updates the installed dependencies but
    doesn't change anything about project configuration (does not save
    the lock file).

    Args:
        project (Project): the project
        env_spec_name (str): environment spec name or None for all environment specs

    Returns:
        ``Status`` instance
    """
    return _update_and_lock(project, env_spec_name, update=True)


def unlock(project, env_spec_name):
    """Attempt to unfreeze dependency versions in anaconda-project-lock.yml.

    If the env_spec_name is None rather than a name,
    all env specs are unfrozen.

    Args:
        project (Project): the project
        env_spec_name (str): environment spec name or None for all environment specs

    Returns:
        ``Status`` instance
    """
    failed = _check_problems(project)
    if failed is not None:
        return failed

    if env_spec_name is not None:
        env = project.env_specs.get(env_spec_name, None)
        if env is None:
            problem = "Environment spec {} doesn't exist.".format(env_spec_name)
            return SimpleStatus(success=False, description=problem)

    # if env_spec_name is None this disables locking for ALL env specs
    project.lock_file._disable_locking(env_spec_name)

    status = _commit_requirement_if_it_works(project, CondaEnvRequirement, env_spec_name)

    if status:
        if env_spec_name is None:
            description = "Dependency locking is now disabled."
        else:
            description = "Dependency locking is now disabled for env spec %s." % env_spec_name
        return SimpleStatus(success=True, description=description)
    else:
        return status


def _check_env_spec_name(project, name):
    if name is not None and name not in project.env_specs:
        problem = "Environment spec {} doesn't exist.".format(name)
        return SimpleStatus(success=False, description=problem)
    else:
        return None


# this function is specific to fields that go into the EnvSpec
# (CondaEnvRequirement/lockset-affecting)
def _modify_inherited_field(project, name, field, additions, removals):
    # TODO this is not even as clever as remove_packages, in that
    # it simply removes from either the global or single-env-spec
    # list of platforms, and doesn't try to remove from the global
    # list if you remove from a single env spec that is inheriting
    # the platform from the global. See remove_packages for how
    # it could be smarter, but even remove_packages should be updated
    # to handle inheritance generally, instead of just the global
    # vs. specific lists.

    failed = _check_problems(project)
    if failed is None:
        failed = _check_env_spec_name(project, name)

    if failed is not None:
        return failed

    # field values will be validated when we try out the new
    # project file, we won't save if the result is invalid.

    with _updating_project_lock_file(project) as status_holder:

        if name is None:
            env_dict = project.project_file.root
        else:
            env_dict = project.project_file.get_value(['env_specs', name])
            assert env_dict is not None

        # packages may be a "CommentedSeq" and we don't want to lose the comments,
        # so don't convert this thing to a regular list.
        old_values = env_dict.get(field, [])
        for value in additions:
            if value in old_values:
                # no-op adding the same thing (don't move it around)
                continue
            else:
                old_values.append(value)

        def should_keep(p):
            return not (is_string(p) and p in removals)

        _filter_inplace(should_keep, old_values)

        env_dict[field] = old_values

    if status_holder.status is None:
        status = _commit_requirement_if_it_works(project, CondaEnvRequirement, env_spec_name=name)
    else:
        project.load()  # revert
        status = status_holder.status

    return status


def _modify_platforms(project, name, additions, removals):
    return _modify_inherited_field(project, name, 'platforms', additions, removals)


def add_platforms(project, env_spec_name, platforms):
    """Attempt to add platforms the project supports.

    If the env_spec_name is None rather than an env name,
    packages are added in the global platforms section (to
    all environment specs).

    The returned ``Status`` should be a ``RequirementStatus`` for
    the environment requirement if it evaluates to True (on success),
    but may be another subtype of ``Status`` on failure. A False
    status will have an ``errors`` property with a list of error
    strings.

    Args:
        project (Project): the project
        env_spec_name (str): environment spec name or None for all environment specs
        platforms (list of str): platforms to add

    Returns:
        ``Status`` instance
    """
    return _modify_platforms(project, env_spec_name, additions=platforms, removals=[])


def remove_platforms(project, env_spec_name, platforms):
    """Attempt to remove platforms the project supports.

    If the env_spec_name is None rather than an env name,
    packages are added in the global platforms section (to
    all environment specs).

    The returned ``Status`` should be a ``RequirementStatus`` for
    the environment requirement if it evaluates to True (on success),
    but may be another subtype of ``Status`` on failure. A False
    status will have an ``errors`` property with a list of error
    strings.

    Args:
        project (Project): the project
        env_spec_name (str): environment spec name or None for all environment specs
        platforms (list of str): platforms to remove

    Returns:
        ``Status`` instance
    """
    return _modify_platforms(project, env_spec_name, additions=[], removals=platforms)


def _prepare_env_prefix(project, env_spec_name, prepare_result, mode):
    failed = _check_problems(project)
    if failed is None:
        failed = _check_env_spec_name(project, env_spec_name)
    if failed is not None:
        return (None, failed)

    # we need an env prefix to store in keyring

    env_prefix = None
    if prepare_result is not None:
        env_prefix = prepare_result.env_prefix

    if env_prefix is None:
        result = prepare.prepare_without_interaction(project,
                                                     provide_whitelist=(CondaEnvRequirement, ),
                                                     env_spec_name=env_spec_name,
                                                     mode=mode)
        status = result.status_for(CondaEnvRequirement)
        assert status is not None
        if status:
            env_prefix = result.environ[status.requirement.env_var]
        else:
            # ignore errors if only checking
            if mode == provide.PROVIDE_MODE_CHECK:
                return (None, None)
            else:
                return (None, status)

    return (env_prefix, None)


def _path_to_per_env_spec_thing(env_spec_name, thing_name, varname):
    if env_spec_name is None:
        return [thing_name, varname]
    else:
        return ['env_specs', env_spec_name, thing_name, varname]


def _path_to_variable(env_spec_name, varname):
    return _path_to_per_env_spec_thing(env_spec_name, 'variables', varname)


def _path_to_download(env_spec_name, varname):
    return _path_to_per_env_spec_thing(env_spec_name, 'downloads', varname)


def _path_to_service(env_spec_name, varname):
    return _path_to_per_env_spec_thing(env_spec_name, 'services', varname)


def add_variables(project, env_spec_name, vars_to_add, defaults=None):
    """Add variables in anaconda-project.yml, optionally setting their defaults.

    Returns a ``Status`` instance which evaluates to True on
    success and has an ``errors`` property (with a list of error
    strings) on failure.

    Args:
        project (Project): the project
        env_spec_name (str): environment spec name or None for all environment specs
        vars_to_add (list of str): variable names
        defaults (dict): dictionary from keys to defaults, can be empty

    Returns:
        ``Status`` instance
    """
    failed = _check_problems(project)
    if failed is None:
        failed = _check_env_spec_name(project, env_spec_name)
    if failed is not None:
        return failed

    if defaults is None:
        defaults = dict()

    present_vars = {req.env_var for req in project.requirements(env_spec_name) if isinstance(req, EnvVarRequirement)}
    for varname in vars_to_add:

        path_to_variable = _path_to_variable(env_spec_name, varname)

        if varname in defaults:
            # we need to update the default even if var already exists
            new_default = defaults.get(varname)
            variable_value = project.project_file.get_value(path_to_variable)
            if variable_value is None or not isinstance(variable_value, dict):
                variable_value = new_default
            else:
                variable_value['default'] = new_default
            project.project_file.set_value(path_to_variable, variable_value)
        elif varname not in present_vars:
            # we are only adding the var if nonexistent and should leave
            # the default alone if it's already set
            project.project_file.set_value(path_to_variable, None)
    project.project_file.save()

    return SimpleStatus(success=True, description="Variables added to the project file.")


def _unset_variable(project, env_spec_name, env_prefix, varname, local_state):
    reqs = project.find_requirements(env_spec_name, env_var=varname)
    if len(reqs) > 0:
        req = reqs[0]
        if req.encrypted:
            # import keyring locally because it's an optional dependency
            # that prints a warning when it's needed but not found.
            from anaconda_project.internal import keyring

            keyring.unset(env_prefix, varname)
        else:
            local_state.unset_value(['variables', varname])


def remove_variables(project, env_spec_name, vars_to_remove, prepare_result=None):
    """Remove variables from anaconda-project.yml and unset their values in local project state.

    Returns a ``Status`` instance which evaluates to True on
    success and has an ``errors`` property (with a list of error
    strings) on failure.

    Args:
        project (Project): the project
        env_spec_name (str): environment spec name or None for all environment specs
        vars_to_remove (list of str): variable names
        prepare_result (PrepareResult): result of a previous prepare or None

    Returns:
        ``Status`` instance
    """
    (env_prefix, status) = _prepare_env_prefix(project, env_spec_name, prepare_result, mode=provide.PROVIDE_MODE_CHECK)
    # we allow env_prefix of None, which means the env wasn't created so we won't
    # try to unset any values for the variable.
    if status is not None and not status:
        return status

    local_state = LocalStateFile.load_for_directory(project.directory_path)
    for varname in vars_to_remove:
        path_to_variable = _path_to_variable(env_spec_name, varname)

        if env_prefix is not None:
            _unset_variable(project, env_spec_name, env_prefix, varname, local_state)
        path_to_variable = _path_to_variable(env_spec_name, varname)
        project.project_file.unset_value(path_to_variable)
        project.project_file.save()
        local_state.save()

    return SimpleStatus(success=True, description="Variables removed from the project file.")


def set_variables(project, env_spec_name, vars_and_values, prepare_result=None):
    """Set variables' values in anaconda-project-local.yml.

    Returns a ``Status`` instance which evaluates to True on
    success and has an ``errors`` property (with a list of error
    strings) on failure.

    Args:
        project (Project): the project
        env_spec_name (str): name of env spec to use or None for all
        vars_and_values (list of tuple): key-value pairs
        prepare_result (PrepareResult): result of a previous prepare or None

    Returns:
        ``Status`` instance
    """
    (env_prefix, status) = _prepare_env_prefix(project,
                                               env_spec_name,
                                               prepare_result,
                                               mode=provide.PROVIDE_MODE_DEVELOPMENT)
    if env_prefix is None:
        return status

    local_state = LocalStateFile.load_for_directory(project.directory_path)
    var_reqs = dict()
    for req in project.find_requirements(env_spec_name, klass=EnvVarRequirement):
        var_reqs[req.env_var] = req
    present_vars = set(var_reqs.keys())
    errors = []
    local_state_count = 0
    keyring_count = 0
    for varname, value in vars_and_values:
        if varname in present_vars:
            if var_reqs[varname].encrypted:
                # import keyring locally because it's an optional dependency
                # that prints a warning when it's needed but not found.
                from anaconda_project.internal import keyring

                keyring.set(env_prefix, varname, value)
                keyring_count = keyring_count + 1
            else:
                local_state.set_value(['variables', varname], value)
                local_state_count = local_state_count + 1
        else:
            errors.append("Variable %s does not exist in the project." % varname)

    if errors:
        return SimpleStatus(success=False, description="Could not set variables.", errors=errors)
    else:
        if local_state_count > 0:
            local_state.save()
        if keyring_count == 0:
            description = ("Values saved in %s." % local_state.filename)
        elif local_state_count == 0:
            description = ("Values saved in the system keychain.")
        else:
            description = ("%d values saved in %s, %d values saved in the system keychain." %
                           (local_state_count, local_state.filename, keyring_count))
        return SimpleStatus(success=True, description=description)


def unset_variables(project, env_spec_name, vars_to_unset, prepare_result=None):
    """Unset variables' values in anaconda-project-local.yml.

    Returns a ``Status`` instance which evaluates to True on
    success and has an ``errors`` property (with a list of error
    strings) on failure.

    Args:
        project (Project): the project
        env_spec_name (str): name of env spec to use or None for all
        vars_to_unset (list of str): variable names
        prepare_result (PrepareResult): result of a previous prepare or None

    Returns:
        ``Status`` instance
    """
    (env_prefix, status) = _prepare_env_prefix(project, env_spec_name, prepare_result, mode=provide.PROVIDE_MODE_CHECK)
    if env_prefix is None:
        return status

    local_state = LocalStateFile.load_for_directory(project.directory_path)
    for varname in vars_to_unset:
        _unset_variable(project, env_spec_name, env_prefix, varname, local_state)
    local_state.save()

    return SimpleStatus(success=True, description=("Variables were unset."))


def add_command(project, name, command_type, command, env_spec_name=None, supports_http_options=None):
    """Add a command to anaconda-project.yml.

    Returns a ``Status`` subtype (it won't be a
    ``RequirementStatus`` as with some other functions, just a
    plain status).

    Args:
       project (Project): the project
       name (str): name of the command
       command_type (str): choice of `bokeh_app`, `notebook`, `unix` or `windows` command
       command (str): the command line or filename itself
       env_spec_name (str): env spec to use with this command
       supports_http_options (bool): None for leave it alone, otherwise true or false

    Returns:
       a ``Status`` instance
    """
    if command_type not in ALL_COMMAND_TYPES:
        raise ValueError("Invalid command type " + command_type + " choose from " + repr(ALL_COMMAND_TYPES))

    name = name.strip()

    failed = _check_problems(project)
    if failed is not None:
        return failed

    command_dict = project.project_file.get_value(['commands', name])
    if command_dict is None:
        command_dict = dict()
        project.project_file.set_value(['commands', name], command_dict)

    command_dict[command_type] = command

    if env_spec_name is None:
        if 'env_spec' not in command_dict:
            # make it explicit for clarity
            command_dict['env_spec'] = project.default_env_spec_name
        # if env_spec is set, leave it alone; this way people can
        # modify commands via command line without specifying the
        # env_spec every time.
    else:
        command_dict['env_spec'] = env_spec_name

    if supports_http_options is not None:
        assert isinstance(supports_http_options, bool)
        command_dict['supports_http_options'] = supports_http_options

    if command_type == 'notebook':
        notebook_file = os.path.join(project.directory_path, command)
        errors = []
        # TODO missing notebook should be an error caught before here
        if os.path.isfile(notebook_file):
            extras = notebook_analyzer.extras(notebook_file, errors)
        else:
            extras = {}
        if len(errors) > 0:
            failed = SimpleStatus(success=False, description="Unable to add the command.", errors=errors)
            return failed
        command_dict.update(extras)

    project.project_file.use_changes_without_saving()

    failed = _check_problems(project, description="Unable to add the command.")
    if failed is not None:
        # reset, maybe someone added conflicting command line types or something
        project.project_file.load()
        return failed
    else:
        project.project_file.save()
        return SimpleStatus(success=True, description="Command added to project file.")


def update_command(project, name, command_type=None, command=None, new_name=None):
    """Update attributes of a command in anaconda-project.yml.

    Returns a ``Status`` subtype (it won't be a
    ``RequirementStatus`` as with some other functions, just a
    plain status).

    Args:
       project (Project): the project
       name (str): name of the command
       command_type (str or None): choice of `bokeh_app`, `notebook`, `unix` or `windows` command
       command (str or None): the command line or filename itself; command_type must also be specified

    Returns:
       a ``Status`` instance
    """
    # right now update_command can be called "pointlessly" (with
    # no new command), this is because in theory it might let you
    # update other properties too, when/if commands have more
    # properties.
    if command_type is None and new_name is None:
        return SimpleStatus(success=True, description=("Nothing to change about command %s" % name))

    if command_type not in (list(ALL_COMMAND_TYPES) + [None]):
        raise ValueError("Invalid command type " + command_type + " choose from " + repr(ALL_COMMAND_TYPES))

    if command is None and command_type is not None:
        raise ValueError("If specifying the command_type, must also specify the command")

    failed = _check_problems(project)
    if failed is not None:
        return failed

    if name not in project.commands:
        return SimpleStatus(success=False,
                            description="Failed to update command.",
                            errors=[("No command '%s' found." % name)])

    command_dict = project.project_file.get_value(['commands', name])
    assert command_dict is not None

    if new_name:
        project.project_file.unset_value(['commands', name])
        project.project_file.set_value(['commands', new_name], command_dict)

    existing_types = set(command_dict.keys())
    conflicting_types = existing_types - set([command_type])
    # 'unix' and 'windows' don't conflict with one another
    if command_type == 'unix':
        conflicting_types = conflicting_types - set(['windows'])
    elif command_type == 'windows':
        conflicting_types = conflicting_types - set(['unix'])

    if command_type is not None:
        for conflicting in conflicting_types:
            del command_dict[conflicting]

        command_dict[command_type] = command

    project.project_file.use_changes_without_saving()

    failed = _check_problems(project, description="Unable to add the command.")
    if failed is not None:
        # reset, maybe someone added a nonexistent bokeh app or something
        project.project_file.load()
        return failed
    else:
        project.project_file.save()
        return SimpleStatus(success=True, description="Command updated in project file.")


def remove_command(project, name):
    """Remove a command from anaconda-project.yml.

    Returns a ``Status`` subtype (it won't be a
    ``RequirementStatus`` as with some other functions, just a
    plain status).

    Args:
       project (Project): the project
       name (string): name of the command to be removed

    Returns:
       a ``Status`` instance
    """
    failed = _check_problems(project)
    if failed is not None:
        return failed

    if name not in project.commands:
        return SimpleStatus(success=False, description="Command: '{}' not found in project file.".format(name))

    command = project.commands[name]

    # if we remove a notebook, it's an error normally, we have to mark it skipped
    # TODO share this code with the no_fix function in project.py
    if command.notebook is not None:
        skipped_notebooks = project.project_file.get_value(['skip_imports', 'notebooks'], default=[])
        if isinstance(skipped_notebooks, list) and \
           command.notebook not in skipped_notebooks:
            skipped_notebooks.append(command.notebook)
            project.project_file.set_value(['skip_imports', 'notebooks'], skipped_notebooks)

    project.project_file.unset_value(['commands', name])
    project.project_file.use_changes_without_saving()

    assert project.problems == []
    project.project_file.save()

    return SimpleStatus(success=True, description="Command: '{}' removed from project file.".format(name))


def add_service(project, env_spec_name, service_type, variable_name=None):
    """Add a service to anaconda-project.yml.

    The returned ``Status`` should be a ``RequirementStatus`` for
    the service requirement if it evaluates to True (on success),
    but may be another subtype of ``Status`` on failure. A False
    status will have an ``errors`` property with a list of error
    strings.

    Args:
        project (Project): the project
        env_spec_name (str): environment spec name or None for all environment specs
        service_type (str): which kind of service
        variable_name (str): environment variable name (None for default)

    Returns:
        ``Status`` instance
    """
    failed = _check_problems(project)
    if failed is not None:
        return failed

    known_types = project.plugin_registry.list_service_types()
    found = None
    for known in known_types:
        if known.name == service_type:
            found = known
            break

    if found is None:
        return SimpleStatus(success=False,
                            description="Unable to add service.",
                            errors=[
                                "Unknown service type '%s', we know about: %s" %
                                (service_type, ", ".join(map(lambda s: s.name, known_types)))
                            ])

    if variable_name is None:
        variable_name = found.default_variable

    assert len(known_types) == 1  # when this fails, see change needed in the loop below

    requirement_already_exists = False
    existing_requirements = project.find_requirements(project.default_env_spec_name, env_var=variable_name)
    if len(existing_requirements) > 0:
        requirement = existing_requirements[0]
        if isinstance(requirement, ServiceRequirement):
            assert requirement.service_type == service_type
            # when the above assertion fails, add the second known type besides
            # redis in test_project_ops.py::test_add_service_already_exists_with_different_type
            # and then uncomment the below code.
            # if requirement.service_type != service_type:
            #    return SimpleStatus(success=False, description="Unable to add service.",
            #                            errors=["Service %s already exists but with type '%s'" %
            #                              (variable_name, requirement.service_type)])
            # else:
            requirement_already_exists = True
        else:
            return SimpleStatus(success=False,
                                description="Unable to add service.",
                                errors=["Variable %s is already in use." % variable_name])

    if not requirement_already_exists:
        project.project_file.set_value(_path_to_service(env_spec_name, variable_name), service_type)

    return _commit_requirement_if_it_works(project, variable_name, env_spec_name=env_spec_name)


def remove_service(project, env_spec_name, variable_name, prepare_result=None):
    """Remove a service to anaconda-project.yml.

    Returns a ``Status`` instance which evaluates to True on
    success and has an ``errors`` property (with a list of error
    strings) on failure.

    Args:
        project (Project): the project
        env_spec_name (str): environment spec name or None for all environment specs
        variable_name (str): environment variable name for the service requirement
        prepare_result (PrepareResult): result of a previous prepare or None

    Returns:
        ``Status`` instance
    """
    failed = _check_problems(project)

    if failed is not None:
        return failed

    requirements = [
        req for req in project.find_requirements(env_spec_name, klass=ServiceRequirement)
        if req.service_type == variable_name or req.env_var == variable_name
    ]
    if not requirements:
        return SimpleStatus(success=False,
                            description="Service '{}' not found in the project file.".format(variable_name))

    if len(requirements) > 1:
        return SimpleStatus(success=False,
                            description=("Conflicting results, found {} matches, use list-services"
                                         " to identify which service you want to remove").format(len(requirements)))

    if prepare_result is None:
        prepare_result = prepare.prepare_without_interaction(project,
                                                             provide_whitelist=(requirements[0], ),
                                                             env_spec_name=env_spec_name,
                                                             mode=provide.PROVIDE_MODE_CHECK)

    assert env_spec_name is None or prepare_result.env_spec_name == env_spec_name

    env_var = requirements[0].env_var

    status = prepare.unprepare(project, prepare_result, whitelist=[env_var])
    if not status:
        return status

    project.project_file.unset_value(_path_to_service(env_spec_name, env_var))
    project.project_file.use_changes_without_saving()
    assert project.problems == []

    project.project_file.save()
    return SimpleStatus(success=True, description="Removed service '{}' from the project file.".format(variable_name))


def clean(project, prepare_result):
    """Blow away auto-provided state for the project.

    This should not remove any potential "user data" such as
    anaconda-project-local.yml.

    This includes a call to ``anaconda_project.prepare.unprepare``
    but also removes the entire services/ and envs/ directories
    even if they contain leftovers that we didn't prepare in the
    most recent prepare() call.

    Args:
        project (Project): the project instance
        prepare_result (PrepareResult): result of a previous prepare

    Returns:
        a ``Status`` instance

    """
    status = prepare.unprepare(project, prepare_result)

    errors = list(status.errors)

    if status:
        project.frontend.info(status.status_description)
    else:
        errors.extend([status.status_description])
        project.frontend.error(status.status_description)

    # we also nuke any "debris" from non-current choices, like old
    # environments or services
    def cleanup_dir(dirname):
        if os.path.isdir(dirname):
            project.frontend.info("Removing %s." % dirname)
            try:
                shutil.rmtree(dirname)
            except Exception as e:
                errors.append("Error removing %s: %s." % (dirname, str(e)))

    cleanup_dir(os.path.join(project.directory_path, "services"))

    # Clean up the environments only if they are inside the project
    our_root = project.directory_path
    for base in os.environ.get('ANACONDA_PROJECT_ENVS_PATH', '').split(os.pathsep):
        base = os.path.expanduser(base) if base else 'envs'
        apath = os.path.abspath(os.path.join(our_root, base))
        if apath == our_root:
            errors.append('Not removing the project directory itself.')
        elif apath.startswith(our_root + os.sep):
            cleanup_dir(apath)
        else:
            errors.append('Not removing external environment directory: %s' % base)

    if status and len(errors) == 0:
        return SimpleStatus(success=True, description="Cleaned.", errors=errors)
    else:
        return SimpleStatus(success=False, description="Failed to clean everything up.", errors=errors)


def archive(project, filename, pack_envs=False):
    """Make an archive of the non-ignored files in the project.

    Args:
        project (``Project``): the project
        filename (str): name of a zip, tar.gz, or tar.bz2 archive file

    Returns:
        a ``Status``, if failed has ``errors``
    """
    return archiver._archive_project(project, filename, pack_envs)


def unarchive(filename, project_dir, parent_dir=None, frontend=None):
    """Unpack an archive of the project.

    The archive can be untrusted (we will safely defeat attempts
    to put evil links in it, for example), but this function
    doesn't load or validate the unpacked project.

    The target directory must not exist or it's an error.

    project_dir can be None to auto-choose one.

    If parent_dir is non-None, place the project_dir in it. This is most useful
    if project_dir is None.

    Args:
        filename (str): name of a zip, tar.gz, or tar.bz2 archive file
        project_dir (str): the directory to place the project inside
        parent_dir (str): directory to place project_dir within

    Returns:
        a ``Status``, if failed has ``errors``, on success has ``project_dir`` property.

    """
    if frontend is None:
        frontend = _null_frontend()
    return archiver._unarchive_project(filename, project_dir=project_dir, parent_dir=parent_dir, frontend=frontend)


def upload(project, private=None, site=None, username=None, token=None, suffix='.tar.bz2', log_level=None):
    """Upload the project to the Anaconda server.

    The returned status; if successful, has a 'url' attribute with the project URL.

    Args:
        project (``Project``): the project
        private (bool): make project private
        site (str): site alias from Anaconda config
        username (str): Anaconda username
        token (str): Anaconda auth token
        suffix (str): project archive suffix
        log_level (str): Anaconda log level

    Returns:
        a ``Status``, if failed has ``errors``
    """
    failed = _check_problems(project)
    if failed is not None:
        return failed

    # delete=True breaks on windows if you use tmp_tarfile.name to re-open the file,
    # so don't use delete=True.
    tmp_tarfile = NamedTemporaryFile(delete=False, prefix="anaconda_upload_", suffix=suffix)
    tmp_tarfile.close()  # immediately un-use it to avoid file-in-use errors on Windows
    try:
        status = archive(project, tmp_tarfile.name)
        if not status:
            return status
        status = client._upload(project,
                                tmp_tarfile.name,
                                uploaded_basename=(project.name + suffix),
                                private=private,
                                site=site,
                                username=username,
                                token=token,
                                log_level=log_level)
        return status
    finally:
        os.remove(tmp_tarfile.name)


def download(project, unpack=True, project_dir=None, parent_dir=None, site=None, username=None, token=None):
    """Download project from Anaconda Server.

    Args:
        project: The project in format <username>/<project_name>
    """
    download_status = client._download(project,
                                       project_dir=project_dir,
                                       parent_dir=parent_dir,
                                       site=site,
                                       username=username,
                                       token=token)
    if unpack and download_status:
        unpack_status = unarchive(download_status.filename, project_dir=project_dir, parent_dir=parent_dir)
        if unpack_status:
            print(unpack_status.status_description)
    return download_status


def dockerize(project,
              tag=None,
              command='default',
              builder_image='{}:latest'.format(DEFAULT_BUILDER_IMAGE),
              build_args=None):
    """Build docker image from project.

    Args:
        tag: str Version tag for the docker image (default: latest)
        command: str [Optional] Append the Dockerfile with a RUN statement for the chosen anaconda-project command
        build_args: dict [Optional] Additional arguments passed to docker build
    """

    if not project.commands:
        msg = "No known run command for this project; try adding a 'commands:' section to anaconda-project.yml"
        return SimpleStatus(success=False, description=msg)

    if command == 'default':
        command = project.default_command.name
    elif command not in project.commands:
        msg = 'Error setting Docker run command.\n'
        msg += 'The command {} is not one of the configured commands.\n'.format(command)
        msg += 'Available commands are:'
        for k, v in project.commands.items():
            msg += '\n{:>15s}: {}'.format(k, v.description)
        return SimpleStatus(success=False, description=msg)

    if tag is None:
        name = project.name.replace(' ', '').lower()
        tag = '{}:latest'.format(name)

    with TemporaryDirectory() as tempdir:
        print('Archiving project to temporary directory.')

        project_archive = os.path.join(tempdir, 'project.tar.gz')
        archive(project, project_archive)

        project_dir = os.path.join(tempdir, 'project')
        unarchive(project_archive, project_dir)

        print('\nStarting image build. This may take several minutes.')
        build_status = build_image(project_dir,
                                   tag=tag,
                                   command=command,
                                   builder_image=builder_image,
                                   build_args=build_args)

    return build_status
