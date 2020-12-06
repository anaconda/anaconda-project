# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Command-line-specific project prepare utilities."""
from __future__ import absolute_import, print_function

from anaconda_project import prepare
from anaconda_project import project_ops
from anaconda_project.requirements_registry.requirement import EnvVarRequirement
from anaconda_project.requirements_registry.requirements.conda_env import CondaEnvRequirement

from anaconda_project.provide import (PROVIDE_MODE_PRODUCTION, PROVIDE_MODE_DEVELOPMENT, PROVIDE_MODE_CHECK)

import anaconda_project.internal.cli.console_utils as console_utils

# these UI_MODE_ strings are used as values for command line options, so they are user-visible

# ASK_QUESTIONS mode is supposed to ask about default actions too,
# like whether to start servers.  It isn't implemented yet.
UI_MODE_TEXT_ASK_QUESTIONS = "ask"
UI_MODE_TEXT_DEVELOPMENT_DEFAULTS_OR_ASK = "development_defaults_or_ask"
UI_MODE_TEXT_ASSUME_YES_PRODUCTION = "production_defaults"
UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT = "development_defaults"
UI_MODE_TEXT_ASSUME_NO = "check"

_all_ui_modes = (UI_MODE_TEXT_ASK_QUESTIONS, UI_MODE_TEXT_DEVELOPMENT_DEFAULTS_OR_ASK,
                 UI_MODE_TEXT_ASSUME_YES_PRODUCTION, UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT, UI_MODE_TEXT_ASSUME_NO)


def _interactively_fix_missing_variables(project, result):
    """Return True if we need to re-prepare."""
    if project.problems:
        return False

    if not console_utils.stdin_is_interactive():
        return False

    # We don't ask the user to manually enter CONDA_PREFIX
    # (CondaEnvRequirement) because it's a bizarre/confusing
    # thing to ask.
    can_ask_about = [
        status for status in result.statuses if (not status and isinstance(status.requirement, EnvVarRequirement)
                                                 and not isinstance(status.requirement, CondaEnvRequirement))
    ]

    if can_ask_about:
        print("(Use Ctrl+C to quit.)")

    start_over = False
    values = dict()
    for status in can_ask_about:
        reply = console_utils.console_input("Value for " + status.requirement.env_var + ": ",
                                            encrypted=status.requirement.encrypted)
        if reply is None:
            return False  # EOF
        reply = reply.strip()
        if reply == '':
            start_over = True
            break
        values[status.requirement.env_var] = reply

    if len(values) > 0:
        status = project_ops.set_variables(project, result.env_spec_name, values.items(), result)
        if status:
            return True
        else:
            console_utils.print_status_errors(status)
            return False
    else:
        return start_over


def prepare_with_ui_mode_printing_errors(project,
                                         environ=None,
                                         ui_mode=UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT,
                                         env_spec_name=None,
                                         command_name=None,
                                         command=None,
                                         extra_command_args=None,
                                         refresh=False):
    """Perform all steps needed to get a project ready to execute.

    This may need to ask the user questions, may start services,
    run scripts, load configuration, install packages... it can do
    anything. Expect side effects.

    Args:
        project (Project): the project
        environ (dict): the environment to prepare (None to use os.environ)
        ui_mode (str): one of ``UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT``,
                       ``UI_MODE_TEXT_ASSUME_YES_PRODUCTION``, ``UI_MODE_TEXT_ASSUME_NO``
        env_spec_name (str): the environment spec name to require, or None for default
        command_name (str): command name to use or None for default
        command (ProjectCommand): a command object or None
        extra_command_args (list of str): extra args for the command we prepare

    Returns:
        a ``PrepareResult`` instance

    """
    assert ui_mode in _all_ui_modes  # the arg parser should have guaranteed this

    ask = False
    if ui_mode == UI_MODE_TEXT_ASSUME_YES_PRODUCTION:
        provide_mode = PROVIDE_MODE_PRODUCTION
    elif ui_mode == UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT:
        provide_mode = PROVIDE_MODE_DEVELOPMENT
    elif ui_mode == UI_MODE_TEXT_ASSUME_NO:
        provide_mode = PROVIDE_MODE_CHECK
    elif ui_mode == UI_MODE_TEXT_DEVELOPMENT_DEFAULTS_OR_ASK:
        provide_mode = PROVIDE_MODE_DEVELOPMENT
        ask = True

    # We might implement this by using
    # Provider.read_config/Provider.set_config_values_as_strings
    # or some new version of those; dig the old ui_server.py out
    # of git history to see how we used those methods to implement
    # an interactive HTML UI. read_config/set_config_values still
    # exist on Provider in case they are useful to implement this.
    assert ui_mode != UI_MODE_TEXT_ASK_QUESTIONS  # Not implemented yet

    # TODO: this could let you fix the suggestions if they are fixable.
    # (Note that we fix fatal problems in project_load.py, but we only
    #  display suggestions when we do a manual prepare, run, etc.)
    suggestions = project.suggestions
    if len(suggestions) > 0:
        print("Potential issues with this project:")
        for suggestion in project.suggestions:
            print("  * " + suggestion)
        print("")

    environ = None
    while True:
        result = prepare.prepare_without_interaction(project,
                                                     environ,
                                                     mode=provide_mode,
                                                     env_spec_name=env_spec_name,
                                                     command_name=command_name,
                                                     command=command,
                                                     extra_command_args=extra_command_args,
                                                     refresh=refresh)

        if result.failed:
            if ask and _interactively_fix_missing_variables(project, result):
                environ = result.environ
                continue  # re-prepare, building on our previous environ

        # if we didn't continue, quit.
        break

    return result
