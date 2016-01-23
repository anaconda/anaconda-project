from __future__ import absolute_import

# ruamel.yaml supports round-trip preserving dict ordering,
# comments, etc., which is why we use it instead of the usual yaml
# module. Remember the project file is intended to go into source
# control.
import ruamel.yaml as ryaml
import codecs
import errno
import os


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
        self.load()

    def load(self):
        # using RoundTripLoader incorporates safe_load
        # (we don't load code)
        assert issubclass(ryaml.RoundTripLoader, ryaml.constructor.SafeConstructor)
        try:
            with codecs.open(self.filename, 'r', 'utf-8') as file:
                contents = file.read()
            self.yaml = ryaml.load(contents, Loader=ryaml.RoundTripLoader)
        except IOError as e:
            if e.errno == errno.ENOENT:
                # ruamel.yaml returns None if you load an empty file,
                # so we have to build this ourselves
                from ruamel.yaml.comments import CommentedMap
                self.yaml = CommentedMap()
                self.yaml.yaml_set_start_comment("Anaconda project file")
            else:
                raise e

    def save(self):
        contents = ryaml.dump(self.yaml, Dumper=ryaml.RoundTripDumper)
        _atomic_replace(self.filename, contents)

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

            current = current[p]
        return current

    def set_values(self, section_path, values):
        existing = self._ensure_section(section_path)
        for k, v in values.items():
            existing[k] = v

    def set_value(self, section_path, key, value):
        existing = self._ensure_section(section_path)
        existing[key] = value

    def get_value(self, section_path, key=None, default=None):
        existing = self._get_section_or_none(section_path)
        if existing is None:
            return default
        elif key is None:
            return existing
        else:
            return existing.get(key, default)

# use .yml not .yaml to make Windows happy
PROJECT_FILENAME = "project.yml"


class ProjectFile(YamlFile):
    @classmethod
    def ensure_for_directory(cls, directory, requirement_registry):
        path = os.path.join(directory, PROJECT_FILENAME)
        project_file = ProjectFile(path, requirement_registry)
        if not os.path.exists(path):
            project_file.save()
        return project_file

    @classmethod
    def load_for_directory(cls, directory, requirement_registry):
        path = os.path.join(directory, PROJECT_FILENAME)
        return ProjectFile(path, requirement_registry)

    def __init__(self, filename, requirement_registry):
        self.requirement_registry = requirement_registry
        super(ProjectFile, self).__init__(filename)

    def load(self):
        super(ProjectFile, self).load()
        requirements = []
        problems = []
        runtime = self.get_value("runtime")
        # runtime: section can contain a list of var names
        # or a dict from var names to options
        if isinstance(runtime, dict):
            for key in runtime.keys():
                options = runtime[key]
                if isinstance(options, dict):
                    requirement = self.requirement_registry.find_by_env_var(key, options)
                    requirements.append(requirement)
                else:
                    problems.append(("runtime section has key {key} with value {options}; the value " +
                                     "must be a dict of options, instead.").format(key=key,
                                                                                   options=options))
        elif isinstance(runtime, list):
            for item in runtime:
                if isinstance(item, str):
                    requirement = self.requirement_registry.find_by_env_var(item, options=dict())
                    requirements.append(requirement)
                else:
                    problems.append(
                        "runtime section should contain environment variable names, {item} is not a string".format(
                            item=item))
        else:
            problems.append(
                "runtime section contains wrong value type {runtime}, should be dict or list of requirements".format(
                    runtime=runtime))

        self._requirements = requirements
        self._problems = problems

    @property
    def requirements(self):
        return self._requirements

    @property
    def problems(self):
        return self._problems
