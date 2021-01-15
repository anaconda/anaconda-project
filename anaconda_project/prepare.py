# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Prepare a project to run."""
from __future__ import absolute_import
from __future__ import print_function

from abc import ABCMeta, abstractmethod
import os
from copy import deepcopy

from anaconda_project.internal.metaclass import with_metaclass
from anaconda_project.internal.simple_status import SimpleStatus
from anaconda_project.internal.toposort import toposort_from_dependency_info
from anaconda_project.internal import conda_api
from anaconda_project.internal.py2_compat import is_string
from anaconda_project.local_state_file import LocalStateFile
from anaconda_project.provide import (_all_provide_modes, PROVIDE_MODE_DEVELOPMENT)
from anaconda_project.requirements_registry.provider import ProvideContext
from anaconda_project.requirements_registry.requirement import Requirement, EnvVarRequirement, UserConfigOverrides
from anaconda_project.requirements_registry.requirements.conda_env import CondaEnvRequirement
from anaconda_project.requirements_registry.providers.conda_env import _remove_env_path


def _update_environ(dest, src):
    """Overwrite ``environ`` with any additions from the prepared environ.

    Does not remove any variables from ``environ``.
    """
    # updating os.environ can be a memory leak, so we only update
    # those values that actually changed.
    for key, value in src.items():
        if key not in dest or dest[key] != value:
            dest[key] = value


class PrepareResult(with_metaclass(ABCMeta)):
    """Abstract class describing the result of preparing the project to run."""
    def __init__(self, statuses, environ, overrides, env_spec_name):
        """Construct an abstract PrepareResult."""
        self._statuses = tuple(statuses)
        self._environ = environ
        self._overrides = overrides
        self._env_spec_name = env_spec_name

    def __bool__(self):
        """True if we were successful."""
        return not self.failed

    def __nonzero__(self):
        """True if we were successful."""
        return self.__bool__()  # pragma: no cover (py2 only)

    @property
    @abstractmethod
    def failed(self):
        """True if we failed to do what this stage was intended to do.

        If ``execute()`` returned non-None, the failure may not be fatal; stages
        can continue to be executed and may resolve the issue.
        """
        pass  # pragma: no cover

    @property
    def statuses(self):
        """Get latest RequirementStatus if available.

        If we failed before we even checked statuses, this will be an empty list.
        """
        return self._statuses

    def status_for(self, env_var_or_class):
        """Get status for the given env var or class, or None if unknown."""
        for status in self.statuses:
            if is_string(env_var_or_class):
                if isinstance(status.requirement, EnvVarRequirement) and \
                   status.requirement.env_var == env_var_or_class:
                    return status
            elif isinstance(status.requirement, env_var_or_class):
                return status
        return None

    @property
    def environ(self):
        """Computed environment variables for the project.

        If ``failed`` is True, this environ dict may be unmodified
        from the original provided to the prepare function.
        """
        return self._environ

    @property
    def overrides(self):
        """Override object which was passed to prepare()."""
        return self._overrides

    @property
    def errors(self):
        """Get lines of error output."""
        raise NotImplementedError()  # pragma: no cover

    @property
    def env_spec_name(self):
        """The env spec name we used for the prepare.

        If the project was broken or the user provided bad input
        before we could ask CondaEnvRequirement for the env spec
        name, at the moment we sort of take a guess at the right
        name in order to guarantee this is never None. The
        guessing is a little bit broken. But it would be a very
        obscure scenario where it matters.
        """
        return self._env_spec_name

    @property
    def env_prefix(self):
        """The prefix of the prepared env, or None if none was created."""
        status = self.status_for(CondaEnvRequirement)
        if status is None:
            return None
        varname = status.requirement.env_var
        return self._environ.get(varname, None)


