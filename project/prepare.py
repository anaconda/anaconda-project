"""Prepare a project to run."""
from __future__ import absolute_import
from __future__ import print_function

from copy import copy, deepcopy
import os
import subprocess
import sys

from project.plugins.provider import ProvideContext, ProviderRegistry
from project.internal.local_state_file import LocalStateFile

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

    # we modify a copy, which 1) makes all our changes atomic and
    # 2) minimizes memory leaks on systems that use putenv() (it
    # appears we must use deepcopy or we still modify os.environ
    # somehow)
    environ_copy = deepcopy(environ)

    provider_registry = ProviderRegistry()

    # the plan is a list of (provider, requirement) in order we should run it.
    # our algorithm to decide on this will be getting more complicated.
    plan = []
    for requirement in project.requirements:
        providers = requirement.find_providers(provider_registry)
        for provider in providers:
            plan.append((provider, requirement))

    local_state = LocalStateFile.load_for_directory(project.directory_path)

    for (provider, requirement) in plan:
        why_not = requirement.why_not_provided(environ_copy)
        if why_not is None:
            continue
        context = ProvideContext(environ_copy, local_state)
        provider.provide(requirement, context)
        if context.errors:
            for log in context.logs:
                print(log, file=sys.stdout)
            # be sure we print all these before the errors
            sys.stdout.flush()
        # now print the errors
        for error in context.errors:
            print(error, file=sys.stderr)

    failed = False
    for requirement in project.requirements:
        why_not = requirement.why_not_provided(environ_copy)
        if why_not is not None:
            print("missing requirement to run this project: {requirement.title}".format(requirement=requirement),
                  file=sys.stderr)
            print("  {why_not}".format(why_not=why_not), file=sys.stderr)
            failed = True

    if failed:
        return False
    else:
        for key, value in environ_copy.items():
            if key not in environ or environ[key] != value:
                environ[key] = value
        return True


def unprepare(project, io_loop=None):
    """Attempt to clean up project-scoped resources allocated by prepare().

    This will retain any user configuration choices about how to
    provide requirements, but it stops project-scoped services.
    Global system services or other services potentially shared
    among projects will not be stopped.

    Args:
        project (Project): the project
        io_loop (IOLoop): tornado IOLoop to use, None for default

    """
    local_state = LocalStateFile.load_for_directory(project.directory_path)

    run_states = local_state.get_all_service_run_states()
    for service_name in copy(run_states):
        state = run_states[service_name]
        if 'shutdown_commands' in state:
            commands = state['shutdown_commands']
            for command in commands:
                print("Running " + repr(command))
                code = subprocess.call(command)
                print("  exited with " + str(code))
        # clear out the run state once we try to shut it down
        local_state.set_service_run_state(service_name, dict())
        local_state.save()
