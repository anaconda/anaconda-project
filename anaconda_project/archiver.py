# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Bundle up a project for shipment."""
from __future__ import absolute_import, print_function

import codecs
import errno
import fnmatch
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
import uuid
import zipfile
from io import BytesIO
from conda_pack._progress import progressbar
from tqdm import tqdm

from anaconda_project.frontend import NullFrontend, _new_error_recorder
from anaconda_project.internal import logged_subprocess
from anaconda_project.internal.simple_status import SimpleStatus
from anaconda_project.internal.directory_contains import subdirectory_relative_to_directory
from anaconda_project.internal.rename import rename_over_existing
from anaconda_project.internal.makedirs import makedirs_ok_if_exists
from anaconda_project.internal.conda_api import current_platform


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


def _list_project(project_directory, ignore_filter, frontend):
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
        frontend.error("Could not list files in %s: %s." % (project_directory, str(e)))
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


def _parse_ignore_file(filename, frontend):
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
                if line.startswith(r"\#"):
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
            frontend.error("Failed to read %s: %s" % (filename, str(e)))
            return None


def _load_ignore_file(project_directory, frontend):
    ignore_file = os.path.join(project_directory, ".projectignore")
    return _parse_ignore_file(ignore_file, frontend)


def _git_ignored_files(project_directory, frontend):
    if not os.path.exists(os.path.join(project_directory, ".git")):
        if os.path.exists(os.path.join(project_directory, ".gitignore")):
            frontend.error(
                "Warning: the .gitignore file is being ignored because this directory is not a Git repository.")
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
    # --directory means output "node_modules/" if it's ignored, not 100000 JS files
    try:
        output = logged_subprocess.check_output(
            ['git', 'ls-files', '--others', '--ignored', '--exclude-standard', '--directory'], cwd=project_directory)
        # for whatever reason, git doesn't include the ".git" in the ignore list
        return [".git"] + output.decode('utf-8').splitlines()
    except subprocess.CalledProcessError as e:
        message = e.output.decode('utf-8').replace("\n", " ")
        frontend.error("'git ls-files' failed to list ignored files: %s." % (message))
        return None
    except OSError as e:
        frontend.error("Failed to run 'git ls-files'; %s" % str(e))
        return None


def _git_filter(project_directory, frontend):
    git_ignored = _git_ignored_files(project_directory, frontend)
    if git_ignored is None:
        return None

    git_ignored = set(git_ignored)

    def is_git_ignored(info):
        path = info.relative_path
        while path != '':
            assert path != '/'  # would infinite loop
            # git ls-files seems to append "/" to dirs when using --directory
            if path in git_ignored or (path + '/') in git_ignored:
                return True
            path = os.path.dirname(path)
        return False

    return is_git_ignored


def _ignore_file_filter(project_directory, frontend):
    patterns = _load_ignore_file(project_directory, frontend)
    if patterns is None:
        return None

    def matches_some_pattern(info):
        for pattern in patterns:
            if pattern.matches(info):
                return True
        return False

    return matches_some_pattern


def _enumerate_archive_files(project_directory, frontend, requirements):
    git_filter = _git_filter(project_directory, frontend)
    ignore_file_filter = _ignore_file_filter(project_directory, frontend)
    if git_filter is None or ignore_file_filter is None:
        return None

    plugin_patterns = {'/anaconda-project-local.yml'}
    for req in requirements:
        plugin_patterns.update(req.ignore_patterns)
    plugin_patterns = [_FilePattern(s) for s in plugin_patterns]

    def is_plugin_generated(info):
        for pattern in plugin_patterns:
            if pattern.matches(info):
                return True
        return False

    def all_filters(info):
        return git_filter(info) or ignore_file_filter(info) or is_plugin_generated(info)

    infos = _list_project(project_directory, all_filters, frontend)
    if infos is None:
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

    return sorted(all_by_name.values(), key=lambda x: x.relative_path)


