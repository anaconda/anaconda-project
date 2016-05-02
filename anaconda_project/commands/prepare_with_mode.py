# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Command-line-specific project prepare utilities."""
from __future__ import absolute_import, print_function

from anaconda_project import prepare

from anaconda_project.provide import (PROVIDE_MODE_PRODUCTION, PROVIDE_MODE_DEVELOPMENT, PROVIDE_MODE_CHECK)

# these UI_MODE_ strings are used as values for command line options, so they are user-visible

UI_MODE_BROWSER = "browser"
UI_MODE_TEXT_ASK_QUESTIONS = "ask"
UI_MODE_TEXT_ASSUME_YES_PRODUCTION = "production_defaults"
UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT = "development_defaults"
UI_MODE_TEXT_ASSUME_NO = "check"

_all_ui_modes = (UI_MODE_BROWSER, UI_MODE_TEXT_ASK_QUESTIONS, UI_MODE_TEXT_ASSUME_YES_PRODUCTION,
                 UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT, UI_MODE_TEXT_ASSUME_NO)


def prepare_with_ui_mode_printing_errors(project,
                                         environ=None,
                                         ui_mode=UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT,
                                         command_name=None,
                                         extra_command_args=None):
    """Perform all steps needed to get a project ready to execute.

    This may need to ask the user questions, may start services,
    run scripts, load configuration, install packages... it can do
    anything. Expect side effects.

    Args:
        project (Project): the project
        environ (dict): the environment to prepare (None to use os.environ)
        ui_mode (str): one of ``UI_MODE_BROWSER``, ``UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT``,
                       ``UI_MODE_TEXT_ASSUME_YES_PRODUCTION``, ``UI_MODE_TEXT_ASSUME_NO``
        command_name (str): command name to use or None for default
        extra_command_args (list of str): extra args for the command we prepare

    Returns:
        a ``PrepareResult`` instance

    """
    assert ui_mode in _all_ui_modes  # the arg parser should have guaranteed this

    if ui_mode == UI_MODE_BROWSER:
        result = prepare.prepare_with_browser_ui(project,
                                                 environ,
                                                 command_name=command_name,
                                                 extra_command_args=extra_command_args,
                                                 keep_going_until_success=True)
    else:
        if ui_mode == UI_MODE_TEXT_ASSUME_YES_PRODUCTION:
            provide_mode = PROVIDE_MODE_PRODUCTION
        elif ui_mode == UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT:
            provide_mode = PROVIDE_MODE_DEVELOPMENT
        elif ui_mode == UI_MODE_TEXT_ASSUME_NO:
            provide_mode = PROVIDE_MODE_CHECK

        assert ui_mode != UI_MODE_TEXT_ASK_QUESTIONS  # Not implemented yet

        result = prepare.prepare_without_interaction(project,
                                                     environ,
                                                     mode=provide_mode,
                                                     command_name=command_name,
                                                     extra_command_args=extra_command_args)

    if result.failed:
        result.print_output()

    return result
