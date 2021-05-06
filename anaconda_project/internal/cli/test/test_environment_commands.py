# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import os

from anaconda_project.internal.cli.main import _parse_args_and_run_subcommand
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents_completing_project_file
from anaconda_project.internal.simple_status import SimpleStatus
from anaconda_project.project import Project


def _monkeypatch_pwd(monkeypatch, dirname):
    from os.path import abspath as real_abspath

    def mock_abspath(path):
        if path == ".":
            return dirname
        else:
            return real_abspath(path)

    monkeypatch.setattr('os.path.abspath', mock_abspath)


def _monkeypatch_record_args(monkeypatch, what, result):
    params = {}

    def mock_recorder(*args, **kwargs):
        params['args'] = args
        params['kwargs'] = kwargs

        # log status.errors to the frontend, because the real functions
        # do that, in theory
        if hasattr(result, 'errors') and isinstance(args[0], Project):
            for error in result.errors:
                args[0].frontend.error(error)

        return result

    monkeypatch.setattr(what, mock_recorder)

    return params


def _monkeypatch_add_env_spec(monkeypatch, result):
    return _monkeypatch_record_args(monkeypatch, "anaconda_project.project_ops.add_env_spec", result)


def _monkeypatch_add_packages(monkeypatch, result):
    return _monkeypatch_record_args(monkeypatch, "anaconda_project.project_ops.add_packages", result)


def _monkeypatch_remove_packages(monkeypatch, result):
    return _monkeypatch_record_args(monkeypatch, "anaconda_project.project_ops.remove_packages", result)


def _monkeypatch_add_platforms(monkeypatch, result):
    return _monkeypatch_record_args(monkeypatch, "anaconda_project.project_ops.add_platforms", result)


def _monkeypatch_remove_platforms(monkeypatch, result):
    return _monkeypatch_record_args(monkeypatch, "anaconda_project.project_ops.remove_platforms", result)


def _monkeypatch_lock(monkeypatch, result):
    return _monkeypatch_record_args(monkeypatch, "anaconda_project.project_ops.lock", result)


def _monkeypatch_unlock(monkeypatch, result):
    return _monkeypatch_record_args(monkeypatch, "anaconda_project.project_ops.unlock", result)


def _monkeypatch_update(monkeypatch, result):
    return _monkeypatch_record_args(monkeypatch, "anaconda_project.project_ops.update", result)


def _test_environment_command_with_project_file_problems(capsys, monkeypatch, command, append_dirname=False):
    def check(dirname):
        if append_dirname:
            command.append(dirname)
        _monkeypatch_pwd(monkeypatch, dirname)

        code = _parse_args_and_run_subcommand(command)
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert ('variables section contains wrong value type 42,' + ' should be dict or list of requirements\n' +
                'Unable to load the project.\n') in err

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: "variables:\n  42"}, check)


