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
from project.internal.toposort import toposort_from_dependency_info
from project.local_state_file import LocalStateFile
from project.plugins.provider import ProvideContext, ProviderRegistry, ProviderConfigContext

UI_MODE_TEXT = "text"
UI_MODE_BROWSER = "browser"
UI_MODE_NOT_INTERACTIVE = "not_interactive"

_all_ui_modes = (UI_MODE_TEXT, UI_MODE_BROWSER, UI_MODE_NOT_INTERACTIVE)


def _update_environ(dest, src):
    """Overwrite ``environ`` with any additions from the prepared environ.

    Does not remove any variables from ``environ``.
    """
    # updating os.environ can be a memory leak, so we only update
    # those values that actually changed.
    for key, value in src.items():
        if key not in dest or dest[key] != value:
            dest[key] = value


class CommandExecInfo(object):
    """Class describing an executable command."""

    def __init__(self, cwd, args, env):
        """Construct an CommandExecInfo."""
        self._cwd = cwd
        self._args = args
        self._env = env

    @property
    def cwd(self):
        """Working directory to run the command in."""
        return self._cwd

    @property
    def args(self):
        """Command line argument vector to run the command."""
        return self._args

    @property
    def env(self):
        """Environment to run the command in."""
        return self._env

    def popen(self, **kwargs):
        """Convenience method runs the command using Popen.

        Args:
            kwargs: passed through to Popen

        Returns:
            Popen instance
        """
        import subprocess

        return subprocess.Popen(args=self._args, env=self._env, cwd=self._cwd, **kwargs)

    def execvpe(self):
        """Convenience method exec's the command replacing the current process.

        Returns:
            Does not return. May raise an OSError though.
        """
        try:
            old_dir = os.getcwd()
            os.chdir(self._cwd)
            sys.stderr.flush()
            sys.stdout.flush()
            os.execvpe(self._args[0], self._args, self._env)
        finally:
            # avoid side effect if exec fails (or is mocked in tests)
            os.chdir(old_dir)


class PrepareResult(with_metaclass(ABCMeta)):
    """Abstract class describing the result of preparing the project to run."""

    def __init__(self, logs):
        """Construct an abstract PrepareResult."""
        self._logs = logs

    def __bool__(self):
        """True if we were successful."""
        return not self.failed

    def __nonzero__(self):
        """True if we were successful."""
        return self.__bool__()  # pragma: no cover (py2 only)

    @property
    @abstractmethod
    def failed(self):
        """True if we failed to prepare the project to run."""
        pass  # pragma: no cover

    @property
    def logs(self):
        """Get lines of debug log output.

        Does not include errors in case of failure. This is the
        "stdout" logs only.
        """
        return self._logs

    def print_output(self):
        """Print logs and errors to stdout and stderr."""
        for log in self.logs:
            print(log, file=sys.stdout)
            # be sure we print all these before the errors
            sys.stdout.flush()


class PrepareSuccess(PrepareResult):
    """Class describing the successful result of preparing the project to run."""

    def __init__(self, logs, command_exec_info, environ):
        """Construct a PrepareSuccess indicating a successful prepare stage."""
        super(PrepareSuccess, self).__init__(logs)
        self._command_exec_info = command_exec_info
        self._environ = environ

    @property
    def failed(self):
        """Get False for PrepareSuccess."""
        return False

    @property
    def command_exec_info(self):
        """``CommandExecInfo`` instance if available, None if not."""
        return self._command_exec_info

    @property
    def environ(self):
        """Computed environment variables for the project."""
        return self._environ

    def update_environ(self, environ):
        """Overwrite ``environ`` with any additions from the prepared environ.

        Does not remove any variables from ``environ``.
        """
        _update_environ(environ, self._environ)


class PrepareFailure(PrepareResult):
    """Class describing the failed result of preparing the project to run."""

    def __init__(self, logs, errors):
        """Construct a PrepareFailure indicating a failed prepare stage."""
        super(PrepareFailure, self).__init__(logs)
        self._errors = errors

    @property
    def failed(self):
        """Get True for PrepareFailure."""
        return True

    @property
    def errors(self):
        """Get lines of error output."""
        return self._errors

    def print_output(self):
        """Override superclass to also print errors."""
        super(PrepareFailure, self).print_output()
        for error in self.errors:
            print(error, file=sys.stderr)


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

    @property
    @abstractmethod
    def result(self):
        """The ``PrepareResult`` (only available if ``execute()`` returned None)."""
        pass  # pragma: no cover