class PrepareSuccess(PrepareResult):
    """Class describing the successful result of preparing the project to run."""
    def __init__(self, statuses, command_exec_info, environ, overrides, env_spec_name):
        """Construct a PrepareSuccess indicating a successful prepare stage."""
        super(PrepareSuccess, self).__init__(statuses, environ, overrides, env_spec_name)
        self._command_exec_info = command_exec_info
        assert self.env_spec_name is not None

    @property
    def failed(self):
        """Get False for PrepareSuccess."""
        return False

    @property
    def command_exec_info(self):
        """``CommandExecInfo`` instance if available, None if not."""
        return self._command_exec_info

    @property
    def errors(self):
        """Get empty list of errors."""
        return []

    def update_environ(self, environ):
        """Overwrite ``environ`` with any additions from the prepared environ.

        Does not remove any variables from ``environ``.
        """
        _update_environ(environ, self._environ)


class PrepareFailure(PrepareResult):
    """Class describing the failed result of preparing the project to run."""
    def __init__(self, statuses, errors, environ, overrides, env_spec_name=None):
        """Construct a PrepareFailure indicating a failed prepare stage."""
        super(PrepareFailure, self).__init__(statuses, environ, overrides, env_spec_name)
        self._errors = errors

    @property
    def failed(self):
        """Get True for PrepareFailure."""
        return True

    @property
    def errors(self):
        """Get non-empty list of errors."""
        return self._errors


class ConfigurePrepareContext(object):
    """Information needed to configure a stage."""
    def __init__(self, environ, local_state_file, default_env_spec_name, overrides, statuses):
        """Construct a ConfigurePrepareContext."""
        self.environ = environ
        self.local_state_file = local_state_file
        self.default_env_spec_name = default_env_spec_name
        self.overrides = overrides
        self.statuses = statuses
        if len(statuses) > 0:
            from anaconda_project.requirements_registry.requirement import RequirementStatus
            assert isinstance(statuses[0], RequirementStatus)


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
        """Synonym for result.failed, only available after ``execute()``."""
        pass  # pragma: no cover

    @abstractmethod
    def configure(self):
        """Get a ``ConfigurePrepareContext`` or None if no configuration is needed.

        Configuration should be done before execute().

        Returns:
          a ``ConfigurePrepareContext`` or None
        """
        pass  # pragma: no cover

    @abstractmethod
    def execute(self):
        """Run this step and return a new stage, or None if we are done or failed."""
        pass  # pragma: no cover

    @property
    @abstractmethod
    def result(self):
        """The ``PrepareResult`` (only available if ``execute()`` has been called)."""
        pass  # pragma: no cover

    @property
    @abstractmethod
    def environ(self):
        """The latest environment variables (from the result if any, otherwise the pre-execute ones)."""
        pass  # pragma: no cover

    @property
    @abstractmethod
    def overrides(self):
        """User overrides."""
        pass  # pragma: no cover

    @property
    @abstractmethod
    def statuses_before_execute(self):
        """``RequirementStatus`` list before execution.

        This list includes all known requirements and their statuses, while the list
        in the ``configure()`` context only includes those that should be configured
        prior to this stage's execution.
        """
        pass  # pragma: no cover

    @property
    @abstractmethod
    def statuses_after_execute(self):
        """``RequirementStatus`` list after execution.

        This list includes all known requirements and their statuses, as changed
        by ``execute()``. This property cannot be read prior to ``execute()``.
        """
        pass  # pragma: no cover


# This is defined to keep the same requirements from old_statuses
# in the refreshed list, even if they are missing from
# rechecked_statuses, and it does not add any new requirements
# from rechecked_statuses to the refreshed list.
def _refresh_status_list(old_statuses, rechecked_statuses):
    new_by_req = dict()
    for status in rechecked_statuses:
        new_by_req[status.requirement] = status
    updated = []
    for status in old_statuses:
        updated.append(new_by_req.get(status.requirement, status))
    return updated