def test_add_env_spec_no_packages(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        _monkeypatch_add_env_spec(monkeypatch, SimpleStatus(success=True, description='Environment looks good.'))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'add-env-spec', '--name', 'foo'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Environment looks good.\n' + 'Added environment foo to the project file.\n') == out
        assert '' == err

    with_directory_contents_completing_project_file(dict(), check)


def test_add_env_spec_with_packages(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        params = _monkeypatch_add_env_spec(monkeypatch, SimpleStatus(success=True,
                                                                     description='Environment looks good.'))

        code = _parse_args_and_run_subcommand(
            ['anaconda-project', 'add-env-spec', '--name', 'foo', '--channel', 'c1', '--channel=c2', 'a', 'b'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Environment looks good.\n' + 'Added environment foo to the project file.\n') == out
        assert '' == err

        assert 1 == len(params['args'])
        assert dict(name='foo', packages=['a', 'b'], channels=['c1', 'c2']) == params['kwargs']

    with_directory_contents_completing_project_file(dict(), check)


def test_add_env_spec_fails(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        _monkeypatch_add_env_spec(
            monkeypatch,
            SimpleStatus(success=False,
                         description='Environment variable MYDATA is not set.',
                         errors=['This is an error message.']))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'add-env-spec', '--name', 'foo'])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert 'This is an error message.\nEnvironment variable MYDATA is not set.\n' == err

    with_directory_contents_completing_project_file(dict(), check)


def test_remove_env_spec_missing(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        code = _parse_args_and_run_subcommand(['anaconda-project', 'remove-env-spec', '--name', 'foo'])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert "Environment spec foo doesn't exist.\n" == err

    with_directory_contents_completing_project_file(dict(), check)


def test_remove_env_spec_fails(capsys, monkeypatch):
    def check(dirname):
        from shutil import rmtree as real_rmtree
        _monkeypatch_pwd(monkeypatch, dirname)

        test_filename = os.path.join(dirname, 'envs', 'foo')

        # only allow mock to have side effect once
        # later, when cleaning up directory, allow removal
        mock_called = []

        def mock_remove(path, ignore_errors=False, onerror=None):
            if path == test_filename and not mock_called:
                mock_called.append(True)
                raise Exception('Error')
            return real_rmtree(path, ignore_errors, onerror)

        monkeypatch.setattr('shutil.rmtree', mock_remove)

        code = _parse_args_and_run_subcommand(['anaconda-project', 'remove-env-spec', '--name', 'foo'])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert ("Failed to remove environment files in %s: Error.\n" % os.path.join(dirname, "envs", "foo")) == err

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: 'env_specs:\n  foo:\n    channels: []\n    packages:\n    - bar\n' +
            '  baz:\n    channels: []\n    packages:\n    - bar\n',
            'envs/foo/bin/test': 'code here'
        }, check)


def test_remove_env_spec(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)

        code = _parse_args_and_run_subcommand(['anaconda-project', 'remove-env-spec', '--name', 'foo'])
        assert code == 0

        out, err = capsys.readouterr()
        assert '' == err
        assert ('Deleted environment files in %s.\nRemoved environment foo from the project file.\n' %
                os.path.join(dirname, "envs", "foo")) == out

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: 'env_specs:\n  foo:\n    channels: []\n    packages:\n    - bar\n' +
            '  bar:\n    channels: []\n    packages:\n    - baz\n',
            'envs/foo/bin/test': 'code here'
        }, check)


def test_remove_only_env_spec(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)

        code = _parse_args_and_run_subcommand(['anaconda-project', 'remove-env-spec', '--name', 'foo'])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert "At least one environment spec is required; 'foo' is the only one left.\n" == err

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: 'env_specs:\n  foo:\n    channels: []\n    packages:\n    - bar\n',
            'envs/foo/bin/test': 'code here'
        }, check)


def test_remove_env_spec_in_use(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)

        code = _parse_args_and_run_subcommand(['anaconda-project', 'remove-env-spec', '--name', 'bar'])
        assert code == 1

        out, err = capsys.readouterr()
        assert '' == out
        assert (("%s: env_spec 'bar' for command 'foo' does not appear in the env_specs section\n" %
                 DEFAULT_PROJECT_FILENAME) + "Unable to load the project.\n") == err

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: """
commands:
  foo:
    unix: envs/foo/bin/test
    env_spec: bar

env_specs:
  other:
      packages:
         - hello
  bar:
      packages:
        - boo
""",
            'envs/foo/bin/test': 'code here'
        }, check)


def test_add_env_spec_with_project_file_problems(capsys, monkeypatch):
    _test_environment_command_with_project_file_problems(capsys, monkeypatch,
                                                         ['anaconda-project', 'add-env-spec', '--name', 'foo'])


def test_remove_env_spec_with_project_file_problems(capsys, monkeypatch):
    _test_environment_command_with_project_file_problems(capsys, monkeypatch,
                                                         ['anaconda-project', 'remove-env-spec', '--name', 'foo'])


def test_export_env_spec(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)

        exported = os.path.join(dirname, "exported.yml")
        code = _parse_args_and_run_subcommand(['anaconda-project', 'export-env-spec', '--name', 'foo', exported])
        assert code == 0

        out, err = capsys.readouterr()
        assert '' == err
        assert ('Exported environment spec foo to %s.\n' % exported) == out

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: 'env_specs:\n  foo:\n    channels: []\n    packages:\n    - bar\n' +
            '  bar:\n    channels: []\n    packages:\n    - baz\n',
            'envs/foo/bin/test': 'code here'
        }, check)


