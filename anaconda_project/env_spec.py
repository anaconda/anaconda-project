# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Environment class representing a conda environment."""
from __future__ import absolute_import

import codecs
import difflib
import shutil
import os
import re

import anaconda_project.internal.conda_api as conda_api
import anaconda_project.internal.pip_api as pip_api
from anaconda_project.internal.py2_compat import is_string
from anaconda_project import conda_manager

from anaconda_project.yaml_file import _load_string, _save_file, _YAMLError, ryaml


class EnvSpec(object):
    """Represents a set of required conda packages we could potentially instantiate as a Conda environment."""
    def __init__(self,
                 name,
                 conda_packages,
                 channels,
                 pip_packages=(),
                 description=None,
                 inherit_from_names=(),
                 inherit_from=(),
                 platforms=(),
                 lock_set=None):
        """Construct a package set with the given name and packages.

        Args:
            name (str): name of the package set
            conda_packages (list): list of package specs to pass to conda install
            channels (list): list of channel names
            pip_packages (list): list of pip package specs to pass to pip
            description (str or None): one-sentence-ish summary of what this env is
            inherit_from_name (str or None): name of what we inherit from
            inherit_from (EnvSpec or None): pull in packages and channels from
            lock_set (CondaLockSet): locked packages or None
        """
        assert inherit_from_names is not None
        assert inherit_from is not None

        self._name = name
        self._path = None
        self._readonly = None
        self._conda_packages = tuple(conda_packages)
        self._channels = tuple(channels)
        self._pip_packages = tuple(pip_packages)
        self._description = description
        self._logical_hash = None
        self._locked_hash = None
        self._import_hash = None
        self._inherit_from_names = inherit_from_names
        self._inherit_from = inherit_from
        self._lock_set = lock_set
        self._platforms = tuple(conda_api.sort_platform_list(platforms))

        # inherit_from must be a subset of inherit_from_names
        # except that we can have an anonymous base env spec for
        # the global packages/channels sections; if there was an
        # error that kept us from creating one of the specs we
        # name as a parent, then self._inherit_from would be a
        # subset rather than equal.
        for name in tuple([spec.name for spec in self._inherit_from]):
            assert name is None or name in self._inherit_from_names

        conda_specs_by_name = dict()
        for spec in self.conda_packages_for_create:
            # we quietly skip invalid specs here and let them fail
            # somewhere we can more easily report an error message.
            parsed = conda_api.parse_spec(spec)
            if parsed is not None:
                conda_specs_by_name[parsed.name] = spec
        self._conda_specs_for_create_by_name = conda_specs_by_name

        name_set = set()
        conda_constrained_packages = []
        for spec in self.conda_packages:
            parsed = conda_api.parse_spec(spec)
            if parsed is not None:
                name_set.add(parsed.name)
                if parsed.conda_constraint is not None or parsed.pip_constraint is not None:
                    conda_constrained_packages.append(spec)
        self._conda_logical_specs_name_set = name_set
        self.conda_constrained_packages = sorted(conda_constrained_packages)

        pip_specs_by_name = dict()
        for spec in self.pip_packages_for_create:
            # we quietly skip invalid specs here and let them fail
            # somewhere we can more easily report an error message.
            parsed = pip_api.parse_spec(spec)
            if parsed is not None:
                pip_specs_by_name[parsed.name] = spec
        self._pip_specs_for_create_by_name = pip_specs_by_name

        name_set = set()
        for spec in self.pip_packages:
            parsed = pip_api.parse_spec(spec)
            if parsed is not None:
                name_set.add(parsed.name)
        self._pip_logical_specs_name_set = name_set

        self._conda = conda_manager.new_conda_manager()

    @property
    def name(self):
        """Get name of the package set.

        May be None for the anonymous shared base spec
        (toplevel packages, channels sections).
        """
        return self._name

    @property
    def description(self):
        """Get the description of the environment."""
        if self._description is None:
            return self._name
        else:
            return self._description

    def _compute_hash(self, conda_packages, platforms):
        import hashlib
        m = hashlib.sha1()
        for p in conda_packages:
            m.update(p.encode("utf-8"))
        for p in self.pip_packages:
            m.update(p.encode("utf-8"))
        for c in self.channels:
            m.update(c.encode("utf-8"))
        for p in platforms:
            m.update(p.encode("utf-8"))
        result = m.hexdigest()
        return result

    @property
    def logical_hash(self):
        """Get a hash of our "logical" requirements.

        (Changing logical requirements could change the lock set
        if we recreate it.)

        Order matters (change in order will count as a change).

        """
        if self._logical_hash is None:
            self._logical_hash = self._compute_hash(self.conda_packages, self.platforms)
        return self._logical_hash

    @property
    def locked_hash(self):
        """Get a hash of our locked packages (what we'd pass to conda create).

        This is used to see if we need to reprepare
        environments. Order matters (change in order will count as
        a change).
        """
        if self._locked_hash is None:
            self._locked_hash = self._compute_hash(self.conda_packages_for_create, platforms=())
        return self._locked_hash

    @property
    def import_hash(self):
        """Get a hash of parts of the env spec that can appear in environment.yml.

        This is used to see if we need to re-import the environment.yml, requirements.txt
        or whatever. Those files don't have platform information.
        """
        if self._import_hash is None:
            self._import_hash = self._compute_hash(self.conda_packages, platforms=())
        return self._import_hash

    def _get_inherited(self, public_attr, key_func=None):
        private_attr = '_' + public_attr

        def getter(spec):
            return getattr(spec, private_attr)

        return self._get_inherited_with_getter(getter, key_func=key_func)

    def _get_inherited_with_getter(self, getter, key_func=None):
        def _linearized_ancestors(specs, accumulator):
            for spec in specs:
                if spec not in accumulator:
                    _linearized_ancestors(spec._inherit_from, accumulator)
                    accumulator.append(spec)

        ancestors = []
        _linearized_ancestors([self], ancestors)
        assert ancestors[-1] is self

        to_combine = []
        for spec in ancestors:
            to_combine.append(getter(spec))
        combined = []
        for item in to_combine:
            combined = conda_manager._combine_keeping_last_duplicate(combined, item, key_func=key_func)
        return combined

    @property
    def conda_packages(self):
        """Get the conda packages to install in the environment as an iterable."""
        return self._get_inherited('conda_packages', conda_manager._conda_combine_key)

    @property
    def channels(self):
        """Get the channels to install conda packages from."""
        return self._get_inherited('channels')

    @property
    def platforms(self):
        """Get the platforms the environment can be on."""
        return self._get_inherited('platforms')

    @property
    def pip_packages(self):
        """Get the pip packages to install in the environment as an iterable."""
        return self._get_inherited('pip_packages', conda_manager._pip_combine_key)

    @property
    def conda_package_names_set(self):
        """Conda package names that we require, as a Python set."""
        return self._conda_logical_specs_name_set

    @property
    def conda_package_names_for_create_set(self):
        """Conda package names that we require, as a Python set."""
        return set(self._conda_specs_for_create_by_name.keys())

    @property
    def conda_package_names_constrained_set(self):
        """List of conda package names with version constraints."""
        return set(self._conda_names_constrained)

    @property
    def pip_package_names_set(self):
        """Pip package names that we require, as a Python set."""
        return set(self._pip_logical_specs_name_set)

    @property
    def pip_package_names_for_create_set(self):
        """Pip package names that we require, as a Python set."""
        return set(self._pip_specs_for_create_by_name.keys())

    @property
    def lock_set(self):
        """Get ``CondaLockSet`` for this env spec."""
        return self._lock_set

    @property
    def conda_packages_for_create(self):
        """Get conda packages (preferring the lock set list if present)."""
        if self._lock_set is not None and self._lock_set.enabled and self._lock_set.supports_current_platform:
            return self._lock_set.package_specs_for_current_platform
        else:
            return self.conda_packages

    @property
    def pip_packages_for_create(self):
        """Get pip packages (preferring the lock set list if present)."""
        if self._lock_set is not None and self._lock_set.enabled and self._lock_set.supports_current_platform:
            # This happens during the lock procedure because pip packages
            # cannot be determined until they are installed. Conda is the
            # reverse.
            if not self._lock_set.pip_package_specs and self.pip_packages:
                return self.pip_packages
            else:
                return self._lock_set.pip_package_specs
        else:
            return self.pip_packages

    def _specs_for_package_names(self, names, mapping):
        specs = []
        for name in names:
            spec = mapping.get(name, None)
            if spec is not None:
                specs.append(spec)
        return specs

    def specs_for_conda_package_names(self, names):
        """Get the full install specs given an iterable of package names."""
        return self._specs_for_package_names(names, self._conda_specs_for_create_by_name)

    def specs_for_pip_package_names(self, names):
        """Get the full install specs given an iterable of package names."""
        return self._specs_for_package_names(names, self._pip_specs_for_create_by_name)

    @property
    def inherit_from(self):
        """Env spec that we inherit stuff from."""
        return self._inherit_from

    @property
    def inherit_from_names(self):
        """Env spec names that we inherit stuff from."""
        return self._inherit_from_names

    def path(self, project_dir, reset=False, force_writable=False):
        """The filesystem path to the default conda env containing our packages."""

        if reset:
            # Reset is used after a readonly env is cloned to identify
            # the new writeable env prefix, otherwise the readonly prefix
            # would remain chached
            self._path = None

        if self._path is None:

            def _prefix(base_path):
                base_path = os.path.expanduser(base_path) if base_path else 'envs'
                path = os.path.abspath(os.path.join(project_dir, base_path, self.name))
                return path

            def _found(env_prefix):
                return os.path.isdir(os.path.join(env_prefix, 'conda-meta'))

            env_paths = os.environ.get('ANACONDA_PROJECT_ENVS_PATH', '').split(os.pathsep)

            # Scan for an existing env with the same name
            existing_env = None
            for base in env_paths:
                prefix = _prefix(base)
                if _found(prefix) and (not force_writable or self._conda._is_environment_writable(prefix)):
                    existing_env = prefix
                    break

            # If we need a writable environment, find the first writable location
            if existing_env is None and force_writable:
                for base in env_paths:
                    prefix = _prefix(base)
                    if not _found(prefix) and self._conda._is_environment_writable(prefix):
                        shutil.rmtree(prefix)
                        existing_env = prefix
                        break

            if existing_env is not None:
                self._path = existing_env
            else:
                self._path = _prefix(env_paths[0])

        return self._path

    def diff_from(self, old):
        """A string showing the comparison between this env spec and another one."""
        channels_diff = list(difflib.ndiff(old.channels, self.channels))
        conda_diff = list(difflib.ndiff(old.conda_packages, self.conda_packages))
        pip_diff = list(difflib.ndiff(old.pip_packages, self.pip_packages))
        if pip_diff:
            pip_diff = ["  pip:"] + list(map(lambda x: "    " + x, pip_diff))
        if channels_diff:
            channels_diff = ["  channels:"] + list(map(lambda x: "    " + x, channels_diff))
        return "\n".join(channels_diff + conda_diff + pip_diff)

    def diff_only_removes_notebook_or_bokeh(self, old):
        """Check whether the diff is exclusively removing 'bokeh' or 'notebook'.

        This is used for a hack, because we can auto-add 'bokeh' or 'notebook'
        packages when we anaconda-project init, and that alone shouldn't result
        in being out of sync with the environment.yml.
        """
        to_remove = [("- " + r) for r in ("bokeh", "notebook")]

        def filter_context(items):
            return list(filter(lambda line: line.startswith("- ") or line.startswith("+ "), items))

        conda_diff = filter_context(difflib.ndiff(old.conda_packages, self.conda_packages))
        for r in to_remove:
            if r in conda_diff:
                conda_diff.remove(r)

        if len(conda_diff) > 0:
            return False

        channels_diff = filter_context(difflib.ndiff(old.channels, self.channels))
        if len(channels_diff) > 0:
            return False

        pip_diff = filter_context(difflib.ndiff(old.pip_packages, self.pip_packages))
        if len(pip_diff) > 0:
            return False

        return True

    def to_json(self):
        """Get JSON for an anaconda-project.yml env spec section."""
        # Note that we use _conda_packages (only the packages we
        # introduce ourselves) rather than conda_packages
        # (includes inherited packages).
        packages = list(self._conda_packages)
        pip_packages = list(self._pip_packages)
        if pip_packages:
            packages.append(dict(pip=pip_packages))
        channels = list(self._channels)
        platforms = list(self._platforms)

        # this is a gross, roundabout hack to get ryaml dicts that
        # have ordering... OrderedDict doesn't work because the
        # yaml saver saves them as some "!!omap" nonsense. Other
        # than ordering, the formatting isn't even preserved here.
        template_json = ryaml.load("something:\n    description: null\n" + "    packages: []\n" + "    channels: []\n",
                                   Loader=ryaml.RoundTripLoader)

        if self._description is not None:
            template_json['something']['description'] = self._description
        else:
            del template_json['something']['description']
        template_json['something']['packages'] = packages
        template_json['something']['channels'] = channels

        # usually "platforms" will be global so don't clutter
        # every env spec by default
        if len(platforms) > 0:
            template_json['something']['platforms'] = platforms

        if len(self.inherit_from_names) > 0:
            if len(self.inherit_from_names) == 1:
                names = self.inherit_from_names[0]
            else:
                names = list(self.inherit_from_names)
            template_json['something']['inherit_from'] = names

        return template_json['something']

    def apply_pins(self, prefix, updating=()):
        """Write the augmented pinned file in the environment."""
        conda_meta_path = os.path.join(prefix, 'conda-meta')
        if not os.path.isdir(conda_meta_path):
            raise RuntimeError('Expected path {} to exist'.format(conda_meta_path))
        fname = os.path.join(conda_meta_path, 'pinned')
        if os.path.exists(fname):
            with open(fname, 'r') as fp:
                old_list = fp.read()
        else:
            old_list = ''
        # Don't add pins for packages we are currently updating to avoid issues
        # with the historical soft pins of conda 4.6 and later
        new_list = '\n'.join(set(self.conda_constrained_packages) - set(updating))
        if old_list != new_list:
            if new_list:
                with open(fname + '.__ap_new', 'w') as fp:
                    fp.write(new_list)
            if os.path.exists(fname):
                os.rename(fname, fname + '.__ap_orig')
            if new_list:
                os.rename(fname + '.__ap_new', fname)

    def remove_pins(self, prefix):
        """Remove the pinned file."""
        conda_meta_path = os.path.join(prefix, 'conda-meta')
        if not os.path.isdir(conda_meta_path):
            raise RuntimeError('Expected path {} to exist'.format(conda_meta_path))
        fname = os.path.join(conda_meta_path, 'pinned')
        if os.path.exists(fname):
            if os.path.exists(fname + '.__ap_orig'):
                os.rename(fname + '.__ap_orig', fname)
            else:
                os.remove(fname)

    def save_environment_yml(self, filename):
        """Save as an environment.yml file."""
        # here we want to flatten the env spec to include all inherited stuff
        packages = list(self.conda_packages)
        pip_packages = list(self.pip_packages)
        if pip_packages:
            packages.append(dict(pip=pip_packages))
        channels = list(self.channels)

        yaml = ryaml.load("name: " "\ndependencies: []\nchannels: []\n", Loader=ryaml.RoundTripLoader)

        assert self.name is not None  # the global anonymous spec can't be saved
        yaml['name'] = self.name
        yaml['dependencies'] = packages
        yaml['channels'] = channels

        _save_file(yaml, filename)