class _FunctionPrepareStage(PrepareStage):
    """A stage chain where the description and the execute function are passed in to the constructor."""
    def __init__(self, environ, overrides, description, statuses, execute, config_context=None):
        assert isinstance(environ, dict)
        assert config_context is None or isinstance(config_context, ConfigurePrepareContext)
        self._environ = environ
        self._overrides = overrides
        # the execute function is supposed to set these two (via accessor)
        self._result = None
        self._statuses_after_execute = None

        self._description = description
        self._statuses_before_execute = statuses
        self._execute = execute
        self._config_context = config_context

    # def __repr__(self):
    #    return "_FunctionPrepareStage(%r)" % (self._description)

    @property
    def description_of_action(self):
        return self._description

    @property
    def failed(self):
        return self.result.failed

    def configure(self):
        return self._config_context

    def execute(self):
        return self._execute(self)

    @property
    def result(self):
        if self._result is None:
            raise RuntimeError("result property isn't available until after execute()")
        return self._result

    @property
    def environ(self):
        if self._result is None:
            return self._environ
        else:
            return self.result.environ

    @property
    def overrides(self):
        return self._overrides

    @property
    def statuses_before_execute(self):
        return self._statuses_before_execute

    @property
    def statuses_after_execute(self):
        if self._statuses_after_execute is None:
            raise RuntimeError("statuses_after_execute isn't available until after execute()")
        return self._statuses_after_execute

    def set_result(self, result, rechecked_statuses):
        assert result is not None
        self._statuses_after_execute = _refresh_status_list(self._statuses_before_execute, rechecked_statuses)
        self._result = result


class _AndThenPrepareStage(PrepareStage):
    """A stage chain which runs an ``and_then`` function after it executes successfully."""
    def __init__(self, stage, and_then):
        self._stage = stage
        self._and_then = and_then

    # def __repr__(self):
    #    return "_AndThenPrepareStage(%r, %r)" % (self._stage, self._and_then)

    @property
    def description_of_action(self):
        return self._stage.description_of_action

    @property
    def failed(self):
        return self._stage.failed

    def configure(self):
        return self._stage.configure()

    def execute(self):
        next = self._stage.execute()
        if next is None:
            if self._stage.failed:
                return None
            else:
                return self._and_then(self._stage.statuses_after_execute)
        else:
            return _AndThenPrepareStage(next, self._and_then)

    @property
    def result(self):
        return self._stage.result

    @property
    def environ(self):
        return self._stage.environ

    @property
    def overrides(self):
        return self._stage.overrides

    @property
    def statuses_before_execute(self):
        return self._stage.statuses_before_execute

    @property
    def statuses_after_execute(self):
        return self._stage.statuses_after_execute


def _after_stage_success(stage, and_then):
    """Run and_then function after stage executes successfully.

    and_then may return another stage, or None. It takes
    the current list of updated statuses as a parameter.
    """
    assert stage is not None
    return _AndThenPrepareStage(stage, and_then)


def _sort_statuses(environ, local_state, statuses, missing_vars_getter):
    def get_node_key(status):
        # If we add a Requirement that isn't an EnvVarRequirement,
        # we can simply return the requirement object here as its
        # own key I believe. But for now that doesn't happen.
        assert hasattr(status.requirement, 'env_var')
        return status.requirement.env_var

    def get_dependency_keys(status):
        config_keys = set()
        for env_var in missing_vars_getter(status):
            config_keys.add(env_var)
        return config_keys

    def can_ignore_dependency_on_key(key):
        # if a key is already in the environment, we don't have to
        # worry about it existing as a node in the graph we are
        # toposorting
        return key in environ

    return toposort_from_dependency_info(statuses, get_node_key, get_dependency_keys, can_ignore_dependency_on_key)


def _in_provide_whitelist(provide_whitelist, requirement):
    if provide_whitelist is None:
        # whitelist of None means "everything"
        return True

    for env_var_or_class_or_req in provide_whitelist:
        if isinstance(env_var_or_class_or_req, Requirement):
            if requirement is env_var_or_class_or_req:
                return True
        elif is_string(env_var_or_class_or_req):
            if isinstance(requirement, EnvVarRequirement) and requirement.env_var == env_var_or_class_or_req:
                return True
        else:
            if isinstance(requirement, env_var_or_class_or_req):
                return True
    return False


