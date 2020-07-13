# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""YAML file loading and manipulation."""
from __future__ import absolute_import, print_function

# ruamel.yaml supports round-trip preserving dict ordering,
# comments, etc., which is why we use it instead of the usual yaml
# module. Remember the project file is intended to go into source
# control.
try:
    # this is the conda-packaged version of ruamel.yaml which has the
    # module renamed
    import ruamel_yaml as ryaml
    from ruamel_yaml.error import YAMLError
    from ruamel_yaml.comments import CommentedMap
    from ruamel_yaml.comments import CommentedSeq
except ImportError:  # pragma: no cover
    # this is the upstream version
    import ruamel.yaml as ryaml  # pragma: no cover
    from ruamel.yaml.error import YAMLError  # pragma: no cover
    from ruamel.yaml.comments import CommentedMap  # pragma: no cover
    from ruamel.yaml.comments import CommentedSeq  # pragma: no cover

import codecs
import errno
import os
import sys
import uuid

from anaconda_project.internal.makedirs import makedirs_ok_if_exists
from anaconda_project.internal.rename import rename_over_existing
from anaconda_project.internal.py2_compat import is_string

# We use this in other files (to abstract over the imports above)
_YAMLError = YAMLError
_CommentedMap = CommentedMap
_CommentedSeq = CommentedSeq


def _atomic_replace(path, contents, encoding='utf-8'):
    tmp = path + ".tmp-" + str(uuid.uuid4())
    try:
        with codecs.open(tmp, 'w', encoding) as file:
            file.write(contents)
            file.flush()
            file.close()
        rename_over_existing(tmp, path)
    finally:
        try:
            os.remove(tmp)
        except (IOError, OSError):
            pass


def _load_string(contents):
    if contents.strip() == '':
        # ryaml.load below returns None for an empty file, we want
        # to return an empty dict instead.
        return {}
    else:
        # using RoundTripLoader incorporates safe_load
        # (we don't load code)
        assert issubclass(ryaml.RoundTripLoader, ryaml.constructor.SafeConstructor)
        return ryaml.load(contents, Loader=ryaml.RoundTripLoader)


def _dump_string(yaml):
    return ryaml.dump(yaml, Dumper=ryaml.RoundTripDumper)


def _save_file(yaml, filename, contents=None):
    if contents is None:
        contents = _dump_string(yaml)

    try:
        # This is to ensure we don't corrupt the file, even if ruamel.yaml is broken
        ryaml.load(contents, Loader=ryaml.RoundTripLoader)
    except YAMLError as e:  # pragma: no cover (should not happen)
        print("ruamel.yaml bug; it failed to parse a file that it generated.", file=sys.stderr)
        print("  the parse error was: " + str(e), file=sys.stderr)
        print("Generated file was:", file=sys.stderr)
        print(contents, file=sys.stderr)
        raise RuntimeError("Bug in ruamel.yaml library; failed to parse a file that it generated: " + str(e))

    if not os.path.isfile(filename):
        # might have to make the directory
        dirname = os.path.dirname(filename)
        makedirs_ok_if_exists(dirname)
    _atomic_replace(filename, contents)


def _block_style_all_nodes(yaml):
    if hasattr(yaml, 'fa'):
        yaml.fa.set_block_style()

    if isinstance(yaml, list):
        for element in yaml:
            _block_style_all_nodes(element)
    elif isinstance(yaml, dict):
        for value in yaml.values():
            _block_style_all_nodes(value)


