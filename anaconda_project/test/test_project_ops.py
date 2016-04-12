# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from anaconda_project import project_ops
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.local_state_file import LocalStateFile
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME
from anaconda_project.test.project_utils import project_no_dedicated_env


def test_add_variables():
    def check_set_var(dirname):
        project = project_no_dedicated_env(dirname)
        project_ops.add_variables(project, [('foo', 'bar'), ('baz', 'qux')])
        re_loaded = project.project_file.load_for_directory(project.directory_path)
        assert re_loaded.get_value(['runtime', 'foo']) == {}
        assert re_loaded.get_value(['runtime', 'baz']) == {}
        local_state = LocalStateFile.load_for_directory(dirname)

        local_state.get_value(['runtime', 'foo']) == 'bar'
        local_state.get_value(['runtime', 'baz']) == 'qux'

    with_directory_contents({DEFAULT_PROJECT_FILENAME: ('runtime:\n' '  preset: {}')}, check_set_var)


def test_add_variables_existing_req():
    def check_set_var(dirname):
        project = project_no_dedicated_env(dirname)
        project_ops.add_variables(project, [('foo', 'bar'), ('baz', 'qux')])
        re_loaded = project.project_file.load_for_directory(project.directory_path)
        assert re_loaded.get_value(['runtime', 'foo']) == {}
        assert re_loaded.get_value(['runtime', 'baz']) == {}
        assert re_loaded.get_value(['runtime', 'datafile'], None) is None
        assert re_loaded.get_value(['downloads', 'datafile']) == 'http://localhost:8000/data.tgz'
        local_state = LocalStateFile.load_for_directory(dirname)

        local_state.get_value(['variables', 'foo']) == 'bar'
        local_state.get_value(['variables', 'baz']) == 'qux'
        local_state.get_value(['variables', 'datafile']) == 'http://localhost:8000/data.tgz'

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: ('runtime:\n'
                                    '  preset: {}\n'
                                    'downloads:\n'
                                    '  datafile: http://localhost:8000/data.tgz')}, check_set_var)
