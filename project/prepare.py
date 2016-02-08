"""Prepare a project to run."""
from __future__ import absolute_import
from __future__ import print_function

from abc import ABCMeta, abstractmethod
import os
import subprocess
import sys
from copy import copy, deepcopy

from tornado.ioloop import IOLoop

from project.internal.metaclass import with_metaclass
from project.internal.prepare_ui import NotInteractivePrepareUI, BrowserPrepareUI, ConfigurePrepareContext
from project.local_state_file import LocalStateFile
from project.plugins.provider import ProvideContext, ProviderRegistry, ProviderConfigContext

UI_MODE_TEXT = "text"
UI_MODE_BROWSER = "browser"
UI_MODE_NOT_INTERACTIVE = "not_interactive"

_all_ui_modes = (UI_MODE_TEXT, UI_MODE_BROWSER, UI_MODE_NOT_INTERACTIVE)


class PrepareStage(with_metaclass(ABCMeta)):
    """A step in the project preparation process."""

    @property
    @abstractmethod
    def description_of_action(self):
        """Get a user-visible description of what happens if this step is executed."""
        pass  # pragma: no cover

    @property
    @abstractmethod
    def failed(self):
        """True if there was a failure during ``execute()``."""
        pass  # pragma: no cover

    @abstractmethod
    def execute(self, ui):
        """Run this step and return a new stage, or None if we are done or failed."""
        pass  # pragma: no cover


class _FunctionPrepareStage(PrepareStage):
    """A stage chain where the description and the execute function are passed in to the constructor."""

    def __init__(self, description, execute):
        self._failed = False
        self._description = description
        self._execute = execute

    @property
    def description_of_action(self):
        return self._description

    @property
    def failed(self):
        return self._failed

    def execute(self, ui):
        return self._execute(self, ui)


class _AndThenPrepareStage(PrepareStage):
    """A stage chain which runs an ``and_then`` function after it executes successfully."""

    def __init__(self, stage, and_then):
        self._stage = stage
        self._and_then = and_then

    @property
    def description_of_action(self):
        return self._stage.description_of_action

    @property
    def failed(self):
        return self._stage.failed

    def execute(self, ui):
        next = self._stage.execute(ui)
        if next is None:
            if self._stage.failed:
                return None
            else:
                return self._and_then()
        else:
            return _AndThenPrepareStage(next, self._and_then)


def _after_stage_success(stage, and_then):
    """Run and_then function after stage executes successfully.

    and_then may return another stage, or None.
    """
    return _AndThenPrepareStage(stage, and_then)


def _process_requirements_and_providers(project, environ, local_state, requirements_and_providers):
    def configure_stage(stage, ui):
        configure_context = ConfigurePrepareContext(environ=environ,
                                                    local_state_file=local_state,
                                                    requirements_and_providers=requirements_and_providers)

        # wait for the configure UI if any
        ui.configure(configure_context)

        return _FunctionPrepareStage("Set up project requirements.", provide_stage)

    def provide_stage(stage, ui):
        # the plan is a list of (provider, requirement) in order we
        # should run it.  our algorithm to decide on this will be
        # getting more complicated for example we should be able to
        # ignore any disabled providers, or prefer certain providers,
        # etc.
        plan = []
        for (requirement, providers) in requirements_and_providers:
            for provider in providers:
                plan.append((provider, requirement))

        for (provider, requirement) in plan:
            why_not = requirement.why_not_provided(environ)
            if why_not is None:
                continue
            config_context = ProviderConfigContext(environ, local_state, requirement)
            config = provider.read_config(config_context)
            context = ProvideContext(environ, local_state, config)
            provider.provide(requirement, context)
            if context.errors:
                for log in context.logs:
                    print(log, file=sys.stdout)
                # be sure we print all these before the errors
                sys.stdout.flush()
            # now print the errors
            for error in context.errors:
                print(error, file=sys.stderr)

        stage._failed = False
        for requirement in project.requirements:
            why_not = requirement.why_not_provided(environ)
            if why_not is not None:
                print("missing requirement to run this project: {requirement.title}".format(requirement=requirement),
                      file=sys.stderr)
                print("  {why_not}".format(why_not=why_not), file=sys.stderr)
                stage._failed = True

        return None

    return _FunctionPrepareStage("Customize how project requirements will be met.", configure_stage)