class _FunctionPrepareStage(PrepareStage):
    """A stage chain where the description and the execute function are passed in to the constructor."""

    def __init__(self, description, execute):
        self._result = None
        self._description = description
        self._execute = execute

    @property
    def description_of_action(self):
        return self._description

    @property
    def failed(self):
        return self.result.failed

    def execute(self, ui):
        return self._execute(self, ui)

    @property
    def result(self):
        if self._result is None:
            raise RuntimeError("result property isn't available until execute() returns None")
        return self._result


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

    @property
    def result(self):
        return self._stage.result


def _after_stage_success(stage, and_then):
    """Run and_then function after stage executes successfully.

    and_then may return another stage, or None.
    """
    assert stage is not None
    return _AndThenPrepareStage(stage, and_then)


def _sort_requirements_and_providers(environ, local_state, requirements_and_providers, missing_vars_getter):
    def get_node_key(requirement_and_providers):
        # If we add a Requirement that isn't an EnvVarRequirement,
        # we can simply return the requirement object here as its
        # own key I believe. But for now that doesn't happen.
        assert hasattr(requirement_and_providers[0], 'env_var')
        return requirement_and_providers[0].env_var

    def get_dependency_keys(requirement_and_providers):
        config_keys = set()
        for provider in requirement_and_providers[1]:
            for env_var in missing_vars_getter(provider, requirement_and_providers[0], environ, local_state):
                config_keys.add(env_var)
        return config_keys

    def can_ignore_dependency_on_key(key):
        # if a key is already in the environment, we don't have to
        # worry about it existing as a node in the graph we are
        # topsorting
        return key in environ

    return toposort_from_dependency_info(requirements_and_providers, get_node_key, get_dependency_keys,
                                         can_ignore_dependency_on_key)


def _configure_and_provide(project, environ, local_state, requirements_and_providers):
    def configure_stage(stage, ui):
        configure_context = ConfigurePrepareContext(environ=environ,
                                                    local_state_file=local_state,
                                                    requirements_and_providers=requirements_and_providers)

        # wait for the configure UI if any
        ui.configure(configure_context)

        stage._result = PrepareSuccess(logs=(), command_exec_info=None, environ=environ)

        return _FunctionPrepareStage("Set up project requirements.", provide_stage)

    def provide_stage(stage, ui):
        # the plan is a list of (provider, requirement) in order we
        # should run it.  our algorithm to decide on this may be
        # getting more complicated for example we should be able to
        # ignore any disabled providers, or prefer certain providers,
        # etc.

        def get_missing_to_provide(provider, requirement, environ, local_state):
            return provider.missing_env_vars_to_provide(requirement, environ, local_state)

        sorted = _sort_requirements_and_providers(environ, local_state, requirements_and_providers,
                                                  get_missing_to_provide)

        plan = []
        for (requirement, providers) in sorted:
            for provider in providers:
                plan.append((provider, requirement))

        logs = []
        errors = []

        for (provider, requirement) in plan:
            why_not = requirement.why_not_provided(environ)
            if why_not is None:
                continue
            config_context = ProviderConfigContext(environ, local_state, requirement)
            config = provider.read_config(config_context)
            context = ProvideContext(environ, local_state, config)
            provider.provide(requirement, context)
            logs.extend(context.logs)
            errors.extend(context.errors)

        failed = False
        for (requirement, providers) in requirements_and_providers:
            why_not = requirement.why_not_provided(environ)
            if why_not is not None:
                errors.append("missing requirement to run this project: {requirement.title}"
                              .format(requirement=requirement))
                errors.append("  {why_not}".format(why_not=why_not))
                failed = True

        if failed:
            stage._result = PrepareFailure(logs=logs, errors=errors)
        else:
            exec_info = None
            if project.launch_argv is not None:
                argv = project.launch_argv_for_environment(environ)
                # conda.misc.launch() uses the home directory
                # instead of the project directory as cwd when
                # running an installed package, but for our
                # purposes where we know we have a project dir
                # that's user-interesting, project directory seems
                # more useful. This way apps can for example find
                # sample data files relative to the project
                # directory.
                exec_info = CommandExecInfo(cwd=project.directory_path, args=argv, env=environ)
            stage._result = PrepareSuccess(logs=logs, command_exec_info=exec_info, environ=environ)
        return None

    return _FunctionPrepareStage("Customize how project requirements will be met.", configure_stage)


