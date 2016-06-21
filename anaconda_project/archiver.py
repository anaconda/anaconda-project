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
import uuid
import zipfile

from anaconda_project.internal.simple_status import SimpleStatus
from anaconda_project.internal.directory_contains import subdirectory_relative_to_directory
from anaconda_project.internal.rename import rename_over_existing


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


def _list_project(project_directory, ignore_filter, errors):
    try:
        file_infos = []
        for root, dirs, files in os.walk(project_directory):
            filtered_dirs = []
            for d in dirs:
                info = _FileInfo(project_directory=project_directory, filename=os.path.join(root, d), is_directory=True)
                if ignore_filter(info):
                    continue
                else:
                    filtered_dirs.append(d)
                    file_infos.append(info)

            # don't even recurse into filtered-out directories, mostly because recursing into
            # "envs" is very slow
            dirs[:] = filtered_dirs

            for f in files:
                info = _FileInfo(project_directory=project_directory,
                                 filename=os.path.join(root, f),
                                 is_directory=False)
                if not ignore_filter(info):
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
            assert path.startswith("/")
            while path != '/':
                if fnmatch.fnmatch(path, pattern):
                    return True
                # this assumes that on Windows, dirname on a unixified path
                # will do the right thing...
                path = os.path.dirname(path)
            return False

        if self.pattern.startswith("/"):
            # we have to match the full path or one of its parents exactly
            pattern = self.pattern
        else:
            # we only have to match the end of the path (implicit "*/")
            pattern = "*/" + self.pattern

        # So that */ matches even plain "foo" we need to start with /
        match_against = "/" + info.unixified_relative_path

        # ending with / means only match directories
        if pattern.endswith("/"):
            if info.is_directory:
                return match(match_against, pattern[:-1])
            else:
                return False
        else:
            return match(match_against, pattern)


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


def _git_filter(project_directory, errors):
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

    return is_git_ignored


def _ignore_file_filter(project_directory, errors):
    patterns = _load_ignore_file(project_directory, errors)
    if patterns is None:
        assert errors
        return None

    def matches_some_pattern(info):
        for pattern in patterns:
            if pattern.matches(info):
                return True
        return False

    return matches_some_pattern


def _enumerate_archive_files(project_directory, errors, requirements):
    git_filter = _git_filter(project_directory, errors)
    ignore_file_filter = _ignore_file_filter(project_directory, errors)
    if git_filter is None or ignore_file_filter is None:
        assert errors
        return None

    plugin_patterns = set()
    for req in requirements:
        plugin_patterns = plugin_patterns.union(req.ignore_patterns)
    plugin_patterns = [_FilePattern(s) for s in plugin_patterns]

    def is_plugin_generated(info):
        for pattern in plugin_patterns:
            if pattern.matches(info):
                return True
        return False

    def all_filters(info):
        return git_filter(info) or ignore_file_filter(info) or is_plugin_generated(info)

    infos = _list_project(project_directory, all_filters, errors)
    if infos is None:
        assert errors
        return None

    return infos


def _leaf_infos(infos):
    all_by_name = dict()
    for info in infos:
        all_by_name[info.relative_path] = info
    for info in infos:
        parent = os.path.dirname(info.relative_path)
        while parent != '':
            assert parent != '/'  # would be infinite loop
            if parent in all_by_name:
                del all_by_name[parent]
            parent = os.path.dirname(parent)

    return all_by_name.values()


def _write_tar(archive_root_name, infos, filename, compression, logs):
    if compression is None:
        compression = ""
    else:
        compression = ":" + compression
    with tarfile.open(filename, ('w%s' % compression)) as tf:
        for info in _leaf_infos(infos):
            arcname = os.path.join(archive_root_name, info.relative_path)
            logs.append("  added %s" % arcname)
            tf.add(info.full_path, arcname=arcname)


def _write_zip(archive_root_name, infos, filename, logs):
    with zipfile.ZipFile(filename, 'w') as zf:
        for info in _leaf_infos(infos):
            arcname = os.path.join(archive_root_name, info.relative_path)
            logs.append("  added %s" % arcname)
            zf.write(info.full_path, arcname=arcname)


# function exported for project.py
def _list_relative_paths_for_unignored_project_files(project_directory, errors, requirements):
    infos = _enumerate_archive_files(project_directory, errors, requirements=requirements)
    if infos is None:
        return None
    return [info.relative_path for info in infos]


# function exported for project_ops.py
def _archive_project(project, filename):
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
    infos = _enumerate_archive_files(project.directory_path, errors, requirements=project.requirements)
    if infos is None:
        return SimpleStatus(success=False, description="Failed to list files in the project.", errors=errors)

    # don't put the destination zip into itself, since it's fairly natural to
    # create a archive right in the project directory
    relative_dest_file = subdirectory_relative_to_directory(filename, project.directory_path)
    if not os.path.isabs(relative_dest_file):
        infos = [info for info in infos if info.relative_path != relative_dest_file]

    logs = []
    tmp_filename = filename + ".tmp-" + str(uuid.uuid4())
    try:
        if filename.lower().endswith(".zip"):
            _write_zip(project.name, infos, tmp_filename, logs)
        elif filename.lower().endswith(".tar.gz"):
            _write_tar(project.name, infos, tmp_filename, compression="gz", logs=logs)
        elif filename.lower().endswith(".tar.bz2"):
            _write_tar(project.name, infos, tmp_filename, compression="bz2", logs=logs)
        elif filename.lower().endswith(".tar"):
            _write_tar(project.name, infos, tmp_filename, compression=None, logs=logs)
        else:
            return SimpleStatus(success=False,
                                description="Project archive filename must be a .zip, .tar.gz, or .tar.bz2.",
                                errors=["Unsupported archive filename %s." % (filename)])
        rename_over_existing(tmp_filename, filename)
    except IOError as e:
        return SimpleStatus(success=False,
                            description=("Failed to write project archive %s." % (filename)),
                            errors=[str(e)])
    finally:
        try:
            os.remove(tmp_filename)
        except (IOError, OSError):
            pass

    return SimpleStatus(success=True, description=("Created project archive %s" % filename), logs=logs)