def _load_environment_yml(filename):
    """Load an environment.yml as an EnvSpec, or None if not loaded."""
    try:
        with codecs.open(filename, 'r', 'utf-8') as file:
            contents = file.read()
        yaml = _load_string(contents)
    except (IOError, _YAMLError):
        return None

    name = None
    if 'name' in yaml:
        name = yaml['name']
    if not name:
        if 'prefix' in yaml and yaml['prefix']:
            name = os.path.basename(yaml['prefix'])

    if not name:
        name = os.path.basename(filename)

    # We don't do too much validation here because we end up doing it
    # later if we import this into the project, and then load it from
    # the project file. We will do the import such that we don't end up
    # keeping the new project file if it's messed up.
    #
    # However we do try to avoid crashing on None or type errors here.

    raw_dependencies = yaml.get('dependencies', [])
    if not isinstance(raw_dependencies, list) or len(raw_dependencies) == 0:
        raw_dependencies = yaml.get('packages', [])
        if not isinstance(raw_dependencies, list):
            raw_dependencies = []

    raw_channels = yaml.get('channels', [])
    if not isinstance(raw_channels, list):
        raw_channels = []

    conda_packages = []
    pip_packages = []

    for dep in raw_dependencies:
        if is_string(dep):
            conda_packages.append(dep)
        elif isinstance(dep, dict) and 'pip' in dep and isinstance(dep['pip'], list):
            for pip_dep in dep['pip']:
                if is_string(pip_dep):
                    pip_packages.append(pip_dep)

    channels = []
    for channel in raw_channels:
        if is_string(channel):
            channels.append(channel)

    return EnvSpec(name=name, conda_packages=conda_packages, channels=channels, pip_packages=pip_packages, platforms=())


