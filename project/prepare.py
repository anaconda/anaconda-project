"""Prepare a project to run."""
from __future__ import print_function

import os
import sys

from project.plugins.provider import ProviderRegistry

UI_MODE_TEXT = "text"
UI_MODE_BROWSER = "browser"
UI_MODE_NOT_INTERACTIVE = "not_interactive"

_all_ui_modes = (UI_MODE_TEXT, UI_MODE_BROWSER, UI_MODE_NOT_INTERACTIVE)


def prepare(project, ui_mode=UI_MODE_BROWSER, io_loop=None, show_url=None, environ=None):
    """Perform all steps needed to get a project ready to execute.

    This may need to ask the user questions, may start services,
    run scripts, load configuration, install packages... it can do
    anything. Expect side effects.

    Args:
        project (Project): the project
        ui_mode (str): one of ``UI_MODE_TEXT``, ``UI_MODE_BROWSER``, ``UI_MODE_NOT_INTERACTIVE``
        io_loop (IOLoop): tornado IOLoop to use, None for default
        show_url (function): takes a URL and displays it in a browser somehow, None for default
        environ (dict): the environment to prepare (None to use os.environ)

    Returns:
        True if successful.

    """
    if ui_mode not in _all_ui_modes:
        raise ValueError("invalid UI mode " + ui_mode)

    if environ is None:
        environ = os.environ

    provider_registry = ProviderRegistry()

    # the plan is a list of (provider, requirement) in order we should run it.
    # our algorithm to decide on this will be getting more complicated.
    plan = []
    for requirement in project.requirements:
        providers = requirement.find_providers(provider_registry)
        plan.append((providers[0], requirement))

    for (provider, requirement) in plan:
        provider.provide(requirement, environ)

    failed = False
    for requirement in project.requirements:
        why_not = requirement.why_not_provided(environ)
        if why_not is not None:
            print("missing requirement to run this project: {requirement.title}".format(requirement=requirement),
                  file=sys.stderr)
            print("  {why_not}".format(why_not=why_not), file=sys.stderr)
            failed = True

    return not failed