def _configure_and_provide(project, environ, local_state, statuses, all_statuses, keep_going_until_success, mode,
                           provide_whitelist, overrides, command, extra_command_args):

    default_env_spec_name = project.default_env_spec_name_for_command(command)

    def provide_stage(stage):
        def get_missing_to_provide(status):
            return status.analysis.missing_env_vars_to_provide

        sorted = _sort_statuses(environ, local_state, statuses, get_missing_to_provide)

        # we have to recheck all the statuses in case configuration happened
        rechecked = []
        for status in sorted:
            rechecked.append(status.recheck(environ, local_state, default_env_spec_name, overrides))

        errors = []
        did_any_providing = False
        results_by_status = dict()

        for status in rechecked:
            if not _in_provide_whitelist(provide_whitelist, status.requirement):
                continue
            elif status.has_been_provided:
                continue
            else:
                did_any_providing = True
                context = ProvideContext(environ, local_state, default_env_spec_name, status, mode, project.frontend)
                result = status.provider.provide(status.requirement, context)
                errors.extend(result.errors)
                results_by_status[status] = result

        if did_any_providing:
            old = rechecked
            rechecked = []
            for status in old:
                rechecked.append(
                    status.recheck(environ,
                                   local_state,
                                   default_env_spec_name,
                                   overrides,
                                   latest_provide_result=results_by_status.get(status)))

        failed = False
        for status in rechecked:
            if not status:
                errors.append("missing requirement to run this project: {requirement.description}".format(
                    requirement=status.requirement))
                project.frontend.error(errors[-1])
                errors.append("  {why_not}".format(why_not=status.status_description))
                project.frontend.error(errors[-1])
                failed = True

        result_statuses = _refresh_status_list(all_statuses, rechecked)

        current_env_spec_name = None
        for status in result_statuses:
            if status.env_spec_name is not None:
                # we're expecting exactly one status to set this,
                # the status from the CondaEnvRequirement. Possibly
                # we sometimes do a prepare with no CondaEnvRequirement?
                # but doing one with two wouldn't make sense afaik.

                # TODO: Should we just remove this? (considering the case of bootstrap env)
                # assert current_env_spec_name is None
                current_env_spec_name = status.env_spec_name

        if failed:
            stage.set_result(
                PrepareFailure(statuses=result_statuses,
                               errors=errors,
                               environ=environ,
                               overrides=overrides,
                               env_spec_name=current_env_spec_name), rechecked)
            if keep_going_until_success:
                return _start_over(stage.statuses_after_execute, rechecked)
            else:
                return None
        else:
            if command is None:
                exec_info = None
            else:
                exec_info = command.exec_info_for_environment(environ, extra_args=extra_command_args)
            stage.set_result(
                PrepareSuccess(statuses=result_statuses,
                               command_exec_info=exec_info,
                               environ=environ,
                               overrides=overrides,
                               env_spec_name=current_env_spec_name), rechecked)
            return None

    def _start_over(updated_all_statuses, updated_statuses):
        configure_context = ConfigurePrepareContext(environ=environ,
                                                    local_state_file=local_state,
                                                    default_env_spec_name=default_env_spec_name,
                                                    overrides=overrides,
                                                    statuses=updated_statuses)
        return _FunctionPrepareStage(environ, overrides, "Set up project.", updated_all_statuses, provide_stage,
                                     configure_context)

    return _start_over(all_statuses, statuses)


def _partition_first_group_to_configure(environ, local_state, statuses):
    def get_missing_to_configure(status):
        return status.analysis.missing_env_vars_to_configure

    sorted = _sort_statuses(environ, local_state, statuses, get_missing_to_configure)

    # We want "head" to be everything up to but not including the
    # first requirement that's missing needed env vars. head
    # should then include the requirement that supplies the
    # missing env var.

    head = []
    tail = []

    sorted.reverse()  # to efficiently pop
    while sorted:
        status = sorted.pop()

        missing_vars = status.provider.missing_env_vars_to_configure(status.requirement, environ, local_state)

        if len(missing_vars) > 0:
            tail.append(status)
            break
        else:
            head.append(status)

    sorted.reverse()  # put it back in order
    tail.extend(sorted)

    return (head, tail)


