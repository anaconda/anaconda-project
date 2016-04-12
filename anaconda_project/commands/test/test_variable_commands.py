# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import pytest

from anaconda_project.commands.variable_commands import main
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME


class Args(object):
    def __init__(self, action, vars_to_set=None, vars_to_unset=None, project='.'):
        self.project = project
        self.action = action
        self.environment = 'default'
        self.vars_to_set = vars_to_set
        self.vars_to_unset = vars_to_unset


def test_set_variable_command(monkeypatch):

    params = []

    def mock_add_variables(project, _vars):
        params.append(_vars)
        return True

    monkeypatch.setattr('anaconda_project.project_ops.add_variables', mock_add_variables)

    args = Args('set', vars_to_set=['foo=bar', 'baz=qux'])
    res = main(args)
    assert res == 0
    assert len(params) == 1
    assert ['foo', 'bar'] in params[0]
    assert ['baz', 'qux'] in params[0]


def test_set_variable_project_problem(capsys):
    def check_problem(dirname):
        args = Args('set', vars_to_set=['foo=bar', 'baz=qux'], project=dirname)
        res = main(args)
        assert res == 1

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
runtime:
  42
"""}, check_problem)

    out, err = capsys.readouterr()
    assert out == ''
    expected_err = ('Unable to load project:\n  '
                    'runtime section contains wrong value type 42, should be dict or list of requirements\n')
    assert err == expected_err


def test_set_variable_command_bad(monkeypatch, capsys):

    params = []

    def mock_add_variables(project, _vars):
        params.append(_vars)
        return True

    monkeypatch.setattr('anaconda_project.project_ops.add_variables', mock_add_variables)

    args = Args('set', vars_to_set=['foo=bar', 'baz'])
    res = main(args)
    assert res == 1
    out, err = capsys.readouterr()
    assert "Error: {} doesn't define a name=value pair".format('baz') in out

    assert len(params) == 0


def test_unset_variable_command(monkeypatch):

    args = Args('unset', vars_to_unset=['foo=bar', 'baz=qux'])
    with pytest.raises(NotImplementedError):
        main(args)
