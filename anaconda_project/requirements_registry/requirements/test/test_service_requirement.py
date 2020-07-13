# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
from anaconda_project.project import Project
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME
from anaconda_project.requirements_registry.requirements.service import ServiceRequirement

from anaconda_project.internal.test.tmpfile_utils import with_directory_contents_completing_project_file


def _load_service_requirement(dirname):
    project = Project(dirname)
    assert [] == project.problems
    for req in project.requirements(project.default_env_spec_name):
        if isinstance(req, ServiceRequirement):
            return req
    raise RuntimeError("no ServiceRequirement found")


def test_service_dict_with_options():
    def check(dirname):
        req = _load_service_requirement(dirname)
        assert req.options == dict(type='redis', foo='bar', default='hello')
        assert req.env_var == 'FOOBAR'

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
services:
    FOOBAR: { type: redis, foo: bar, default: hello }
    """}, check)


def test_service_dict_with_bad_value():
    def check(dirname):
        project = Project(dirname)
        assert ["Service FOOBAR should have a service type string or a dictionary as its value."] == project.problems

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
services:
    FOOBAR:
     - 42
    """}, check)


def test_service_with_bad_service_type():
    def check(dirname):
        project = Project(dirname)
        assert ["Service FOOBAR has an unknown type 'not_a_service'."] == project.problems

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
services:
    FOOBAR: not_a_service
    """}, check)


def test_service_dict_with_no_service_type():
    def check(dirname):
        project = Project(dirname)
        assert ["Service FOOBAR doesn't contain a 'type' field."] == project.problems

    with_directory_contents_completing_project_file({DEFAULT_PROJECT_FILENAME: """
services:
    FOOBAR: {}
    """}, check)


def test_service_dict_bad_default():
    def check(dirname):
        project = Project(dirname)
        assert ["default value for variable FOOBAR must be null, a string, or a number, not []."] == project.problems

    with_directory_contents_completing_project_file(
        {DEFAULT_PROJECT_FILENAME: """
services:
    FOOBAR: { type: redis, default: [] }
    """}, check)