def _process_requirement_statuses(project, environ, local_state, current_statuses, all_statuses,
                                  keep_going_until_success, mode, provide_whitelist, overrides, command,
                                  extra_command_args):
    (initial, remaining) = _partition_first_group_to_configure(environ, local_state, current_statuses)

    # a surprising thing here is that the "stages" from
    # _configure_and_provide() can be user-visible, so we always
    # want at least one (even when all the lists are empty), but
    # we don't want to pointlessly create two by splitting off an
    # empty list when we already have a list. So we want two
    # _configure_and_provide() only if there are two non-empty lists,
    # but we always want at least one _configure_and_provide()

    def _stages_for(statuses):
        return _configure_and_provide(project, environ, local_state, statuses, all_statuses, keep_going_until_success,
                                      mode, provide_whitelist, overrides, command, extra_command_args)

    if len(initial) > 0 and len(remaining) > 0:

        def process_remaining(updated_all_statuses):
            # get the new status for each remaining requirement
            updated = _refresh_status_list(remaining, updated_all_statuses)
            return _process_requirement_statuses(project, environ, local_state, updated, updated_all_statuses,
                                                 keep_going_until_success, mode, provide_whitelist, overrides, command,
                                                 extra_command_args)

        return _after_stage_success(_stages_for(initial), process_remaining)
    elif len(initial) > 0:
        return _stages_for(initial)
    else:
        # this branch would happen if a requirement depends on an
        # already-met requirement, right now our only dependency
        # is on the env prefix which we always unset at the start
        # of prepare, so this should be unreachable. Keeping this
        # code though because in future we might want it back.
        assert False, "This code should not be reachable, bug!"  # pragma: no cover
        return _stages_for(remaining)  # pragma: no cover (not reachable)


# this used to create requirement objects for missing reqs, but
# at the moment missing reqs aren't possible, so it's changed to
# an assertion until it's possible again.
def _assert_no_missing_env_var_requirements(project, environ, local_state, overrides, command, statuses):
    by_env_var = dict()
    for status in statuses:
        # if we add requirements with no env_var, change this to
        # skip those requirements here
        assert hasattr(status.requirement, 'env_var')
        by_env_var[status.requirement.env_var] = status.requirement

    needed_env_vars = set()
    for status in statuses:
        needed_env_vars.update(status.provider.missing_env_vars_to_configure(status.requirement, environ, local_state))
        needed_env_vars.update(status.provider.missing_env_vars_to_provide(status.requirement, environ, local_state))

    # created_anything = False

    for env_var in needed_env_vars:
        assert env_var in by_env_var

    #     if env_var not in by_env_var:
    #         created_anything = True
    #         requirement = project.plugin_registry.find_requirement_by_env_var(env_var, options=dict())
    #         statuses.append(requirement.check_status(environ,
    #                                                  local_state,
    #                                                  project.default_env_spec_name_for_command(command),
    #                                                  overrides,
    #                                                  latest_provide_result=None))

    # if created_anything:
    #     # run the whole above again to find any transitive requirements of the new providers
    #     _add_missing_env_var_requirements(project, environ, local_state, overrides, command, statuses)


def _first_stage(project, environ, local_state, statuses, keep_going_until_success, mode, provide_whitelist, overrides,
                 command, extra_command_args):
    assert 'PROJECT_DIR' in environ

    _assert_no_missing_env_var_requirements(project, environ, local_state, overrides, command, statuses)

    first_stage = _process_requirement_statuses(project, environ, local_state, statuses, statuses,
                                                keep_going_until_success, mode, provide_whitelist, overrides, command,
                                                extra_command_args)

    return first_stage


def _prepare_environ_and_overrides(project, environ=None, env_spec_name=None):
    if environ is None:
        environ = os.environ

    assert 'PATH' in environ

    # we modify a copy, which 1) makes all our changes atomic and
    # 2) minimizes memory leaks on systems that use putenv().
    #
    # On Linux, it appears we must use deepcopy (vs plain copy) or
    # we still modify os.environ somehow.
    #
    # On the Windows CI server, but NOT on my local Windows 10
    # machine, deepcopy() didn't work but adding the extra .copy()
    # fixed it. The failure mode was that changes to PATH in the
    # copy were not visible via os.environ or os.getenv('PATH'),
    # but they DID affect what subprocess.Popen was able to see,
    # so that a test which modified PATH in this environ_copy
    # would break subsequent tests (such as test_conda_api which
    # tries to run conda). Anyway, presumably this is a bug in
    # something, but I'm not sure in what. If you can remove the
    # extra copy() and still pass all tests on all platforms at
    # some point in the future, feel free to clean up this
    # hackery.
    environ_copy = deepcopy(environ.copy())

    # many requirements and providers might need this, plus
    # it's useful for scripts to find their source tree.
    environ_copy['PROJECT_DIR'] = project.directory_path

    # Save and then clear out any existing environment
    existing_env_prefix = conda_api.environ_get_prefix(environ_copy)
    conda_api.environ_delete_prefix_variables(environ_copy)

    overrides = UserConfigOverrides(env_spec_name=env_spec_name, inherited_env=existing_env_prefix)

    return (environ_copy, overrides)