_requirement_option_re = re.compile(r'^-([-a-zA-Z0-9]+)\s(.*)')


def _load_requirements_txt(filename):
    """Load a requirements.txt as an EnvSpec, or None if not loaded."""
    try:
        with codecs.open(filename, 'r', 'utf-8') as file:
            lines = file.readlines()
    except (IOError, _YAMLError):
        return None

    # We don't do too much validation here because we end up doing it
    # later if we import this into the project, and then load it from
    # the project file. We will do the import such that we don't end up
    # keeping the new project file if it's messed up.
    #
    # However we do try to avoid crashing on None or type errors here.

    packages = []
    for line in lines:
        line = line.strip()
        # note: comments MUST be at start of line, because
        # urls can have a hash mark in them
        if line.startswith("#") or line == '':
            continue
        m = _requirement_option_re.search(line)
        if m is not None:
            option = m.group(1)
            package = m.group(2)
            # '-e' means a URL requirement.  '-r' means to
            # recursively include another file. other options are
            # simply ignored right now, which won't really work
            # out well, but.
            if option == 'e':
                packages.append(package)
            elif option == 'r':
                path = os.path.join(os.path.dirname(filename), package)
                child_spec = _load_requirements_txt(path)
                if child_spec is not None:
                    packages.extend(child_spec.pip_packages)
        else:
            packages.append(line)

    return EnvSpec(name='default', conda_packages=(), channels=(), pip_packages=packages)


