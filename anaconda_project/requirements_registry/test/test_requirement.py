# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from anaconda_project.requirements_registry.registry import RequirementsRegistry
from anaconda_project.requirements_registry.requirement import EnvVarRequirement, UserConfigOverrides

from anaconda_project.internal.test.tmpfile_utils import tmp_local_state_file


def test_user_config_overrides():
    overrides = UserConfigOverrides()
    assert overrides.env_spec_name is None
    overrides = UserConfigOverrides(env_spec_name='foo')
    assert overrides.env_spec_name == 'foo'


def test_find_by_env_var_unknown():
    registry = RequirementsRegistry()
    found = registry.find_requirement_by_env_var(env_var='FOO', options=None)
    assert found is not None
    assert isinstance(found, EnvVarRequirement)
    assert found.env_var == 'FOO'
    assert "EnvVarRequirement(env_var='FOO')" == repr(found)


def test_find_by_service_type_unknown():
    registry = RequirementsRegistry()
    found = registry.find_requirement_by_service_type(service_type='blah', env_var='FOO', options=dict())
    assert found is None


def test_autoguess_encrypted_option():
    def req(env_var, options=None):
        return EnvVarRequirement(registry=RequirementsRegistry(), env_var=env_var, options=options)

    assert not req(env_var='FOO').encrypted
    assert req(env_var='FOO', options=dict(encrypted=True)).encrypted

    assert req(env_var='FOO_PASSWORD').encrypted
    assert req(env_var='FOO_SECRET').encrypted
    assert req(env_var='FOO_SECRET_KEY').encrypted

    assert not req(env_var='FOO_PASSWORD', options=dict(encrypted=False)).encrypted
    assert not req(env_var='FOO_SECRET', options=dict(encrypted=False)).encrypted
    assert not req(env_var='FOO_SECRET_KEY', options=dict(encrypted=False)).encrypted


def test_empty_variable_treated_as_unset():
    requirement = EnvVarRequirement(registry=RequirementsRegistry(), env_var='FOO')
    status = requirement.check_status(dict(FOO=''), tmp_local_state_file(), 'default', UserConfigOverrides())
    assert not status
    assert "Environment variable FOO is not set." == status.status_description
    assert [] == status.errors


def test_requirement_repr():
    requirement = EnvVarRequirement(registry=RequirementsRegistry(), env_var='FOO')
    assert "EnvVarRequirement(env_var='FOO')" == repr(requirement)


def test_requirement_status_repr():
    requirement = EnvVarRequirement(registry=RequirementsRegistry(), env_var='FOO')
    status = requirement.check_status(dict(FOO=''), tmp_local_state_file(), 'default', UserConfigOverrides())
    assert "RequirementStatus(False,'Environment variable FOO is not set.',EnvVarRequirement(env_var='FOO'))" == repr(
        status)


def test_requirement_parse_default():
    null_default = dict(default=None)
    string_default = dict(default="foo")
    int_default = dict(default=42)
    float_default = dict(default=3.14)

    # invalid defaults
    bool_default = dict(default=True)
    list_default = dict(default=[])

    def type_error(value):
        return "default value for variable FOO must be null, a string, or a number, not {value}.".format(value=value)

    problems = []

    EnvVarRequirement._parse_default(null_default, "FOO", problems)
    assert null_default == dict()
    assert problems == []

    EnvVarRequirement._parse_default(string_default, "FOO", problems)
    assert string_default == dict(default="foo")
    assert problems == []

    EnvVarRequirement._parse_default(int_default, "FOO", problems)
    assert int_default == dict(default=42)
    assert problems == []

    EnvVarRequirement._parse_default(float_default, "FOO", problems)
    assert float_default == dict(default=3.14)
    assert problems == []

    EnvVarRequirement._parse_default(bool_default, "FOO", problems)
    assert problems == [type_error(True)]

    problems = []
    EnvVarRequirement._parse_default(list_default, "FOO", problems)
    assert problems == [type_error([])]


def test_requirement_default_as_string():
    no_default = dict()
    string_default = dict(default="foo")
    int_default = dict(default=42)
    float_default = dict(default=3.14)

    req = EnvVarRequirement(registry=RequirementsRegistry(), env_var='FOO', options=no_default)
    assert req.default_as_string is None

    req = EnvVarRequirement(registry=RequirementsRegistry(), env_var='FOO', options=string_default)
    assert req.default_as_string == "foo"

    req = EnvVarRequirement(registry=RequirementsRegistry(), env_var='FOO', options=int_default)
    assert req.default_as_string == "42"

    req = EnvVarRequirement(registry=RequirementsRegistry(), env_var='FOO', options=float_default)
    assert req.default_as_string == "3.14"
