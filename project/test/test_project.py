from __future__ import absolute_import, print_function

from copy import deepcopy
import os
import stat
import subprocess

import pytest

from project.test.environ_utils import minimal_environ
from project.internal.test.tmpfile_utils import with_directory_contents
from project.test.project_utils import project_no_dedicated_env
from project.plugins.registry import PluginRegistry
from project.plugins.requirement import EnvVarRequirement
from project.plugins.requirements.conda_env import CondaEnvRequirement
from project.project_file import PROJECT_FILENAME
from project.conda_meta_file import META_DIRECTORY, META_FILENAME


def test_properties():
    def check_properties(dirname):
        project = project_no_dedicated_env(dirname)
        assert dirname == project.directory_path
        assert dirname == os.path.dirname(project.project_file.filename)
        assert dirname == os.path.dirname(os.path.dirname(project.conda_meta_file.filename))
        assert project.name == os.path.basename(dirname)
        assert project.version == "unknown"
        assert project.problems == []

    with_directory_contents(dict(), check_properties)


def test_ignore_trailing_slash_on_dirname():
    def check_properties(dirname):
        project = project_no_dedicated_env(dirname + "/")
        assert dirname == project.directory_path
        assert dirname == os.path.dirname(project.project_file.filename)
        assert dirname == os.path.dirname(os.path.dirname(project.conda_meta_file.filename))
        assert project.name == os.path.basename(dirname)
        assert project.version == "unknown"
        assert project.problems == []

    with_directory_contents(dict(), check_properties)


def test_single_env_var_requirement():
    def check_some_env_var(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        assert 2 == len(project.requirements)
        assert "FOO" == project.requirements[0].env_var
        assert "CONDA_ENV_PATH" == project.requirements[1].env_var

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  FOO: {}
"""}, check_some_env_var)


def test_problem_in_project_file():
    def check_problem(dirname):
        project = project_no_dedicated_env(dirname)
        assert 0 == len(project.requirements)
        assert 1 == len(project.problems)

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  42
"""}, check_problem)


def test_single_env_var_requirement_with_options():
    def check_some_env_var(dirname):
        project = project_no_dedicated_env(dirname)
        assert 2 == len(project.requirements)
        assert "FOO" == project.requirements[0].env_var
        assert dict(default="hello") == project.requirements[0].options
        assert "CONDA_ENV_PATH" == project.requirements[1].env_var

    with_directory_contents({PROJECT_FILENAME: """
runtime:
    FOO: { default: "hello" }
"""}, check_some_env_var)


def test_override_plugin_registry():
    def check_override_plugin_registry(dirname):
        registry = PluginRegistry()
        project = project_no_dedicated_env(dirname, registry)
        assert project._config_cache.registry is registry

    with_directory_contents({PROJECT_FILENAME: """
runtime:
  FOO: {}
"""}, check_override_plugin_registry)