def _write_tar(archive_root_name, infos, filename, compression, packed_envs, frontend):
    if compression is None:
        compression = ""
    else:
        compression = ":" + compression
    with tarfile.open(filename, ('w%s' % compression)) as tf:
        for info in _leaf_infos(infos):
            arcname = os.path.join(archive_root_name, info.relative_path)
            frontend.info("  added %s" % arcname)
            tf.add(info.full_path, arcname=arcname)

        for pack in packed_envs:
            env_name = os.path.basename(pack)
            print('Joining packed env {}'.format(env_name))
            with tarfile.open(pack, mode='r', dereference=False) as env:
                with progressbar(env.getmembers()) as env_p:
                    for file in env_p:
                        try:
                            data = env.extractfile(file)
                            tf.addfile(file, data)
                        except KeyError:  # pragma: no cover
                            tf.addfile(file)
                    env_spec = env_name.split('.')[0].split('_')[-1]
                    dot_packed = os.path.join(archive_root_name, 'envs', env_spec, 'conda-meta', '.packed')
                    platform = '{}\n'.format(current_platform())

                    f = BytesIO()
                    f.write(platform.encode())

                    tinfo = tarfile.TarInfo(dot_packed)
                    tinfo.size = f.tell()
                    f.seek(0)
                    tf.addfile(tinfo, fileobj=f)


def _write_zip(archive_root_name, infos, filename, packed_envs, frontend):
    with zipfile.ZipFile(filename, 'w') as zf:
        for info in _leaf_infos(infos):
            arcname = os.path.join(archive_root_name, info.relative_path)
            frontend.info("  added %s" % arcname)
            zf.write(info.full_path, arcname=arcname)

        for pack in packed_envs:
            env_name = os.path.basename(pack)
            print('Joining packed env {}'.format(env_name))
            with zipfile.ZipFile(pack, mode='r') as env:
                with progressbar(env.infolist()) as infolist:
                    for file in infolist:
                        data = env.read(file)
                        zf.writestr(file, data)
                    env_spec = env_name.split('.')[0].split('_')[-1]
                    dot_packed = os.path.join(archive_root_name, 'envs', env_spec, 'conda-meta', '.packed')
                    zf.writestr(dot_packed, '{}\n'.format(current_platform()))


# function exported for project.py
def _list_relative_paths_for_unignored_project_files(project_directory, frontend, requirements):
    infos = _enumerate_archive_files(project_directory, frontend, requirements=requirements)
    if infos is None:
        return None
    return [info.relative_path for info in infos]