def _internal_prepare_in_stages(project, environ_copy, overrides, keep_going_until_success, mode, provide_whitelist,
                                command_name, command, extra_command_args, refresh):
    assert not project.problems
    if mode not in _all_provide_modes:
        raise ValueError("invalid provide mode " + mode)

    assert not (command_name is not None and command is not None)
    assert command_name is None or (command_name in project.commands) or (command_name == 'default')
    assert overrides.env_spec_name is None or overrides.env_spec_name in project.env_specs

    if command is None:
        command = project.command_for_name(command_name)
        # at this point, "command" is only None if there are no
        # commands for this project.
    default_env_name = project.default_env_spec_name_for_command(command)

    our_root = project.directory_path
    local_state = LocalStateFile.load_for_directory(our_root)

    if refresh:
        # To do: move the refresh flag into the provider somehow. Thought: add
        # the refresh flag to overrides, and have the conda env requirements
        # engine interpret that and schedule a refresh and create.
        env_name = overrides.env_spec_name or default_env_name
        _remove_env_path(project.env_specs[env_name].path(our_root), our_root)

    statuses = []
    for requirement in project.requirements(overrides.env_spec_name):
        status = requirement.check_status(environ_copy,
                                          local_state,
                                          default_env_name,
                                          overrides,
                                          latest_provide_result=None)
        statuses.append(status)

    return _first_stage(project, environ_copy, local_state, statuses, keep_going_until_success, mode, provide_whitelist,
                        overrides, command, extra_command_args)


def prepare_in_stages(project,
                      environ=None,
                      keep_going_until_success=False,
                      mode=PROVIDE_MODE_DEVELOPMENT,
                      provide_whitelist=None,
                      env_spec_name=None,
                      command_name=None,
                      command=None,
                      extra_command_args=None,
                      refresh=False):
    """Get a chain of all steps needed to get a project ready to execute.

    This function does not immediately do anything; it returns a
    ``PrepareStage`` object which can be executed. Executing each
    stage may return a new stage, or may return ``None``. If a
    stage returns ``None``, preparation is done and the ``failed``
    property of the stage indicates whether it failed.

    Executing a stage may ask the user questions, may start
    services, run scripts, load configuration, install
    packages... it can do anything. Expect side effects.

    Before calling this function, command_name must be validated
    (must be in ``project.commands``, or be ``None``) and
    ``project.problems`` must be empty.

    Args:
        project (Project): the project
        environ (dict): the environment to start from (None to use os.environ)
        keep_going_until_success (bool): keep returning new stages until all requirements are met
        mode (str): One of ``PROVIDE_MODE_PRODUCTION``, ``PROVIDE_MODE_DEVELOPMENT``, ``PROVIDE_MODE_CHECK``
        provide_whitelist (iterable of str): ONLY call provide() for the listed env vars' requirements
        env_spec_name (str): the environment spec name to require, or None for default
        command_name (str): which named command to choose from the project, None for default
        command (ProjectCommand): command object, None for default
        extra_command_args (list of str): extra args for the command we prepare
        refresh (bool): do a full reinstall of the environment

    Returns:
        The first ``PrepareStage`` in the chain of steps.

    """
    (environ_copy, overrides) = _prepare_environ_and_overrides(project, environ, env_spec_name)

    return _internal_prepare_in_stages(project,
                                       environ_copy=environ_copy,
                                       overrides=overrides,
                                       keep_going_until_success=keep_going_until_success,
                                       mode=mode,
                                       provide_whitelist=provide_whitelist,
                                       command_name=command_name,
                                       command=command,
                                       extra_command_args=extra_command_args,
                                       refresh=refresh)


