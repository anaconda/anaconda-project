# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Bundle up a project for shipment."""
from __future__ import absolute_import, print_function

import codecs
import errno
import fnmatch
import os
import platform
import subprocess
import tarfile
import zipfile

from anaconda_project.internal.simple_status import SimpleStatus
from anaconda_project.internal.directory_contains import subdirectory_relative_to_directory


class _FileInfo(object):
    def __init__(self, project_directory, filename, is_directory):
        self.full_path = os.path.abspath(filename)
        self.relative_path = os.path.relpath(self.full_path, start=project_directory)
        if platform.system() == 'Windows':
            self.unixified_relative_path = self.relative_path.replace("\\", "/")
        else:
            self.unixified_relative_path = self.relative_path
        self.basename = os.path.basename(self.full_path)
        self.is_directory = is_directory


def _list_project(project_directory, errors):
    try:
        file_infos = []
        for root, dirs, files in os.walk(project_directory):
            for f in files:
                info = _FileInfo(project_directory=project_directory,
                                 filename=os.path.join(root, f),
                                 is_directory=False)
                file_infos.append(info)
            for d in dirs:
                info = _FileInfo(project_directory=project_directory, filename=os.path.join(root, d), is_directory=True)
                file_infos.append(info)
        return file_infos
    except OSError as e:
        errors.append("Could not list files in %s: %s." % (project_directory, str(e)))
        return None


class _FilePattern(object):
    def __init__(self, pattern):
        assert pattern != ''
        # the glob string
        self.pattern = pattern

    def matches(self, info):
        # Unlike .gitignore, this is a path-unaware match; fnmatch doesn't pay
        # any attention to "/" as a special character. However, on Windows, we
        # have fixed up unixified_relative_path to have / instead of \, so that
        # it will match patterns specified with /.
        def match(path, pattern):
            while path != '':
                assert path[0] != '/'  # this would put us in an infinite loop
                if fnmatch.fnmatch(path, pattern):
                    return True
                # this assumes that on Windows, dirname on a unixified path
                # will do the right thing...
                path = os.path.dirname(path)
            return False

        if self.pattern.startswith("/"):
            # we have to match the full path or one of its parents exactly
            return match(info.unixified_relative_path, self.pattern[1:])
        else:
            # we only have to match the end of the path (implicit "*")
            return match(info.unixified_relative_path, "*" + self.pattern)


def _parse_ignore_file(filename, errors):
    patterns = []
    try:
        with codecs.open(filename, 'r', 'utf-8') as f:
            for line in f:
                line = line.strip()

                # comments can't be at the end of the line,
                # you can only comment out an entire line.
                if line.startswith("#"):
                    continue

                # you can backslash-escape a hash at the start
                if line.startswith("\#"):
                    line = line[1:]

                if line != '':
                    patterns.append(_FilePattern(pattern=line))
        return patterns
    except (OSError, IOError) as e:
        # it's ok for .projectignore to be absent, but not OK
        # to fail to read it if present.
        if e.errno == errno.ENOENT:
            # return default patterns anyway
            return patterns
        else:
            errors.append("Failed to read %s: %s" % (filename, str(e)))
            return None


def _load_ignore_file(project_directory, errors):
    ignore_file = os.path.join(project_directory, ".projectignore")
    return _parse_ignore_file(ignore_file, errors)


def _git_ignored_files(project_directory, errors):
    if not os.path.exists(os.path.join(project_directory, ".git")):
        return []

    # It is pretty involved to parse .gitignore correctly. Lots of
    # little syntax rules that don't quite match python's fnmatch,
    # there can be multiple .gitignore, and there are also things
    # in the git config file that affect what's ignored.  So we
    # let git do this itself. If the project has a `.git` we assume
    # the user is using git.

    # --other means show untracked (not added) files
    # --ignored means show ignored files
    # --exclude-standard means use the usual .gitignore and other configuration
    try:
        output = subprocess.check_output(
            ['git', 'ls-files', '--others', '--ignored', '--exclude-standard'],
            cwd=project_directory)
        # for whatever reason, git doesn't include the ".git" in the ignore list
        return [".git"] + output.decode('utf-8').splitlines()
    except subprocess.CalledProcessError as e:
        message = e.output.decode('utf-8').replace("\n", " ")
        errors.append("'git ls-files' failed to list ignored files: %s." % (message))
        return None
    except OSError as e:
        errors.append("Failed to run 'git ls-files'; %s" % str(e))
        return None