def prepare_in_stages(project, environ=None):
    """Get a chain of all steps needed to get a project ready to execute.

    This function does not immediately do anything; it returns a
    ``PrepareStage`` object which can be executed. Executing each
    stage may return a new stage, or may return ``None``. If a
    stage returns ``None``, preparation is done and the ``failed``
    property of the stage indicates whether it failed.

    Executing a stage may ask the user questions, may start
    services, run scripts, load configuration, install
    packages... it can do anything. Expect side effects.

    Args:
        project (Project): the project
        environ (dict): the environment to prepare (None to use os.environ)

    Returns:
        The first ``PrepareStage`` in the chain of steps.

    """
    if environ is None:
        environ = os.environ

    # we modify a copy, which 1) makes all our changes atomic and
    # 2) minimizes memory leaks on systems that use putenv() (it
    # appears we must use deepcopy (vs plain copy) or we still
    # modify os.environ somehow)
    environ_copy = deepcopy(environ)

    # many requirements and providers might need this, plus
    # it's useful for scripts to find their source tree.
    environ_copy['PROJECT_DIR'] = project.directory_path

    provider_registry = ProviderRegistry()

    requirements_and_providers = []
    for requirement in project.requirements:
        providers = requirement.find_providers(provider_registry)
        requirements_and_providers.append((requirement, providers))

    local_state = LocalStateFile.load_for_directory(project.directory_path)

    first_stage = _process_requirements_and_providers(project, environ_copy, local_state, requirements_and_providers)

    def set_vars():
        for key, value in environ_copy.items():
            if key not in environ or environ[key] != value:
                environ[key] = value
        return None

    return _after_stage_success(first_stage, set_vars)


def _default_show_url(url):
    import webbrowser
    webbrowser.open_new_tab(url)


def prepare(project, environ=None, ui_mode=UI_MODE_NOT_INTERACTIVE, io_loop=None, show_url=None):
    """Perform all steps needed to get a project ready to execute.

    This may need to ask the user questions, may start services,
    run scripts, load configuration, install packages... it can do
    anything. Expect side effects.

    Args:
        project (Project): the project
        environ (dict): the environment to prepare (None to use os.environ)
        ui_mode (str): one of ``UI_MODE_TEXT``, ``UI_MODE_BROWSER``, ``UI_MODE_NOT_INTERACTIVE``
        io_loop (IOLoop): tornado IOLoop to use, None for default
        show_url (function): takes a URL and displays it in a browser somehow, None for default

    Returns:
        True if successful.

    """
    if ui_mode not in _all_ui_modes:
        raise ValueError("invalid UI mode " + ui_mode)

    old_current_loop = None
    try:
        if io_loop is None:
            old_current_loop = IOLoop.current()
            io_loop = IOLoop()
            io_loop.make_current()

        if show_url is None:
            show_url = _default_show_url

        if ui_mode == UI_MODE_NOT_INTERACTIVE:
            ui = NotInteractivePrepareUI()
        elif ui_mode == UI_MODE_BROWSER:
            ui = BrowserPrepareUI(io_loop=io_loop, show_url=show_url)

        stage = prepare_in_stages(project, environ)
        while stage is not None:
            # this is a little hack to get code coverage since we will only use
            # the description later after refactoring the UI
            stage.description_of_action
            next_stage = stage.execute(ui)
            if stage.failed:
                return False
            stage = next_stage

    finally:
        if old_current_loop is not None:
            old_current_loop.make_current()

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
