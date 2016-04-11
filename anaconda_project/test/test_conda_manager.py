# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import

from project.conda_manager import push_conda_manager_class, pop_conda_manager_class, new_conda_manager, CondaManager


def test_use_non_default_conda_manager():
    called = dict()

    class MyCondaManager(CondaManager):
        def find_environment_deviations(self, *args):
            called['find_environment_deviations'] = args

        def fix_environment_deviations(self, *args):
            called['fix_environment_deviations'] = args

    push_conda_manager_class(MyCondaManager)
    try:
        manager = new_conda_manager()
        manager.find_environment_deviations(None, None)
        manager.fix_environment_deviations(None, None)
        assert dict(find_environment_deviations=(None, None), fix_environment_deviations=(None, None)) == called
    finally:
        pop_conda_manager_class()