def _project_problems_to_prepare_failure(project, environ, overrides, would_have_used_env_spec):
    if project.problems:
        errors = []
        for problem in project.problems:
            errors.append(problem)
            project.frontend.error(problem)
        error = "Unable to load the project."
        errors.append(error)
        project.frontend.error(error)

        return PrepareFailure(statuses=(),
                              errors=errors,
                              environ=environ,
                              overrides=overrides,
                              env_spec_name=would_have_used_env_spec)
    else:
        return None


def _prepare_failure_on_bad_command_name(project, command_name, environ, overrides, would_have_used_env_spec):
    if command_name == 'default':
        command_name = project.default_command.name
    elif command_name is not None and command_name not in project.commands:
        error = ("Command name '%s' is not in %s, these names were found: %s" %
                 (command_name, project.project_file.filename, ", ".join(sorted(project.commands.keys()))))
        project.frontend.error(error)
        return PrepareFailure(statuses=(),
                              errors=[error],
                              environ=environ,
                              overrides=overrides,
                              env_spec_name=would_have_used_env_spec)
    else:
        return None


def _prepare_failure_on_bad_env_spec_name(project, env_spec_name, environ, overrides, would_have_used_env_spec):
    if env_spec_name is not None and env_spec_name not in project.env_specs:
        error = ("Environment name '%s' is not in %s, these names were found: %s" %
                 (env_spec_name, project.project_file.filename, ", ".join(sorted(project.env_specs.keys()))))
        project.frontend.error(error)
        return PrepareFailure(statuses=(),
                              errors=[error],
                              environ=environ,
                              overrides=overrides,
                              env_spec_name=would_have_used_env_spec)
    else:
        return None


def _check_prepare_prerequisites(project, env_spec_name, command_name, command, environ, overrides):
    assert not (command_name is not None and command is not None)

    if command is None:
        command = project.command_for_name(command_name)
        # at this point, "command" is only None if there are no
        # commands for this project.

        # this is sort of a hack to predict which env spec the
        # CondaEnvRequirement will report in its status, since we may
        # not get to checking its status if these prereqs fail.  I'm
        # not sure yet how to refactor to avoid duplicating this logic
        # with CondaEnvRequirement; one thing we fail to handle here
        # is if CONDA_PREFIX is already set and we are in
        # inherit_environment=true mode.
    would_have_used_env_spec = overrides.env_spec_name
    if would_have_used_env_spec is None:
        if command is None:
            would_have_used_env_spec = project.default_env_spec_name
        else:
            would_have_used_env_spec = project.default_env_spec_name_for_command(command)

    failed = _project_problems_to_prepare_failure(project, environ, overrides, would_have_used_env_spec)
    if failed is None:
        failed = _prepare_failure_on_bad_env_spec_name(project, env_spec_name, environ, overrides,
                                                       would_have_used_env_spec)
    if failed is None:
        failed = _prepare_failure_on_bad_command_name(project, command_name, environ, overrides,
                                                      would_have_used_env_spec)
    return failed