# function exported for project_ops.py
def _archive_project(project, filename, pack_envs=False):
    """Make an archive of the non-ignored files in the project.

    Args:
        project (``Project``): the project
        filename (str): name for the new zip or tar.gz archive file

    Returns:
        a ``Status``, if failed has ``errors``
    """
    failed = project.problems_status()
    if failed is not None:
        for error in failed.errors:
            project.frontend.error(error)
        return failed

    frontend = _new_error_recorder(project.frontend)

    if not os.path.exists(project.project_file.filename):
        frontend.error("%s does not exist." % project.project_file.basename)
        return SimpleStatus(success=False, description="Can't create an archive.", errors=frontend.pop_errors())

    # this would most likely happen in a GUI editor, if it reloaded
    # the project from memory but hadn't saved yet.
    if project.project_file.has_unsaved_changes:
        frontend.error("%s has been modified but not saved." % project.project_file.basename)
        return SimpleStatus(success=False, description="Can't create an archive.", errors=frontend.pop_errors())

    envs_path = os.path.join(project.project_file.project_dir, 'envs')

    packed_envs = []
    if pack_envs and os.path.isdir(envs_path):
        conda_pack_dir = tempfile.mkdtemp()
        import conda_pack
        for env in os.listdir(envs_path):
            ext = 'zip' if filename.lower().endswith(".zip") else 'tar'
            pack = os.path.join(conda_pack_dir, '{}_envs_{}.{}'.format(current_platform(), env, ext))
            zip_symlinks = True if ext == 'zip' else False
            fn = conda_pack.pack(prefix=os.path.join(envs_path, env),
                                 arcroot=os.path.join(project.name, 'envs', env),
                                 output=pack,
                                 zip_symlinks=zip_symlinks,
                                 verbose=True,
                                 force=True)
            packed_envs.append(fn)

    infos = _enumerate_archive_files(project.directory_path,
                                     frontend,
                                     requirements=project.union_of_requirements_for_all_envs)
    if infos is None:
        return SimpleStatus(success=False,
                            description="Failed to list files in the project.",
                            errors=frontend.pop_errors())

    # don't put the destination zip into itself, since it's fairly natural to
    # create a archive right in the project directory
    relative_dest_file = subdirectory_relative_to_directory(filename, project.directory_path)
    if not os.path.isabs(relative_dest_file):
        infos = [info for info in infos if info.relative_path != relative_dest_file]

    tmp_filename = filename + ".tmp-" + str(uuid.uuid4())
    try:
        if filename.lower().endswith(".zip"):
            _write_zip(project.name, infos, tmp_filename, packed_envs=packed_envs, frontend=frontend)
        elif filename.lower().endswith(".tar.gz"):
            _write_tar(project.name, infos, tmp_filename, compression="gz", packed_envs=packed_envs, frontend=frontend)
        elif filename.lower().endswith(".tar.bz2"):
            _write_tar(project.name, infos, tmp_filename, compression="bz2", packed_envs=packed_envs, frontend=frontend)
        elif filename.lower().endswith(".tar"):
            _write_tar(project.name, infos, tmp_filename, compression=None, packed_envs=packed_envs, frontend=frontend)
        else:
            frontend.error("Unsupported archive filename %s." % (filename))
            return SimpleStatus(success=False,
                                description="Project archive filename must be a .zip, .tar.gz, or .tar.bz2.",
                                errors=frontend.pop_errors())
        rename_over_existing(tmp_filename, filename)
    except IOError as e:
        frontend.error(str(e))
        return SimpleStatus(success=False,
                            description=("Failed to write project archive %s." % (filename)),
                            errors=frontend.pop_errors())
    finally:
        try:
            os.remove(tmp_filename)
            if pack_envs:
                os.remove(conda_pack_dir)
        except (IOError, OSError):
            pass

    unlocked = []
    for env_spec in project.env_specs.values():
        if env_spec.lock_set.disabled:
            unlocked.append(env_spec.name)

    if len(unlocked) > 0:
        frontend.info("Warning: env specs are not locked, which means they may not "
                      "work consistently for others or when deployed.")
        frontend.info("  Consider using the 'anaconda-project lock' command to lock the project.")
        if len(unlocked) != len(project.env_specs):
            frontend.info("  Unlocked env specs are: " + (", ".join(sorted(unlocked))))

    return SimpleStatus(success=True, description=("Created project archive %s" % filename))


def _list_files_zip(zip_path):
    with zipfile.ZipFile(zip_path, mode='r') as zf:
        return sorted(zf.namelist())


def _list_files_tar(tar_path):
    with tarfile.open(tar_path, mode='r') as tf:
        # we don't want links or block devices or anything weird, they could be a security problem
        return sorted([member.name for member in tf.getmembers() if member.isreg() or member.isdir()])


def _extractall_chmod(zf, destination):
    for zinfo in zf.infolist():
        out_path = zf.extract(zinfo.filename, path=destination)
        mode = zinfo.external_attr >> 16
        if not (mode == 0):
            os.chmod(out_path, mode)