def test_get_name_and_version_from_conda_meta_yaml():
    def check_conda_meta(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.name == "foo"
        assert project.version == "1.2.3"

    with_directory_contents(
        {
            META_DIRECTORY + "/" + META_FILENAME: """
package:
  name: foo
  version: 1.2.3
"""
        }, check_conda_meta)


def test_get_name_and_version_from_project_file():
    def check_name_and_version(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.name == "foo"
        assert project.version == "1.2.3"

        assert project.conda_meta_file.name == "from_meta"
        assert project.conda_meta_file.version == "1.2.3meta"

    with_directory_contents(
        {PROJECT_FILENAME: """
package:
  name: foo
  version: 1.2.3
    """,
         META_DIRECTORY + "/" + META_FILENAME: """
package:
  name: from_meta
  version: 1.2.3meta
"""}, check_name_and_version)


def test_set_name_and_version_in_project_file():
    def check_name_and_version(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.name == "foo"
        assert project.version == "1.2.3"

        project.project_file.name = "bar"
        project.project_file.version = "4.5.6"
        assert project.name == "bar"
        assert project.version == "4.5.6"
        project.project_file.save()

        project2 = project_no_dedicated_env(dirname)
        assert project2.name == "bar"
        assert project2.version == "4.5.6"

    with_directory_contents(
        {PROJECT_FILENAME: """
package:
  name: foo
  version: 1.2.3
    """}, check_name_and_version)


def test_get_package_requirements_from_project_file():
    def check_get_packages(dirname):
        project = project_no_dedicated_env(dirname)
        env = project.conda_environments['default']
        assert env.name == 'default'
        assert ("foo", "hello >= 1.0", "world") == env.dependencies
        assert set(["foo", "hello", "world"]) == env.conda_package_names_set

        # find CondaEnvRequirement
        conda_env_req = None
        for r in project.requirements:
            if isinstance(r, CondaEnvRequirement):
                assert conda_env_req is None  # only one
                conda_env_req = r
        assert len(conda_env_req.environments) == 1
        assert 'default' in conda_env_req.environments
        assert conda_env_req.environments['default'] is env

    with_directory_contents(
        {PROJECT_FILENAME: """
dependencies:
  - foo
  - hello >= 1.0
  - world
    """}, check_get_packages)


def test_use_env_options_when_packages_also_specified():
    def check_get_packages(dirname):
        project = project_no_dedicated_env(dirname)

        # find CondaEnvRequirement
        conda_env_req = None
        for r in project.requirements:
            if isinstance(r, CondaEnvRequirement):
                assert conda_env_req is None  # only one
                conda_env_req = r

        assert conda_env_req.options == dict(hello=42)

    with_directory_contents(
        {PROJECT_FILENAME: """
runtime:
  CONDA_ENV_PATH: { hello: 42 }

dependencies:
  - foo
  - hello >= 1.0
  - world
    """}, check_get_packages)


def test_get_package_requirements_from_empty_project():
    def check_get_packages(dirname):
        project = project_no_dedicated_env(dirname)
        assert () == project.conda_environments['default'].dependencies

    with_directory_contents({PROJECT_FILENAME: ""}, check_get_packages)


def test_complain_about_dependencies_not_a_list():
    def check_get_packages(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        "should be a list of strings not 'CommentedMap" in project.problems[0]

    with_directory_contents({PROJECT_FILENAME: """
dependencies:
    foo: bar
    """}, check_get_packages)


def test_load_environments():
    def check_environments(dirname):
        project = project_no_dedicated_env(dirname)
        assert 0 == len(project.problems)
        assert len(project.conda_environments) == 2
        assert 'foo' in project.conda_environments
        assert 'bar' in project.conda_environments
        assert project.default_conda_environment_name == 'foo'
        foo = project.conda_environments['foo']
        bar = project.conda_environments['bar']
        assert foo.dependencies == ('python', 'dog', 'cat', 'zebra')
        assert bar.dependencies == ()

    with_directory_contents(
        {PROJECT_FILENAME: """
environments:
  foo:
    dependencies:
       - python
       - dog
       - cat
       - zebra
  bar: {}
    """}, check_environments)


def test_load_environments_merging_in_global():
    def check_environments(dirname):
        project = project_no_dedicated_env(dirname)
        assert 0 == len(project.problems)
        assert len(project.conda_environments) == 2
        assert 'foo' in project.conda_environments
        assert 'bar' in project.conda_environments
        assert project.default_conda_environment_name == 'foo'
        foo = project.conda_environments['foo']
        bar = project.conda_environments['bar']
        assert foo.dependencies == ('dead-parrot', 'elephant', 'python', 'dog', 'cat', 'zebra')
        assert bar.dependencies == ('dead-parrot', 'elephant')

    with_directory_contents(
        {PROJECT_FILENAME: """
dependencies:
  - dead-parrot
  - elephant

environments:
  foo:
    dependencies:
       - python
       - dog
       - cat
       - zebra
  bar: {}
    """}, check_environments)


def test_load_environments_default_always_default_even_if_not_first():
    def check_environments(dirname):
        project = project_no_dedicated_env(dirname)
        assert 0 == len(project.problems)
        assert len(project.conda_environments) == 3
        assert 'foo' in project.conda_environments
        assert 'bar' in project.conda_environments
        assert 'default' in project.conda_environments
        assert project.default_conda_environment_name == 'default'
        foo = project.conda_environments['foo']
        bar = project.conda_environments['bar']
        default = project.conda_environments['default']
        assert foo.dependencies == ()
        assert bar.dependencies == ()
        assert default.dependencies == ()

    with_directory_contents(
        {PROJECT_FILENAME: """
environments:
  foo: {}
  bar: {}
  default: {}
    """}, check_environments)


def test_complain_about_environments_not_a_dict():
    def check_environments(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        "should be a directory from environment name to environment attributes, not 42" in project.problems[0]

    with_directory_contents({PROJECT_FILENAME: """
environments: 42
    """}, check_environments)


def test_complain_about_dependencies_list_of_wrong_thing():
    def check_get_packages(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        "should be a string not '42'" in project.problems[0]

    with_directory_contents({PROJECT_FILENAME: """
dependencies:
    - 42
    """}, check_get_packages)


def test_load_list_of_runtime_requirements():
    def check_file(dirname):
        filename = os.path.join(dirname, PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        requirements = project.requirements
        assert 3 == len(requirements)
        assert isinstance(requirements[0], EnvVarRequirement)
        assert 'FOO' == requirements[0].env_var
        assert isinstance(requirements[1], EnvVarRequirement)
        assert 'BAR' == requirements[1].env_var
        assert isinstance(requirements[2], CondaEnvRequirement)
        assert 'CONDA_ENV_PATH' == requirements[2].env_var
        assert dict() == requirements[2].options
        assert len(project.problems) == 0

    with_directory_contents({PROJECT_FILENAME: "runtime:\n  - FOO\n  - BAR\n"}, check_file)


def test_load_dict_of_runtime_requirements():
    def check_file(dirname):
        filename = os.path.join(dirname, PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        requirements = project.requirements
        assert 3 == len(requirements)
        assert isinstance(requirements[0], EnvVarRequirement)
        assert 'FOO' == requirements[0].env_var
        assert dict(a=1) == requirements[0].options
        assert isinstance(requirements[1], EnvVarRequirement)
        assert 'BAR' == requirements[1].env_var
        assert dict(b=2) == requirements[1].options
        assert isinstance(requirements[2], CondaEnvRequirement)
        assert 'CONDA_ENV_PATH' == requirements[2].env_var
        assert dict() == requirements[2].options
        assert len(project.problems) == 0

    with_directory_contents({PROJECT_FILENAME: "runtime:\n  FOO: { a: 1 }\n  BAR: { b: 2 }\n"}, check_file)


def test_non_string_runtime_requirements():
    def check_file(dirname):
        filename = os.path.join(dirname, PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = project_no_dedicated_env(dirname)
        assert 2 == len(project.problems)
        assert 0 == len(project.requirements)
        assert "42 is not a string" in project.problems[0]
        assert "43 is not a string" in project.problems[1]

    with_directory_contents({PROJECT_FILENAME: "runtime:\n  - 42\n  - 43\n"}, check_file)


def test_bad_runtime_requirements_options():
    def check_file(dirname):
        filename = os.path.join(dirname, PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = project_no_dedicated_env(dirname)
        assert 2 == len(project.problems)
        assert 0 == len(project.requirements)
        assert "key FOO with value 42; the value must be a dict" in project.problems[0]
        assert "key BAR with value baz; the value must be a dict" in project.problems[1]

    with_directory_contents({PROJECT_FILENAME: "runtime:\n  FOO: 42\n  BAR: baz\n"}, check_file)


def test_runtime_requirements_not_a_collection():
    def check_file(dirname):
        filename = os.path.join(dirname, PROJECT_FILENAME)
        assert os.path.exists(filename)
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        assert 0 == len(project.requirements)
        assert "runtime section contains wrong value type 42" in project.problems[0]

    with_directory_contents({PROJECT_FILENAME: "runtime:\n  42\n"}, check_file)


def test_corrupted_project_file_and_meta_file():
    def check_problem(dirname):
        project = project_no_dedicated_env(dirname)
        assert 0 == len(project.requirements)
        assert 2 == len(project.problems)
        assert 'project.yml has a syntax error that needs to be fixed by hand' in project.problems[0]
        assert 'meta.yaml has a syntax error that needs to be fixed by hand' in project.problems[1]

    with_directory_contents(
        {PROJECT_FILENAME: """
^
runtime:
  FOO
""",
         META_DIRECTORY + "/" + META_FILENAME: """
^
package:
  name: foo
  version: 1.2.3
"""}, check_problem)


def test_non_dict_meta_yaml_app_entry():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert project.conda_meta_file.app_entry == 42
        assert 1 == len(project.problems)
        expected_error = "%s: app: entry: should be a string not '%r'" % (project.conda_meta_file.filename, 42)
        assert expected_error == project.problems[0]

    with_directory_contents({META_DIRECTORY + "/" + META_FILENAME: "app:\n  entry: 42\n"}, check_app_entry)


def test_non_dict_commands_section():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: 'commands:' section should be a dictionary from command names to attributes, not %r" % (
            project.project_file.filename, 42)
        assert expected_error == project.problems[0]

    with_directory_contents({PROJECT_FILENAME: "commands:\n  42\n"}, check_app_entry)


def test_non_string_as_value_of_command():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: command name '%s' should be followed by a dictionary of attributes not %r" % (
            project.project_file.filename, 'default', 42)
        assert expected_error == project.problems[0]

    with_directory_contents({PROJECT_FILENAME: "commands:\n default: 42\n"}, check_app_entry)


def test_empty_command():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: command '%s' does not have a command line in it" % (project.project_file.filename,
                                                                                  'default')
        assert expected_error == project.problems[0]

    with_directory_contents({PROJECT_FILENAME: "commands:\n default: {}\n"}, check_app_entry)


def test_two_empty_commands():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert 2 == len(project.problems)
        expected_error_1 = "%s: command '%s' does not have a command line in it" % (project.project_file.filename,
                                                                                    'foo')
        expected_error_2 = "%s: command '%s' does not have a command line in it" % (project.project_file.filename,
                                                                                    'bar')
        assert expected_error_1 == project.problems[0]
        assert expected_error_2 == project.problems[1]

    with_directory_contents({PROJECT_FILENAME: "commands:\n foo: {}\n bar: {}\n"}, check_app_entry)


def test_non_string_as_value_of_conda_app_entry():
    def check_app_entry(dirname):
        project = project_no_dedicated_env(dirname)
        assert 1 == len(project.problems)
        expected_error = "%s: command '%s' attribute '%s' should be a string not '%r'" % (
            project.project_file.filename, 'default', 'conda_app_entry', 42)
        assert expected_error == project.problems[0]

    with_directory_contents({PROJECT_FILENAME: "commands:\n default:\n    conda_app_entry: 42\n"}, check_app_entry)


def test_launch_argv_from_project_file():
    def check_launch_argv(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        command = project.default_command
        command.name == 'foo'
        command._attributes == dict(conda_app_entry="foo bar ${PREFIX}")

        assert 1 == len(project.commands)
        assert 'foo' in project.commands
        assert project.commands['foo'] is command

    with_directory_contents(
        {PROJECT_FILENAME: """
commands:
  foo:
    conda_app_entry: foo bar ${PREFIX}
"""}, check_launch_argv)


def test_launch_argv_is_none_when_no_commands():
    def check_launch_argv(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        command = project.default_command
        assert command is None

        environ = minimal_environ(PROJECT_DIR=dirname)

        launch_argv = project.launch_argv_for_environment(environ)
        assert launch_argv is None

    with_directory_contents({PROJECT_FILENAME: """
"""}, check_launch_argv)


def test_launch_argv_from_meta_file():
    def check_launch_argv(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        command = project.default_command
        command.name == 'default'
        command._attributes == dict(conda_app_entry="foo bar ${PREFIX}")

    with_directory_contents(
        {META_DIRECTORY + "/" + META_FILENAME: """
app:
  entry: foo bar ${PREFIX}
"""}, check_launch_argv)


def test_launch_argv_from_meta_file_with_name_in_project_file():
    def check_launch_argv(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        command = project.default_command
        command.name == 'foo'
        command._attributes == dict(conda_app_entry="foo bar ${PREFIX}")

    with_directory_contents(
        {
            PROJECT_FILENAME: """
commands:
  foo: {}
""",
            META_DIRECTORY + "/" + META_FILENAME: """
app:
  entry: foo bar ${PREFIX}
"""
        }, check_launch_argv)


def _launch_argv_for_environment(environ, expected_output, chdir=False):
    environ = minimal_environ(**environ)

    def check_echo_output(dirname):
        if 'PROJECT_DIR' not in environ:
            environ['PROJECT_DIR'] = dirname
        os.chmod(os.path.join(dirname, "echo.py"), stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        old_dir = None
        if chdir:
            old_dir = os.getcwd()
            os.chdir(dirname)
        try:
            project = project_no_dedicated_env(dirname)
            assert [] == project.problems
            argv = project.launch_argv_for_environment(environ)
            output = subprocess.check_output(argv).decode()
            assert output == expected_output.format(dirname=dirname)
        finally:
            if old_dir is not None:
                os.chdir(old_dir)

    with_directory_contents(
        {
            PROJECT_FILENAME: """
commands:
  default:
    conda_app_entry: echo.py ${PREFIX}/blah foo bar
""",
            "echo.py": """#!/usr/bin/env python
from __future__ import print_function
import sys
print(repr(sys.argv))
"""
        }, check_echo_output)


def test_launch_command_in_project_dir():
    prefix = os.getenv('CONDA_ENV_PATH')
    _launch_argv_for_environment(dict(), "['{dirname}/echo.py', '%s/blah', 'foo', 'bar']\n" % prefix)


def test_launch_command_in_project_dir_and_cwd_is_project_dir():
    prefix = os.getenv('CONDA_ENV_PATH')
    _launch_argv_for_environment(dict(), "['{dirname}/echo.py', '%s/blah', 'foo', 'bar']\n" % prefix, chdir=True)


def test_launch_command_in_project_dir_with_conda_env():
    _launch_argv_for_environment(
        dict(CONDA_ENV_PATH='/someplace',
             CONDA_DEFAULT_ENV='/someplace'),
        "['{dirname}/echo.py', '/someplace/blah', 'foo', 'bar']\n")


def test_launch_command_is_on_system_path():
    def check_python_version_output(dirname):
        environ = minimal_environ(PROJECT_DIR=dirname)
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        argv = project.launch_argv_for_environment(environ)
        output = subprocess.check_output(argv, stderr=subprocess.STDOUT).decode()
        assert output.startswith("Python")

    with_directory_contents(
        {PROJECT_FILENAME: """
commands:
  default:
    conda_app_entry: python --version
"""}, check_python_version_output)


def test_launch_command_does_not_exist():
    def check_error_on_nonexistent_path(dirname):
        import errno
        environ = minimal_environ(PROJECT_DIR=dirname)
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        argv = project.launch_argv_for_environment(environ)
        assert argv[0] == 'this-command-does-not-exist'
        try:
            FileNotFoundError
        except NameError:
            # python 2
            FileNotFoundError = OSError
        with pytest.raises(FileNotFoundError) as excinfo:
            subprocess.check_output(argv, stderr=subprocess.STDOUT).decode()
        assert excinfo.value.errno == errno.ENOENT

    with_directory_contents(
        {PROJECT_FILENAME: """
commands:
  default:
    conda_app_entry: this-command-does-not-exist
"""}, check_error_on_nonexistent_path)


def test_launch_command_stuff_missing_from_environment():
    def check_launch_with_stuff_missing(dirname):
        project = project_no_dedicated_env(dirname)
        assert [] == project.problems
        environ = minimal_environ(PROJECT_DIR=dirname)
        for key in ('PATH', 'CONDA_ENV_PATH', 'PROJECT_DIR'):
            environ_copy = deepcopy(environ)
            del environ_copy[key]
            with pytest.raises(ValueError) as excinfo:
                project.launch_argv_for_environment(environ_copy)
            assert ('%s must be set' % key) in repr(excinfo.value)

    with_directory_contents(
        {PROJECT_FILENAME: """
commands:
  default:
    conda_app_entry: foo
"""}, check_launch_with_stuff_missing)