def prepare_without_interaction(project,
                                environ=None,
                                mode=PROVIDE_MODE_DEVELOPMENT,
                                provide_whitelist=None,
                                env_spec_name=None,
                                command_name=None,
                                command=None,
                                extra_command_args=None,
                                refresh=False):
    """Prepare a project to run one of its commands.

    This method doesn't ask the user any questions, so the
    ``provide_mode`` lets you specify defaults suitable for a
    local workstation, a production deployment, or "check only"
    defaults ("check only" means don't do anything just check
    status).

    This method returns a result object. The result object has
    a ``failed`` property.  If the result is failed, the
    ``errors`` property has the errors.  If the result is not
    failed, the ``command_exec_info`` property has the stuff
    you need to run the project's default command, and the
    ``environ`` property has the updated environment. The
    passed-in ``environ`` is not modified in-place.

    You can update your original environment with
    ``result.update_environ()`` if you like, but it's probably
    a bad idea to modify ``os.environ`` in that way because
    the calling app won't want to have the project
    environment.

    The ``environ`` should usually be kept between
    preparations, starting out as ``os.environ`` but then
    being modified by the user.

    If the project has a non-empty ``problems`` attribute,
    this function returns the project problems inside a failed
    result. So ``project.problems`` does not need to be checked in
    advance.

    Args:
        project (Project): from the ``load_project`` method
        environ (dict): os.environ or the previously-prepared environ; not modified in-place
        mode (str): mode from ``PROVIDE_MODE_PRODUCTION``, ``PROVIDE_MODE_DEVELOPMENT``, ``PROVIDE_MODE_CHECK``
        provide_whitelist (iterable of str): ONLY call provide() for the listed env vars' requirements
        env_spec_name (str): the environment spec name to require, or None for default
        command_name (str): which named command to choose from the project, None for default
        command (ProjectCommand): command object, None for default
        extra_command_args (list): extra args to include in the returned command argv

    Returns:
        a ``PrepareResult`` instance, which has a ``failed`` flag

    """
    (environ_copy, overrides) = _prepare_environ_and_overrides(project, environ, env_spec_name)

    failure = _check_prepare_prerequisites(project, env_spec_name, command_name, command, environ_copy, overrides)
    if failure is not None:
        return failure

    stage = _internal_prepare_in_stages(project,
                                        environ_copy=environ_copy,
                                        overrides=overrides,
                                        keep_going_until_success=False,
                                        mode=mode,
                                        provide_whitelist=provide_whitelist,
                                        command_name=command_name,
                                        command=command,
                                        extra_command_args=extra_command_args,
                                        refresh=refresh)

    return prepare_execute_without_interaction(stage)


def prepare_execute_without_interaction(stage):
    """Advance through the PrepareStage without any interactivity.

    Returns:
       a ``PrepareResult`` instance
    """
    result = None
    while stage is not None:
        next_stage = stage.execute()
        result = stage.result
        if result.failed:
            break
        stage = next_stage
    return result


def unprepare(project, prepare_result, whitelist=None):
    """Attempt to clean up project-scoped resources allocated by prepare().

    This will retain any user configuration choices about how to
    provide requirements, but it stops project-scoped services.
    Global system services or other services potentially shared
    among projects will not be stopped.

    To stop a single service, use ``whitelist=["SERVICE_VARIABLE"]``.

    Args:
        project (Project): the project
        prepare_result (PrepareResult): result from the previous prepare
        whitelist (iterable of str or type): ONLY call shutdown commands for the listed env vars' requirements

    Returns:
        a ``Status`` instance
    """
    if project.problems:
        errors = []
        for problem in project.problems:
            errors.append(problem)
            project.frontend.error(problem)
        return SimpleStatus(success=False, description="Unable to load the project.", errors=errors)

    local_state_file = LocalStateFile.load_for_directory(project.directory_path)

    # note: if the prepare_result was a failure before statuses
    # were even checked, then statuses could be empty
    failed_statuses = []
    failed_requirements = []
    success_statuses = []
    for status in prepare_result.statuses:
        requirement = status.requirement
        if not _in_provide_whitelist(whitelist, requirement):
            continue

        provider = status.provider
        unprovide_status = provider.unprovide(requirement, prepare_result.environ, local_state_file,
                                              prepare_result.overrides, status)
        if not unprovide_status:
            failed_requirements.append(requirement)
            failed_statuses.append(unprovide_status)
        else:
            success_statuses.append(unprovide_status)

    if not failed_statuses:
        if len(success_statuses) > 1:
            for message in [status.status_description for status in success_statuses]:
                project.frontend.info(message)
            return SimpleStatus(success=True, description="Success.")
        elif len(success_statuses) > 0:
            return success_statuses[0]
        else:
            return SimpleStatus(success=True, description="Nothing to clean up.")
    elif len(failed_statuses) == 1:
        for error in failed_statuses[0].errors:
            project.frontend.error(error)
        return failed_statuses[0]
    else:
        all_errors = [error for status in failed_statuses for error in [status.errors + [status.status_description]]]
        all_names = sorted([req.env_var for req in failed_requirements if isinstance(req, EnvVarRequirement)])
        for error in all_errors:
            project.frontend.error(error)

        return SimpleStatus(success=False,
                            description=("Failed to clean up %s." % ", ".join(all_names)),
                            errors=all_errors)