def _load_importable(filename):
    if filename.endswith(".txt"):
        return _load_requirements_txt(filename)
    else:
        return _load_environment_yml(filename)


def _find_importable_spec(directory_path):
    filenames = ("environment.yml", "environment.yaml", 'requirements.txt')
    for filename in filenames:
        full = os.path.join(directory_path, filename)
        spec = _load_importable(full)
        if spec is not None:
            return (spec, filename)

    return (None, None)


def _find_out_of_sync_importable_spec(project_specs, directory_path):
    (spec, filename) = _find_importable_spec(directory_path)

    if spec is None:
        return (None, None)

    for existing in project_specs:
        if existing.name == spec.name and \
           existing.import_hash == spec.import_hash:
            return (None, None)

    return (spec, filename)


# Added so it can be mocked
def _default_env_spec_packages():
    return ['anaconda']


def _anaconda_default_env_spec(shared_base_spec):
    if shared_base_spec is None:
        inherit_from = ()
    else:
        inherit_from = (shared_base_spec, )
    return EnvSpec(name="default",
                   conda_packages=_default_env_spec_packages(),
                   channels=[],
                   platforms=conda_api.default_platforms_with_current(),
                   description="Default environment spec for running commands",
                   inherit_from_names=(),
                   inherit_from=inherit_from)


def _empty_default_env_spec(shared_base_spec):
    if shared_base_spec is None:
        inherit_from = ()
    else:
        inherit_from = (shared_base_spec, )
    return EnvSpec(name="default",
                   conda_packages=[],
                   channels=[],
                   platforms=conda_api.default_platforms_with_current(),
                   description="Default environment spec for running commands",
                   inherit_from_names=(),
                   inherit_from=inherit_from)