def test_export_env_spec_default_name(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)

        exported = os.path.join(dirname, "exported.yml")
        code = _parse_args_and_run_subcommand(['anaconda-project', 'export-env-spec', exported])
        assert code == 0

        out, err = capsys.readouterr()
        assert '' == err
        assert ('Exported environment spec foo to %s.\n' % exported) == out

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: 'env_specs:\n  foo:\n    channels: []\n    packages:\n    - bar\n' +
            '  bar:\n    channels: []\n    packages:\n    - baz\n',
            'envs/foo/bin/test': 'code here'
        }, check)


def test_export_env_spec_no_filename(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)

        code = _parse_args_and_run_subcommand(['anaconda-project', 'export-env-spec', '--name', 'foo'])
        assert code == 2

        out, err = capsys.readouterr()
        assert 'ENVIRONMENT_FILE' in err
        assert '' == out

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: 'env_specs:\n  foo:\n    channels: []\n    packages:\n    - bar\n' +
            '  bar:\n    channels: []\n    packages:\n    - baz\n',
            'envs/foo/bin/test': 'code here'
        }, check)


def test_add_packages_with_project_file_problems(capsys, monkeypatch):
    _test_environment_command_with_project_file_problems(capsys, monkeypatch,
                                                         ['anaconda-project', 'add-packages', 'foo'])


def test_remove_packages_with_project_file_problems(capsys, monkeypatch):
    _test_environment_command_with_project_file_problems(capsys, monkeypatch,
                                                         ['anaconda-project', 'remove-packages', 'foo'])


