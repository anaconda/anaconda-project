# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""YAML file loading and manipulation."""
from __future__ import absolute_import

# ruamel.yaml supports round-trip preserving dict ordering,
# comments, etc., which is why we use it instead of the usual yaml
# module. Remember the project file is intended to go into source
# control.
import ruamel.yaml as ryaml
from ruamel.yaml.error import YAMLError
import codecs
import errno
import os
import sys
import uuid

from anaconda_project.internal.makedirs import makedirs_ok_if_exists
from anaconda_project.internal.rename import rename_over_existing


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


class YamlFile(object):
    """Abstract YAML file, base class for ``ProjectFile`` and ``LocalStateFile``.

    Be careful with creating your own instance of this class,
    because you have to think about when other code might load or
    save in a way that conflicts with your loads and saves.

    """

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
        self._dirty = False
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
        self._change_count = self._change_count + 1

        # using RoundTripLoader incorporates safe_load
        # (we don't load code)
        assert issubclass(ryaml.RoundTripLoader, ryaml.constructor.SafeConstructor)
        try:
            with codecs.open(self.filename, 'r', 'utf-8') as file:
                contents = file.read()
            self._yaml = ryaml.load(contents, Loader=ryaml.RoundTripLoader)
            self._dirty = False
        except IOError as e:
            if e.errno == errno.ENOENT:
                self._yaml = None
            else:
                raise e
        except YAMLError as e:
            self._corrupted = True
            self._corrupted_error_message = str(e)
            self._yaml = None

        if self._yaml is None:
            self._yaml = self._default_content()
            self._dirty = True

    def _default_comment(self):
        return "yaml file"

    def _default_content(self):
        # ruamel.yaml returns None if you load an empty file,
        # so we have to build this ourselves
        from ruamel.yaml.comments import CommentedMap
        root = CommentedMap()
        root.yaml_set_start_comment(self._default_comment())
        return root

    def _throw_if_corrupted(self):
        if self._corrupted:
            raise ValueError("Cannot modify corrupted YAML file %s\n%s" %
                             (self.filename, self._corrupted_error_message))

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
    def change_count(self):
        """Get the number of times we've resynced with the file on disk (reloaded or saved changes).

        This is used for cache invalidation. If a cached value becomes invalid whenever
        ``change_count`` increments, then the cached value will be recomputed whenever
        we save new changes or reload the file.
        """
        return self._change_count

    def save(self):
        """Write the file to disk, only if any changes have been made.

        Raises ``IOError`` if it fails for some reason.

        Returns:
            None
        """
        self._throw_if_corrupted()

        if not self._dirty:
            return

        contents = ryaml.dump(self._yaml, Dumper=ryaml.RoundTripDumper)

        try:
            # This is to ensure we don't corrupt the file, even if ruamel.yaml is broken
            ryaml.load(contents, Loader=ryaml.RoundTripLoader)
        except YAMLError as e:  # pragma: no cover (should not happen)
            print("ruamel.yaml bug; it failed to parse a file that it generated.", file=sys.stderr)
            print("  the parse error was: " + str(e), file=sys.stderr)
            print("Generated file was:", file=sys.stderr)
            print(contents, file=sys.stderr)
            raise RuntimeError("Bug in ruamel.yaml library; failed to parse a file that it generated: " + str(e))

        if not os.path.isfile(self.filename):
            # might have to make the directory
            dirname = os.path.dirname(self.filename)
            makedirs_ok_if_exists(dirname)
        _atomic_replace(self.filename, contents)
        self._change_count = self._change_count + 1
        self._dirty = False

    def transform_yaml(self, transformer):
        """Modify the YAML parse tree.

        This allows you to modify the YAML parse tree directly;
        the transformer function receives the parse tree. It
        should return True to block marking the ``YamlFile``
        dirty, that is, return True if the transformer didn't make
        any changes after all. Return False or None if changes
        were made.

        This method does not save the file, call ``save()`` to do that.

        Args:
            transformer (function): takes 1 parameter (the yaml tree) and returns True if it was NOT modified
        Returns:
            None

        """
        self._throw_if_corrupted()

        result = transformer(self._yaml)
        if result is not True:
            self._dirty = True

    @classmethod
    def _path(cls, path):
        if isinstance(path, str):
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
                current[p] = dict()
                self._dirty = True

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
        self._dirty = True

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
            self._dirty = True

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