def _enumerate_bundle_files(project_directory, errors, requirements):
    infos = _list_project(project_directory, errors)
    if infos is None:
        assert errors
        return None

    git_ignored = _git_ignored_files(project_directory, errors)
    if git_ignored is None:
        assert errors
        return None

    git_ignored = set(git_ignored)

    def is_git_ignored(info):
        path = info.relative_path
        while path != '':
            assert path != '/'  # would infinite loop
            if path in git_ignored:
                return True
            path = os.path.dirname(path)
        return False

    infos = [info for info in infos if not is_git_ignored(info)]

    patterns = _load_ignore_file(project_directory, errors)
    if patterns is None:
        assert errors
        return None

    def matches_some_pattern(info):
        for pattern in patterns:
            if pattern.matches(info):
                return True
        return False

    infos = [info for info in infos if not matches_some_pattern(info)]

    plugin_patterns = set()
    for req in requirements:
        plugin_patterns = plugin_patterns.union(req.ignore_patterns)
    plugin_patterns = [_FilePattern(s) for s in plugin_patterns]

    def is_plugin_generated(info):
        for pattern in plugin_patterns:
            if pattern.matches(info):
                return True
        return False

    infos = [info for info in infos if not is_plugin_generated(info)]

    return infos


def _write_tar(infos, filename, compression, logs):
    with tarfile.open(filename, ('w:%s' % compression)) as tf:
        for info in infos:
            logs.append("  added %s" % info.relative_path)
            tf.add(info.full_path, arcname=info.relative_path)


def _write_zip(infos, filename, logs):
    with zipfile.ZipFile(filename, 'w') as zf:
        for info in infos:
            logs.append("  added %s" % info.relative_path)
            zf.write(info.full_path, arcname=info.relative_path)


# function exported for project.py
def _list_relative_paths_for_unignored_project_files(project_directory, errors, requirements):
    infos = _enumerate_bundle_files(project_directory, errors, requirements=requirements)
    if infos is None:
        return None
    return [info.relative_path for info in infos]


# function exported for project_ops.py
def _bundle_project(project, filename):
    """Make an archive of the non-ignored files in the project.

    Args:
        project (``Project``): the project
        filename (str): name for the new zip or tar.gz archive file

    Returns:
        a ``Status``, if failed has ``errors``
    """
    failed = project.problems_status()
    if failed is not None:
        return failed

    errors = []
    infos = _enumerate_bundle_files(project.directory_path, errors, requirements=project.requirements)
    if infos is None:
        return SimpleStatus(success=False, description="Failed to list files in the project.", errors=errors)

    # don't put the destination zip into itself, since it's fairly natural to
    # create a bundle right in the project directory
    relative_dest_file = subdirectory_relative_to_directory(filename, project.directory_path)
    if not os.path.isabs(relative_dest_file):
        infos = [info for info in infos if info.relative_path != relative_dest_file]

    logs = []
    try:
        if filename.lower().endswith(".zip"):
            _write_zip(infos, filename, logs)
        elif filename.lower().endswith(".tar.gz"):
            _write_tar(infos, filename, compression="gz", logs=logs)
        elif filename.lower().endswith(".tar.bz2"):
            _write_tar(infos, filename, compression="bz2", logs=logs)
        else:
            return SimpleStatus(success=False,
                                description="Project bundle filename must be a .zip, .tar.gz, or .tar.bz2.",
                                errors=["Unsupported bundle filename %s." % (filename)])
    except IOError as e:
        return SimpleStatus(success=False,
                            description=("Failed to write project bundle %s." % (filename)),
                            errors=[str(e)])

    return SimpleStatus(success=True, description=("Created project bundle %s" % filename), logs=logs)