def test_add_packages_to_all_environments(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        params = _monkeypatch_add_packages(monkeypatch, SimpleStatus(success=True, description='Installed ok.'))

        code = _parse_args_and_run_subcommand(
            ['anaconda-project', 'add-packages', '--channel', 'c1', '--channel=c2', 'a', 'b'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Installed ok.\n' + 'Added packages to project file: a, b.\n') == out
        assert '' == err

        assert 1 == len(params['args'])
        assert dict(env_spec_name=None, packages=['a', 'b'], channels=['c1', 'c2'], pip=False) == params['kwargs']

    with_directory_contents_completing_project_file(dict(), check)


def test_add_pip_packages_to_all_environments(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        params = _monkeypatch_add_packages(monkeypatch, SimpleStatus(success=True, description='Installed ok.'))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'add-packages', '--pip', 'a', 'b'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Installed ok.\n' + 'Added packages to project file: a, b.\n') == out
        assert '' == err

        assert 1 == len(params['args'])
        assert dict(env_spec_name=None, packages=['a', 'b'], channels=None, pip=True) == params['kwargs']

    with_directory_contents_completing_project_file(dict(), check)


def test_add_packages_to_specific_environment(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        params = _monkeypatch_add_packages(monkeypatch, SimpleStatus(success=True, description='Installed ok.'))

        code = _parse_args_and_run_subcommand(
            ['anaconda-project', 'add-packages', '--env-spec', 'foo', '--channel', 'c1', '--channel=c2', 'a', 'b'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Installed ok.\n' + 'Added packages to environment foo in project file: a, b.\n') == out
        assert '' == err

        assert 1 == len(params['args'])
        assert dict(env_spec_name='foo', packages=['a', 'b'], channels=['c1', 'c2'], pip=False) == params['kwargs']

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
env_specs:
  foo:
   packages:
     - bar
"""}, check)


def test_add_pip_packages_to_specific_environment(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        params = _monkeypatch_add_packages(monkeypatch, SimpleStatus(success=True, description='Installed ok.'))

        code = _parse_args_and_run_subcommand(
            ['anaconda-project', 'add-packages', '--env-spec', 'foo', '--pip', 'a', 'b'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Installed ok.\n' + 'Added packages to environment foo in project file: a, b.\n') == out
        assert '' == err

        assert 1 == len(params['args'])
        assert dict(env_spec_name='foo', packages=['a', 'b'], channels=None, pip=True) == params['kwargs']

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
env_specs:
  foo:
   packages:
     - bar
"""}, check)


def test_remove_packages_from_all_environments(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        params = _monkeypatch_remove_packages(monkeypatch, SimpleStatus(success=True, description='Installed ok.'))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'remove-packages', 'bar'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Installed ok.\n' + 'Removed packages from project file: bar.\n') == out
        assert '' == err

        assert 1 == len(params['args'])
        assert dict(env_spec_name=None, packages=['bar'], pip=False) == params['kwargs']

    with_directory_contents_completing_project_file(dict(), check)


def test_remove_packages_from_specific_environment(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        params = _monkeypatch_remove_packages(monkeypatch, SimpleStatus(success=True, description='Installed ok.'))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'remove-packages', '--env-spec', 'foo', 'bar'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Installed ok.\n' + 'Removed packages from environment foo in project file: bar.\n') == out
        assert '' == err

        assert 1 == len(params['args'])
        assert dict(env_spec_name='foo', packages=['bar'], pip=False) == params['kwargs']

    with_directory_contents_completing_project_file(dict(), check)


def test_add_platforms_with_project_file_problems(capsys, monkeypatch):
    _test_environment_command_with_project_file_problems(capsys, monkeypatch,
                                                         ['anaconda-project', 'add-platforms', 'foo'])


def test_remove_platforms_with_project_file_problems(capsys, monkeypatch):
    _test_environment_command_with_project_file_problems(capsys, monkeypatch,
                                                         ['anaconda-project', 'remove-platforms', 'foo'])


def test_add_platforms_to_all_environments(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        params = _monkeypatch_add_platforms(monkeypatch, SimpleStatus(success=True, description='Installed ok.'))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'add-platforms', 'a', 'b'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Installed ok.\n' + 'Added platforms to project file: a, b.\n') == out
        assert '' == err

        assert 1 == len(params['args'])
        assert dict(env_spec_name=None, platforms=['a', 'b']) == params['kwargs']

    with_directory_contents_completing_project_file(dict(), check)


def test_add_platforms_to_specific_environment(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        params = _monkeypatch_add_platforms(monkeypatch, SimpleStatus(success=True, description='Installed ok.'))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'add-platforms', '--env-spec', 'foo', 'a', 'b'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Installed ok.\n' + 'Added platforms to environment foo in project file: a, b.\n') == out
        assert '' == err

        assert 1 == len(params['args'])
        assert dict(env_spec_name='foo', platforms=['a', 'b']) == params['kwargs']

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
env_specs:
  foo:
   packages:
     - bar
"""}, check)


def test_remove_platforms_from_all_environments(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        params = _monkeypatch_remove_platforms(monkeypatch, SimpleStatus(success=True, description='Installed ok.'))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'remove-platforms', 'bar'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Installed ok.\n' + 'Removed platforms from project file: bar.\n') == out
        assert '' == err

        assert 1 == len(params['args'])
        assert dict(env_spec_name=None, platforms=['bar']) == params['kwargs']

    with_directory_contents_completing_project_file(dict(), check)


def test_remove_platforms_from_specific_environment(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        params = _monkeypatch_remove_platforms(monkeypatch, SimpleStatus(success=True, description='Installed ok.'))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'remove-platforms', '--env-spec', 'foo', 'bar'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Installed ok.\n' + 'Removed platforms from environment foo in project file: bar.\n') == out
        assert '' == err

        assert 1 == len(params['args'])
        assert dict(env_spec_name='foo', platforms=['bar']) == params['kwargs']

    with_directory_contents_completing_project_file(dict(), check)


def test_list_environments(capsys, monkeypatch):
    def check_list_not_empty(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'list-env-specs', '--directory', dirname])

        assert code == 0
        out, err = capsys.readouterr()
        expected_out = """
Environments for project: {dirname}

Name  Description
====  ===========
bar
foo
""".format(dirname=dirname).strip() + "\n"

        assert out == expected_out

    with_directory_contents_completing_project_file(
        {
            DEFAULT_PROJECT_FILENAME: ('env_specs:\n'
                                       '  foo:\n'
                                       '    packages:\n'
                                       '      - bar\n'
                                       '  bar:\n'
                                       '    packages:\n'
                                       '      - bar\n')
        }, check_list_not_empty)


def test_list_empty_environments(capsys, monkeypatch):
    def check_list_empty(dirname):
        code = _parse_args_and_run_subcommand(['anaconda-project', 'list-env-specs', '--directory', dirname])

        assert code == 0
        out, err = capsys.readouterr()
        expected_out = """
Environments for project: {dirname}

Name     Description
====     ===========
default
""".format(dirname=dirname).strip() + "\n"
        assert out == expected_out

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ''}, check_list_empty)


def test_list_environments_with_project_file_problems(capsys, monkeypatch):
    _test_environment_command_with_project_file_problems(capsys,
                                                         monkeypatch,
                                                         ['anaconda-project', 'list-env-specs', '--directory'],
                                                         append_dirname=True)


def test_list_packages_wrong_env(capsys):
    def check_missing_env(dirname):
        env_name = 'not-there'
        code = _parse_args_and_run_subcommand(
            ['anaconda-project', 'list-packages', '--directory', dirname, '--env-spec', env_name])

        assert code == 1

        expected_err = "Project doesn't have an environment called '{}'\n".format(env_name)

        out, err = capsys.readouterr()
        assert out == ""
        assert err == expected_err

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ""}, check_missing_env)


def _test_list_packages(capsys, env, expected_conda_deps, expected_pip_deps):
    def check_list_not_empty(dirname):
        params = ['anaconda-project', 'list-packages', '--directory', dirname]
        if env is not None:
            params.extend(['--env-spec', env])

        code = _parse_args_and_run_subcommand(params)

        assert code == 0
        out, err = capsys.readouterr()

        project = Project(dirname)
        assert project.default_env_spec_name == 'foo'
        expected_out = "Conda packages for environment '{}':\n{}".format(env or project.default_env_spec_name,
                                                                         expected_conda_deps)
        expected_out += "Pip packages for environment '{}':\n{}".format(env or project.default_env_spec_name,
                                                                        expected_pip_deps)
        assert out == expected_out

    project_contents = ('env_specs:\n'
                        '  foo:\n'
                        '    packages:\n'
                        '      - requests\n'
                        '      - flask\n'
                        '  bar:\n'
                        '    packages:\n'
                        '      - httplib\n'
                        '      - django\n\n'
                        'packages:\n'
                        ' - mandatory_package\n'
                        ' - pip:\n'
                        '     - mandatory_pip_package\n')

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: project_contents}, check_list_not_empty)


def test_list_packages_from_env(capsys):
    _test_list_packages(capsys, 'bar', '\ndjango\nhttplib\nmandatory_package\n\n', '\nmandatory_pip_package\n\n')
    _test_list_packages(capsys, 'foo', '\nflask\nmandatory_package\nrequests\n\n', '\nmandatory_pip_package\n\n')


def test_list_packages_from_env_default(capsys):
    _test_list_packages(capsys, None, '\nflask\nmandatory_package\nrequests\n\n', '\nmandatory_pip_package\n\n')


def test_list_packages_with_project_file_problems(capsys, monkeypatch):
    _test_environment_command_with_project_file_problems(capsys,
                                                         monkeypatch,
                                                         ['anaconda-project', 'list-packages', '--directory'],
                                                         append_dirname=True)


def test_list_platforms_wrong_env(capsys):
    def check_missing_env(dirname):
        env_name = 'not-there'
        code = _parse_args_and_run_subcommand(
            ['anaconda-project', 'list-platforms', '--directory', dirname, '--env-spec', env_name])

        assert code == 1

        expected_err = "Project doesn't have an environment called '{}'\n".format(env_name)

        out, err = capsys.readouterr()
        assert out == ""
        assert err == expected_err

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: ""}, check_missing_env)


def _test_list_platforms(capsys, env, expected_deps):
    def check_list_not_empty(dirname):
        params = ['anaconda-project', 'list-platforms', '--directory', dirname]
        if env is not None:
            params.extend(['--env-spec', env])

        code = _parse_args_and_run_subcommand(params)

        assert code == 0
        out, err = capsys.readouterr()

        project = Project(dirname)
        assert project.default_env_spec_name == 'foo'
        expected_out = "Platforms for environment '{}':\n{}".format(env or project.default_env_spec_name, expected_deps)
        assert out == expected_out

    project_contents = ('env_specs:\n'
                        '  foo:\n'
                        '    platforms:\n'
                        '      - linux-64\n'
                        '      - osx-32\n'
                        '  bar:\n'
                        '    platforms:\n'
                        '      - win-32\n'
                        '      - win-64\n\n'
                        'platforms:\n'
                        ' - osx-64\n')

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: project_contents}, check_list_not_empty)


def test_list_platforms_from_env(capsys):
    _test_list_platforms(capsys, 'bar', '\nosx-64\nwin-32\nwin-64\n\n')
    _test_list_platforms(capsys, 'foo', '\nlinux-64\nosx-32\nosx-64\n\n')


def test_list_platforms_from_env_default(capsys):
    _test_list_platforms(capsys, None, '\nlinux-64\nosx-32\nosx-64\n\n')


def test_list_platforms_with_project_file_problems(capsys, monkeypatch):
    _test_environment_command_with_project_file_problems(capsys,
                                                         monkeypatch,
                                                         ['anaconda-project', 'list-platforms', '--directory'],
                                                         append_dirname=True)


def test_lock_all_environments(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        params = _monkeypatch_lock(monkeypatch, SimpleStatus(success=True, description='Locked.'))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'lock'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Locked.\n') == out
        assert '' == err

        assert 1 == len(params['args'])
        assert dict(env_spec_name=None) == params['kwargs']

    with_directory_contents_completing_project_file(dict(), check)


def test_lock_specific_environment(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        params = _monkeypatch_lock(monkeypatch, SimpleStatus(success=True, description='Locked.'))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'lock', '-n', 'foo'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Locked.\n') == out
        assert '' == err

        assert 1 == len(params['args'])
        assert dict(env_spec_name='foo') == params['kwargs']

    with_directory_contents_completing_project_file(dict(), check)


def test_unlock_all_environments(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        params = _monkeypatch_unlock(monkeypatch, SimpleStatus(success=True, description='Unlocked.'))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'unlock'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Unlocked.\n') == out
        assert '' == err

        assert 1 == len(params['args'])
        assert dict(env_spec_name=None) == params['kwargs']

    with_directory_contents_completing_project_file(dict(), check)


def test_unlock_specific_environment(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        params = _monkeypatch_unlock(monkeypatch, SimpleStatus(success=True, description='Unlocked.'))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'unlock', '-n', 'foo'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Unlocked.\n') == out
        assert '' == err

        assert 1 == len(params['args'])
        assert dict(env_spec_name='foo') == params['kwargs']

    with_directory_contents_completing_project_file(dict(), check)


def test_update_all_environments(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        params = _monkeypatch_update(monkeypatch, SimpleStatus(success=True, description='Updated.'))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'update'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Updated.\n') == out
        assert '' == err

        assert 1 == len(params['args'])
        assert dict(env_spec_name=None) == params['kwargs']

    with_directory_contents_completing_project_file(dict(), check)


def test_update_specific_environment(capsys, monkeypatch):
    def check(dirname):
        _monkeypatch_pwd(monkeypatch, dirname)
        params = _monkeypatch_update(monkeypatch, SimpleStatus(success=True, description='Updated.'))

        code = _parse_args_and_run_subcommand(['anaconda-project', 'update', '-n', 'foo'])
        assert code == 0

        out, err = capsys.readouterr()
        assert ('Updated.\n') == out
        assert '' == err

        assert 1 == len(params['args'])
        assert dict(env_spec_name='foo') == params['kwargs']

    with_directory_contents_completing_project_file(dict(), check)


def test_lock_with_project_file_problems(capsys, monkeypatch):
    _test_environment_command_with_project_file_problems(capsys, monkeypatch, ['anaconda-project', 'lock'])


def test_unlock_with_project_file_problems(capsys, monkeypatch):
    _test_environment_command_with_project_file_problems(capsys, monkeypatch, ['anaconda-project', 'unlock'])


def test_update_with_project_file_problems(capsys, monkeypatch):
    _test_environment_command_with_project_file_problems(capsys, monkeypatch, ['anaconda-project', 'update'])