def _extract_files_zip(zip_path, src_and_dest, frontend):
    # the zipfile API has no way to extract to a filename of
    # our choice, so we have to unpack to a temporary location,
    # then copy those files over.
    tmpdir = tempfile.mkdtemp()
    try:
        with zipfile.ZipFile(zip_path, mode='r') as zf:
            _extractall_chmod(zf, tmpdir)
            if isinstance(frontend.underlying, NullFrontend):
                src_and_dest = tqdm(src_and_dest, desc='Extract ')
            for (src, dest) in src_and_dest:
                frontend.info("Unpacking %s to %s" % (src, dest))
                src_path = os.path.join(tmpdir, src)
                if os.path.isdir(src_path):
                    makedirs_ok_if_exists(dest)
                    shutil.copystat(src_path, dest)
                else:
                    makedirs_ok_if_exists(os.path.dirname(dest))
                    shutil.copy2(src_path, dest)
    finally:
        try:
            shutil.rmtree(tmpdir)
        except (IOError, OSError):
            pass


def _extract_files_tar(tar_path, src_and_dest, frontend):
    with tarfile.open(tar_path, mode='r') as tf:
        if isinstance(frontend.underlying, NullFrontend):
            src_and_dest = tqdm(src_and_dest, desc='Extract ')
        for (src, dest) in src_and_dest:
            frontend.info("Unpacking %s to %s" % (src, dest))
            member = tf.getmember(src)
            # we could also use tf._extract_member here, but the
            # solution below with only the public API isn't that
            # bad.
            if member.isreg():
                makedirs_ok_if_exists(os.path.dirname(dest))
                tf.makefile(member, dest)
            else:
                assert member.isdir()  # we filtered out other types
                makedirs_ok_if_exists(dest)

            try:
                tf.chown(member, dest, False)  # pragma: no cover (python 3.5 has another param)
            except TypeError:  # pragma: no cover
                tf.chown(member, dest)  # pragma: no cover (python 2.7, 3.4)
            tf.chmod(member, dest)
            tf.utime(member, dest)


def _split_after_first(path):
    # starting from archive name, be sure we have a valid path for this OS
    path = path.replace("/", os.sep)

    def _helper(head, tail):
        (dirname, filename) = os.path.split(head)
        if dirname == '':
            # head had no separators, so return it as the first
            return (head, tail)
        elif tail is None:
            # we were called with no tail, so create the first tail
            return _helper(dirname, filename)
        else:
            # add filename to the tail
            return _helper(dirname, os.path.join(filename, tail))

    return _helper(path, None)


def _get_source_and_dest_files(archive_path, list_files, project_dir, parent_dir, frontend):

    names = list_files(archive_path)
    if len(names) == 0:
        frontend.error("A valid project archive must contain at least one file.")
        return None
    items = [(name, prefix, remainder)
             for (name, (prefix, remainder)) in zip(names, [_split_after_first(name) for name in names])]
    candidate_prefix = items[0][1]
    if candidate_prefix == "..":
        frontend.error("Archive contains relative path '%s' which is not allowed." % (items[0][0]))
        return None

    if project_dir is None:
        project_dir = candidate_prefix

    if os.path.isabs(project_dir):
        assert parent_dir is None
        canonical_project_dir = os.path.realpath(os.path.abspath(project_dir))
        canonical_parent_dir = os.path.dirname(canonical_project_dir)
    else:
        if parent_dir is None:
            parent_dir = os.getcwd()

        canonical_parent_dir = os.path.realpath(os.path.abspath(parent_dir))
        canonical_project_dir = os.path.realpath(os.path.abspath(os.path.join(canonical_parent_dir, project_dir)))

    # candidate_prefix is untrusted and may try to send us outside of parent_dir.
    # this assertion is because of the check for candidate_prefix == ".." above.
    assert canonical_project_dir.startswith(canonical_parent_dir)

    if os.path.exists(canonical_project_dir):
        if not os.path.isdir(canonical_project_dir) or os.listdir(canonical_project_dir):
            # This is an error to ensure we always do a "fresh" unpack
            # without worrying about overwriting stuff.
            frontend.error("Destination '%s' already exists and is not an empty directory." % canonical_project_dir)
            return None

    src_and_dest = []
    for (name, prefix, remainder) in items:
        if prefix != candidate_prefix:
            frontend.error(("A valid project archive contains only one project directory " +
                            "with all files inside that directory. '%s' is outside '%s'.") % (name, candidate_prefix))
            return None
        if remainder is None:
            # this is an entry that's either the prefix dir itself,
            # or a file at the root not in any dir
            continue
        dest = os.path.realpath(os.path.abspath(os.path.join(canonical_project_dir, remainder)))
        # this check deals with ".." in the name for example
        if not dest.startswith(canonical_project_dir):
            frontend.error("Archive entry '%s' would end up at '%s' which is outside '%s'." %
                           (name, dest, canonical_project_dir))
            return None
        src_and_dest.append((name, dest))

    return (canonical_project_dir, src_and_dest)


