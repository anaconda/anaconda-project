from __future__ import absolute_import

# ruamel.yaml supports round-trip preserving dict ordering,
# comments, etc., which is why we use it instead of the usual yaml
# module. Remember the project file is intended to go into source
# control.
import ruamel.yaml as ryaml
import codecs
import errno
import os

from project.internal.makedirs import makedirs_ok_if_exists


def _atomic_replace(path, contents, encoding='utf-8'):
    tmp = path + ".tmp"
    try:
        with codecs.open(tmp, 'w', encoding) as file:
            file.write(contents)
            file.flush()
            file.close()
        # on windows this may not work, we will see
        os.rename(tmp, path)
    finally:
        try:
            os.remove(tmp)
        except (IOError, OSError):
            pass


class YamlFile(object):
    def __init__(self, filename):
        self.filename = filename
        self._dirty = False
        self.load()

    def load(self):
        # using RoundTripLoader incorporates safe_load
        # (we don't load code)
        assert issubclass(ryaml.RoundTripLoader, ryaml.constructor.SafeConstructor)
        try:
            with codecs.open(self.filename, 'r', 'utf-8') as file:
                contents = file.read()
            self.yaml = ryaml.load(contents, Loader=ryaml.RoundTripLoader)
            self._dirty = False
        except IOError as e:
            if e.errno == errno.ENOENT:
                self.yaml = None
            else:
                raise e

        if self.yaml is None:
            # ruamel.yaml returns None if you load an empty file,
            # so we have to build this ourselves
            from ruamel.yaml.comments import CommentedMap
            self.yaml = CommentedMap()
            self.yaml.yaml_set_start_comment(self._default_comment())
            self._dirty = True

    def _default_comment(self):
        return "yaml file"

    def save(self):
        if not self._dirty:
            return

        contents = ryaml.dump(self.yaml, Dumper=ryaml.RoundTripDumper)
        if not os.path.isfile(self.filename):
            # might have to make the directory
            dirname = os.path.dirname(self.filename)
            makedirs_ok_if_exists(dirname)
        _atomic_replace(self.filename, contents)
        self._dirty = False

    def _get_section_or_none(self, section_path):
        pieces = section_path.split(".")
        current = self.yaml
        for p in pieces:
            if p in current:
                current = current[p]
            else:
                return None
        return current

    def _ensure_section(self, section_path):
        pieces = section_path.split(".")
        current = self.yaml
        for p in pieces:
            if p not in current:
                current[p] = dict()
                self._dirty = True

            current = current[p]
        return current

    def set_values(self, section_path, values):
        existing = self._ensure_section(section_path)
        for k, v in values.items():
            existing[k] = v
            self._dirty = True

    def set_value(self, section_path, key, value):
        existing = self._ensure_section(section_path)
        existing[key] = value
        self._dirty = True

    def get_value(self, section_path, key=None, default=None):
        existing = self._get_section_or_none(section_path)
        if existing is None:
            return default
        elif key is None:
            return existing
        else:
            return existing.get(key, default)