class YamlFile(object):
    """Abstract YAML file, base class for ``ProjectFile`` and ``LocalStateFile``.

    Be careful with creating your own instance of this class,
    because you have to think about when other code might load or
    save in a way that conflicts with your loads and saves.

    """

    # The dummy entry works around a bug/quirk in ruamel.yaml that drops the
    # top comment for an empty dictionary
    template = '# yaml file\n__dummy__: dummy'

    def __init__(self, filename):
        """Load a YamlFile with the given filename.

        Raises an exception on an IOError, but if the file is
        missing this succeeds (then creates the file if and when
        you call ``save()``).

        If the file has syntax problems, this sets the
        ``corrupted`` and ``corrupted_error_message`` properties,
        and attempts to modify the file will raise an
        exception.

        """
        self.filename = filename
        self._previous_content = ""
        self._change_count = 0
        self.load()

    def load(self):
        """Reload the file from disk, discarding any unsaved changes.

        If the file has syntax problems, this sets the
        ``corrupted`` and ``corrupted_error_message`` properties,
        and attempts to modify the file will raise an
        exception.

        Returns:
            None
        """
        self._corrupted = False
        self._corrupted_error_message = None
        self._corrupted_maybe_line = None
        self._corrupted_maybe_column = None
        self._change_count = self._change_count + 1

        try:
            with codecs.open(self.filename, 'r', 'utf-8') as file:
                contents = file.read()
            self._yaml = _load_string(contents)

            # we re-dump instead of using "contents" because
            # when loading a hand-edited file, we may reformat
            # in trivial ways because our round-tripping isn't perfect,
            # and we don't want to count those trivial reformats as
            # a reason to save.
            self._previous_content = _dump_string(self._yaml)
        except IOError as e:
            if e.errno == errno.ENOENT:
                self._yaml = None
            else:
                raise e
        except YAMLError as e:
            self._corrupted = True
            self._corrupted_error_message = str(e)
            # Not sure all this paranoia is needed
            # about whether these values really exist,
            # but hard to prove it isn't.
            mark = getattr(e, 'problem_mark', None)
            if mark is not None:
                if mark.line is not None and mark.line >= 0:
                    self._corrupted_maybe_line = mark.line
                if mark.column is not None and mark.column >= 0:
                    self._corrupted_maybe_column = mark.column
            self._yaml = None

        if self._yaml is None:
            if self._corrupted:
                # don't want to throw exceptions if people get_value()
                # so stick an empty dict in here
                self._yaml = dict()
            else:
                self._yaml = self._load_template()
                self._fill_default_content(self._yaml)
                # make it pretty
                _block_style_all_nodes(self._yaml)
                if not self._save_default_content():
                    # pretend we already saved
                    self._previous_content = _dump_string(self._yaml)

    def _load_template(self):
        # ruamel.yaml returns None if you load an empty file,
        # so we have to build this ourselves
        assert self.template is not None
        result = _load_string(self.template.lstrip())
        # ruamel.yaml doesn't preserve a header comment for an empty dictionary.
        # To work around this we add a dummy element in the template, then we
        # delete that element to obtain an empty map
        result.pop('__dummy__', None)
        return result

    def _fill_default_content(self, template):
        pass

    def _save_default_content(self):
        """Override to change whether we consider a default, unmodified file dirty."""
        return True

    def _throw_if_corrupted(self):
        if self._corrupted:
            raise ValueError("Cannot modify corrupted YAML file %s\n%s" %
                             (self.filename, self._corrupted_error_message))

    @property
    def basename(self):
        """Basename of the filename."""
        return os.path.basename(self.filename)

    @property
    def corrupted(self):
        """Get whether the file is corrupted.

        A corrupted file has a syntax error so we can't modify and save it.
        See ``corrupted_error_message`` for what's wrong with it.

        Returns:
            True if file is corrupted.
        """
        return self._corrupted

    @property
    def corrupted_error_message(self):
        """Get the error message if file is corrupted, or None if it isn't.

        Use this to display the problem if the file is corrupted.

        Returns:
            Corruption message or None.
        """
        return self._corrupted_error_message

    @property
    def corrupted_maybe_line(self):
        """Get the line number for syntax error, or None if unavailable.

        Returns:
            Corruption line or None.
        """
        return self._corrupted_maybe_line

    @property
    def corrupted_maybe_column(self):
        """Get the column for syntax error, or None if unavailable.

        Returns:
            Corruption column or None.
        """
        return self._corrupted_maybe_column

    @property
    def change_count(self):
        """Get the number of times we've resynced with the file on disk (reloaded or saved changes).

        This is used for cache invalidation. If a cached value becomes invalid whenever
        ``change_count`` increments, then the cached value will be recomputed whenever
        we save new changes or reload the file.
        """
        return self._change_count

    @property
    def has_unsaved_changes(self):
        """Get whether changes are all saved."""
        # this is a fairly expensive check
        return self._previous_content != _dump_string(self._yaml)

    def use_changes_without_saving(self):
        """Apply any in-memory changes as if we'd saved, but don't actually save.

        This is used to "try out" a change before we save it. We can load()
        to undo our changes.
        """
        self._change_count = self._change_count + 1

    def save(self):
        """Write the file to disk, only if any changes have been made.

        Raises ``IOError`` if it fails for some reason.

        Returns:
            None
        """
        self._throw_if_corrupted()

        contents = _dump_string(self._yaml)
        if contents != self._previous_content:
            _save_file(self._yaml, self.filename, contents)
            self._change_count = self._change_count + 1
            self._previous_content = contents

    @classmethod
    def _path(cls, path):
        if is_string(path):
            return (path, )
        else:
            try:
                return list(element for element in path)
            except TypeError:
                raise ValueError("YAML file path must be a string or an iterable of strings")

    def _get_dict_or_none(self, pieces):
        current = self._yaml
        for p in pieces:
            if p in current and isinstance(current[p], dict):
                current = current[p]
            else:
                return None
        return current

    def _ensure_dicts_at_path(self, pieces):
        self._throw_if_corrupted()

        current = self._yaml
        for p in pieces:
            if p not in current or not isinstance(current[p], dict):
                # It's important to use CommentedMap because it preserves
                # order.
                current[p] = CommentedMap()
                _block_style_all_nodes(current[p])

            current = current[p]
        return current

    def set_value(self, path, value):
        """Set a single value at the given path.

        Overwrites any existing value at the path.

        This method does not save the file, call ``save()`` to do that.

        Args:
            path (str or list of str): single key, or list of nested keys
            value: any YAML-compatible value type
        """
        self._throw_if_corrupted()

        path = self._path(path)
        existing = self._ensure_dicts_at_path(path[:-1])
        existing[path[-1]] = value

    def unset_value(self, path):
        """Remove a single value at the given path.

        This method does not save the file, call ``save()`` to do that.

        Args:
            path (str or list of str): single key, or list of nested keys
        """
        self._throw_if_corrupted()

        path = self._path(path)

        existing = self._get_dict_or_none(path[:-1])
        key = path[-1]
        if existing is not None and key in existing:
            del existing[key]

    def get_value(self, path, default=None):
        """Get a single value from the YAML file.

        Args:
            path (str or list of str): single key, or list of nested keys
            default: any YAML-compatible value type

        Returns:
            the value from the file or the provided default
        """
        path = self._path(path)
        existing = self._get_dict_or_none(path[:-1])
        if existing is None:
            return default
        else:
            return existing.get(path[-1], default)

    @property
    def root(self):
        """Get the outermost value from the yaml file."""
        self._throw_if_corrupted()

        return self._yaml
