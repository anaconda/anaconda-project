from __future__ import absolute_import, print_function

from project.plugins.registry import PluginRegistry
from project.plugins.requirements.conda_env import CondaEnvRequirement

from project.internal.test.tmpfile_utils import with_directory_contents


def test_find_by_env_var_conda_env():
    registry = PluginRegistry()
    found = registry.find_requirement_by_env_var(env_var='CONDA_DEFAULT_ENV', options=dict())
    assert found is not None
    assert isinstance(found, CondaEnvRequirement)
    assert found.env_var == 'CONDA_DEFAULT_ENV'


def test_conda_default_env_not_set():
    requirement = CondaEnvRequirement(registry=PluginRegistry())
    status = requirement.check_status(dict())
    expected = "A Conda environment hasn't been activated for this project (CONDA_DEFAULT_ENV is unset)."
    assert expected == status.status_description


def test_conda_default_env_is_bogus():
    requirement = CondaEnvRequirement(registry=PluginRegistry())
    status = requirement.check_status(dict(CONDA_DEFAULT_ENV="not_a_real_env_anyone_has"))
    expected = "Conda environment CONDA_DEFAULT_ENV='not_a_real_env_anyone_has' does not exist yet."
    assert expected == status.status_description


def test_conda_fails_while_looking_up_env(monkeypatch):
    def get_fail_command(extra_args):
        return ["bash", "-c", "echo FAILURE 1>&2 && false"]

    monkeypatch.setattr('project.internal.conda_api._get_conda_command', get_fail_command)
    requirement = CondaEnvRequirement(registry=PluginRegistry())
    status = requirement.check_status(dict(CONDA_DEFAULT_ENV="not_a_real_env_anyone_has"))
    assert status.status_description.startswith(
        "Conda didn't understand environment name or prefix not_a_real_env_anyone_has: ")
    assert 'FAILURE' in status.status_description


def test_conda_fails_while_listing_installed(monkeypatch):
    def sabotaged_installed_command(prefix):
        from project.internal import conda_api
        raise conda_api.CondaError("sabotage!")

    monkeypatch.setattr('project.internal.conda_api.installed', sabotaged_installed_command)

    requirement = CondaEnvRequirement(registry=PluginRegistry(),
                                      options=dict(project_scoped=False),
                                      conda_package_specs=['not_a_real_package'])
    status = requirement.check_status(dict(CONDA_DEFAULT_ENV="root"))
    assert status.status_description.startswith("Conda failed while listing installed packages in ")
    assert status.status_description.endswith(": sabotage!")


def test_project_dir_not_set(monkeypatch):
    def mock_resolve_env_to_prefix(name_or_prefix):
        return "/foo"

    monkeypatch.setattr('project.internal.conda_api.resolve_env_to_prefix', mock_resolve_env_to_prefix)
    requirement = CondaEnvRequirement(registry=PluginRegistry(), options=dict(project_scoped=True))
    status = requirement.check_status(dict(CONDA_DEFAULT_ENV="root"))
    assert "PROJECT_DIR isn't set, so cannot find or create a dedicated Conda environment." == status.status_description


def test_error_when_not_project_scoped_and_must_be(monkeypatch):
    def mock_resolve_env_to_prefix(name_or_prefix):
        return "/foo"

    monkeypatch.setattr('project.internal.conda_api.resolve_env_to_prefix', mock_resolve_env_to_prefix)

    def check_when_not_project_scoped(dirname):
        requirement = CondaEnvRequirement(registry=PluginRegistry(), options=dict(project_scoped=True))
        status = requirement.check_status(dict(CONDA_DEFAULT_ENV="root", PROJECT_DIR=dirname))
        expected = ("This project needs a dedicated Conda environment inside %s, " +
                    "the current environment (in %s) isn't dedicated to this project.") % (dirname, "/foo")
        assert expected == status.status_description

    with_directory_contents(dict(), check_when_not_project_scoped)


def test_when_need_not_be_project_scoped(monkeypatch):
    def check_when_need_not_be_project_scoped(dirname):
        requirement = CondaEnvRequirement(registry=PluginRegistry(), options=dict(project_scoped=False))
        status = requirement.check_status(dict(CONDA_DEFAULT_ENV="root", PROJECT_DIR=dirname))
        assert status.has_been_provided

    with_directory_contents(dict(), check_when_need_not_be_project_scoped)


def test_missing_package():
    def check_missing_package(dirname):
        requirement = CondaEnvRequirement(registry=PluginRegistry(),
                                          options=dict(project_scoped=False),
                                          conda_package_specs=['boguspackage', 'boguspackage2'])
        status = requirement.check_status(dict(CONDA_DEFAULT_ENV="root", PROJECT_DIR=dirname))
        assert "Conda environment is missing packages: boguspackage, boguspackage2" == status.status_description

    with_directory_contents(dict(), check_missing_package)
