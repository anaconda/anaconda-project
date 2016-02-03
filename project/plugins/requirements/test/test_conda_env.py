from __future__ import absolute_import, print_function

from project.plugins.requirement import RequirementRegistry
from project.plugins.requirements.conda_env import CondaEnvRequirement

from project.internal.test.tmpfile_utils import with_directory_contents


def test_find_by_env_var_conda_env():
    registry = RequirementRegistry()
    found = registry.find_by_env_var(env_var='CONDA_DEFAULT_ENV', options=dict())
    assert found is not None
    assert isinstance(found, CondaEnvRequirement)
    assert found.env_var == 'CONDA_DEFAULT_ENV'


def test_conda_default_env_not_set():
    requirement = CondaEnvRequirement()
    why_not = requirement.why_not_provided(dict())
    assert "Environment variable CONDA_DEFAULT_ENV is not set" == why_not


def test_conda_default_env_is_bogus():
    requirement = CondaEnvRequirement()
    why_not = requirement.why_not_provided(dict(CONDA_DEFAULT_ENV="not_a_real_env_anyone_has"))
    assert "Conda environment CONDA_DEFAULT_ENV='not_a_real_env_anyone_has' does not seem to exist." == why_not


def test_project_dir_not_set(monkeypatch):
    def mock_resolve_env_to_prefix(name_or_prefix):
        return "/foo"

    monkeypatch.setattr('project.internal.conda_api.resolve_env_to_prefix', mock_resolve_env_to_prefix)
    requirement = CondaEnvRequirement(options=dict(project_scoped=True))
    why_not = requirement.why_not_provided(dict(CONDA_DEFAULT_ENV="root"))
    assert "PROJECT_DIR not set, so cannot find a project-scoped Conda environment." == why_not


def test_error_when_not_project_scoped_and_must_be(monkeypatch):
    def mock_resolve_env_to_prefix(name_or_prefix):
        return "/foo"

    monkeypatch.setattr('project.internal.conda_api.resolve_env_to_prefix', mock_resolve_env_to_prefix)

    def check_when_not_project_scoped(dirname):
        requirement = CondaEnvRequirement(options=dict(project_scoped=True))
        why_not = requirement.why_not_provided(dict(CONDA_DEFAULT_ENV="root", PROJECT_DIR=dirname))
        expected = "Conda environment at '%s' is not inside project at '%s'" % ("/foo", dirname)
        assert expected == why_not

    with_directory_contents(dict(), check_when_not_project_scoped)


def test_when_need_not_be_project_scoped(monkeypatch):
    def check_when_need_not_be_project_scoped(dirname):
        requirement = CondaEnvRequirement(options=dict(project_scoped=False))
        why_not = requirement.why_not_provided(dict(CONDA_DEFAULT_ENV="root", PROJECT_DIR=dirname))
        assert why_not is None

    with_directory_contents(dict(), check_when_need_not_be_project_scoped)


def test_missing_package():
    def check_missing_package(dirname):
        requirement = CondaEnvRequirement(options=dict(project_scoped=False),
                                          conda_package_specs=['boguspackage', 'boguspackage2'])
        why_not = requirement.why_not_provided(dict(CONDA_DEFAULT_ENV="root", PROJECT_DIR=dirname))
        assert "Conda environment is missing packages: boguspackage, boguspackage2" == why_not

    with_directory_contents(dict(), check_missing_package)