def _partition_first_group_to_configure(environ, local_state, requirements_and_providers):
    def get_missing_to_configure(provider, requirement, environ, local_state):
        return provider.missing_env_vars_to_configure(requirement, environ, local_state)

    sorted = _sort_requirements_and_providers(environ, local_state, requirements_and_providers,
                                              get_missing_to_configure)

    # We want "head" to be everything up to but not including the
    # first requirement that's missing needed env vars. head
    # should then include the requirement that supplies the
    # missing env var.

    head = []
    tail = []

    sorted.reverse()  # to efficiently pop
    while sorted:
        requirement_and_providers = sorted.pop()

        missing_vars = False
        for provider in requirement_and_providers[1]:
            if len(provider.missing_env_vars_to_configure(requirement_and_providers[0], environ, local_state)) > 0:
                missing_vars = True

        if missing_vars:
            tail.append(requirement_and_providers)
            break
        else:
            head.append(requirement_and_providers)

    sorted.reverse()  # put it back in order
    tail.extend(sorted)

    return (head, tail)


def _process_requirements_and_providers(project, environ, local_state, requirements_and_providers):
    (initial, remaining) = _partition_first_group_to_configure(environ, local_state, requirements_and_providers)

    # a surprising thing here is that the "stages" from
    # _configure_and_provide() can be user-visible, so we always
    # want at least one (even when all the lists are empty), but
    # we don't want to pointlessly create two by splitting off an
    # empty list when we already have a list. So we want two
    # _configure_and_provide() only if there are two non-empty lists,
    # but we always want at least one _configure_and_provide()

    def _stages_for(requirements_and_providers):
        return _configure_and_provide(project, environ, local_state, requirements_and_providers)

    if len(initial) > 0 and len(remaining) > 0:

        def process_remaining():
            return _process_requirements_and_providers(project, environ, local_state, remaining)

        return _after_stage_success(_stages_for(initial), process_remaining)
    elif len(initial) > 0:
        return _stages_for(initial)
    else:
        return _stages_for(remaining)


def _add_missing_env_var_requirements(project, provider_registry, environ, local_state, requirements_and_providers):
    by_env_var = dict()
    for (requirement, providers) in requirements_and_providers:
        # if we add requirements with no env_var, change this to
        # skip those requirements here
        assert hasattr(requirement, 'env_var')
        by_env_var[requirement.env_var] = requirement

    needed_env_vars = set()
    for (requirement, providers) in requirements_and_providers:
        for provider in providers:
            needed_env_vars.update(provider.missing_env_vars_to_configure(requirement, environ, local_state))
            needed_env_vars.update(provider.missing_env_vars_to_provide(requirement, environ, local_state))

    created_anything = False

    for env_var in needed_env_vars:
        if env_var not in by_env_var:
            created_anything = True
            requirement = project.requirement_registry.find_by_env_var(env_var, options=dict())
            providers = requirement.find_providers(provider_registry)
            requirements_and_providers.append((requirement, tuple(providers)))

    if created_anything:
        # run the whole above again to find any transitive requirements of the new providers
        _add_missing_env_var_requirements(project, provider_registry, environ, local_state, requirements_and_providers)


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
        environ (dict): the environment to start from (None to use os.environ)

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
        requirements_and_providers.append((requirement, tuple(providers)))

    local_state = LocalStateFile.load_for_directory(project.directory_path)

    _add_missing_env_var_requirements(project, provider_registry, environ, local_state, requirements_and_providers)

    first_stage = _process_requirements_and_providers(project, environ_copy, local_state, requirements_and_providers)

    return first_stage


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
        a ``PrepareResult`` instance

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

        result = None
        stage = prepare_in_stages(project, environ)
        while stage is not None:
            # this is a little hack to get code coverage since we will only use
            # the description later after refactoring the UI
            stage.description_of_action
            next_stage = stage.execute(ui)
            result = stage.result
            if result.failed:
                break
            stage = next_stage

    finally:
        if old_current_loop is not None:
            old_current_loop.make_current()

    if result.failed:
        result.print_output()

    return result


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