class _UnarchiveStatus(SimpleStatus):
    def __init__(self, success, description, project_dir):
        super(_UnarchiveStatus, self).__init__(success=success, description=description)
        self.project_dir = project_dir


# function exported for project_ops.py
def _unarchive_project(archive_filename, project_dir, frontend, parent_dir=None):
    """Unpack an archive of files in the project.

    This takes care of several details, for example it deals with
    hostile archives containing files outside of the dest
    directory, and it handles both tar and zip.

    It does not load or validate the unpacked project.

    project_dir can be None to auto-choose one.

    If parent_dir is non-None, place the project_dir in it. This is most useful
    if project_dir is None.

    Args:
        archive_filename (str): the tar or zip archive file
        project_dir (str): the directory that will contain the project config file
        parent_dir (str): place project directory in here

    Returns:
        a ``Status``, if failed has ``errors``, on success has a ``project_dir`` property
    """
    if project_dir is not None and os.path.isabs(project_dir) and parent_dir is not None:
        raise ValueError("If supplying parent_dir to unarchive, project_dir must be relative or None")

    frontend = _new_error_recorder(frontend)

    list_files = None
    extract_files = None
    if archive_filename.endswith(".zip"):
        list_files = _list_files_zip
        extract_files = _extract_files_zip
    elif any([archive_filename.endswith(suffix) for suffix in [".tar", ".tar.gz", ".tar.bz2"]]):
        list_files = _list_files_tar
        extract_files = _extract_files_tar
    else:
        frontend.error("Unsupported archive filename %s, must be a .zip, .tar.gz, or .tar.bz2" % (archive_filename))
        return SimpleStatus(success=False,
                            description=("Could not unpack archive %s" % archive_filename),
                            errors=frontend.pop_errors())

    try:
        result = _get_source_and_dest_files(archive_filename, list_files, project_dir, parent_dir, frontend)
        if result is None:
            return SimpleStatus(success=False,
                                description=("Could not unpack archive %s" % archive_filename),
                                errors=frontend.pop_errors())
        (canonical_project_dir, src_and_dest) = result

        if len(src_and_dest) == 0:
            frontend.error("Archive does not contain a project directory or is empty.")
            return SimpleStatus(success=False,
                                description=("Could not unpack archive %s" % archive_filename),
                                errors=frontend.pop_errors())

        if not os.path.exists(canonical_project_dir):
            os.makedirs(canonical_project_dir)

        try:
            extract_files(archive_filename, src_and_dest, frontend)
        except Exception as e:
            try:
                shutil.rmtree(canonical_project_dir)
            except (IOError, OSError):
                pass
            raise e

        return _UnarchiveStatus(success=True,
                                description=("Project archive unpacked to %s." % canonical_project_dir),
                                project_dir=canonical_project_dir)
    except (IOError, OSError, zipfile.error, tarfile.TarError) as e:
        frontend.error(str(e))
        return SimpleStatus(success=False, description="Failed to read project archive.", errors=frontend.pop_errors())
