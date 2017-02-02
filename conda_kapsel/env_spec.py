# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Environment class representing a conda environment."""
from __future__ import absolute_import

import codecs
import difflib
import os

import conda_kapsel.internal.conda_api as conda_api
import conda_kapsel.internal.pip_api as pip_api
from conda_kapsel.internal.py2_compat import is_string

from conda_kapsel.yaml_file import _load_string, _YAMLError

try:
    # this is the conda-packaged version of ruamel.yaml which has the
    # module renamed
    import ruamel_yaml as ryaml
except ImportError:  # pragma: no cover
    # this is the upstream version
    import ruamel.yaml as ryaml  # pragma: no cover


class EnvSpec(object):
    """Represents a set of required conda packages we could potentially instantiate as a Conda environment."""

    def __init__(self, name, conda_packages, channels, pip_packages=(), description=None):
        """Construct a package set with the given name and packages.

        Args:
            name (str): name of the package set
            conda_packages (list): list of package specs to pass to conda install
            channels (list): list of channel names
            pip_packages (list): list of pip package specs to pass to pip
            description (str or None): one-sentence-ish summary of what this env is
        """
        self._name = name
        self._conda_packages = tuple(conda_packages)
        self._channels = tuple(channels)
        self._pip_packages = tuple(pip_packages)
        self._description = description
        self._channels_and_packages_hash = None

        conda_specs_by_name = dict()
        for spec in self.conda_packages:
            # we quietly skip invalid specs here and let them fail
            # somewhere we can more easily report an error message.
            parsed = conda_api.parse_spec(spec)
            if parsed is not None:
                conda_specs_by_name[parsed.name] = spec
        self._conda_specs_by_name = conda_specs_by_name

        pip_specs_by_name = dict()
        for spec in self.pip_packages:
            # we quietly skip invalid specs here and let them fail
            # somewhere we can more easily report an error message.
            parsed = pip_api.parse_spec(spec)
            if parsed is not None:
                pip_specs_by_name[parsed.name] = spec
        self._pip_specs_by_name = pip_specs_by_name

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
    def channels_and_packages_hash(self):
        """Get a hash of our channels and packages.

        This is used to see if they have changed. Order matters
        (change in order will count as a change).
        """
        if self._channels_and_packages_hash is None:
            import hashlib
            m = hashlib.sha1()
            for p in self.conda_packages:
                m.update(p.encode("utf-8"))
            for p in self.pip_packages:
                m.update(p.encode("utf-8"))
            for c in self.channels:
                m.update(c.encode("utf-8"))
            self._channels_and_packages_hash = m.hexdigest()
        return self._channels_and_packages_hash

    @property
    def conda_packages(self):
        """Get the conda packages to install in the environment as an iterable."""
        return self._conda_packages

    @property
    def channels(self):
        """Get the channels to install conda packages from."""
        return self._channels

    @property
    def pip_packages(self):
        """Get the pip packages to install in the environment as an iterable."""
        return self._pip_packages

    @property
    def conda_package_names_set(self):
        """Conda package names that we require, as a Python set."""
        return set(self._conda_specs_by_name.keys())

    @property
    def pip_package_names_set(self):
        """Pip package names that we require, as a Python set."""
        return set(self._pip_specs_by_name.keys())

    def _specs_for_package_names(self, names, mapping):
        specs = []
        for name in names:
            spec = mapping.get(name, None)
            if spec is not None:
                specs.append(spec)
        return specs

    def specs_for_conda_package_names(self, names):
        """Get the full install specs given an iterable of package names."""
        return self._specs_for_package_names(names, self._conda_specs_by_name)

    def specs_for_pip_package_names(self, names):
        """Get the full install specs given an iterable of package names."""
        return self._specs_for_package_names(names, self._pip_specs_by_name)

    def path(self, project_dir):
        """The filesystem path to the default conda env containing our packages."""
        return os.path.join(project_dir, "envs", self.name)

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
        packages when we conda-kapsel init, and that alone shouldn't result
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
        """Get JSON for a kapsel.yml env spec section."""
        packages = list(self.conda_packages)
        pip_packages = list(self.pip_packages)
        if pip_packages:
            packages.append(dict(pip=pip_packages))
        channels = list(self.channels)

        # this is a gross, roundabout hack to get ryaml dicts that
        # have ordering... OrderedDict doesn't work because the
        # yaml saver saves them as some "!!omap" nonsense. Other
        # than ordering, the formatting isn't even preserved here.
        template_json = ryaml.load("something:\n    packages: []\n" + "    channels: []\n",
                                   Loader=ryaml.RoundTripLoader)

        template_json['something']['packages'] = packages
        template_json['something']['channels'] = channels

        return template_json['something']


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

    return EnvSpec(name=name, conda_packages=conda_packages, channels=channels, pip_packages=pip_packages)


def _find_environment_yml_spec(directory_path):
    filenames = ("environment.yml", "environment.yaml")
    for filename in filenames:
        full = os.path.join(directory_path, filename)
        spec = _load_environment_yml(full)
        if spec is not None:
            return (spec, filename)

    return (None, None)


def _find_out_of_sync_environment_yml_spec(project_specs, directory_path):
    (spec, filename) = _find_environment_yml_spec(directory_path)

    if spec is None:
        return (None, None)

    for existing in project_specs:
        if existing.name == spec.name and \
           existing.channels_and_packages_hash == spec.channels_and_packages_hash:
            return (None, None)

    return (spec, filename)


def _anaconda_default_env_spec():
    return EnvSpec(name="default",
                   conda_packages=["anaconda"],
                   channels=[],
                   description="Default environment spec for running commands")
