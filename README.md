# Anaconda Projects

This project contains command line tools and a library for
manipulating projects. A project in this sense is a directory full
of Python scripts, notebooks, Bokeh applications, or other
runnable items. Anaconda Project knows how to resolve
requirements - including runtime requirements such as services and
configuration - before running the project's code.

The general architecture of Anaconda Project is that there are
_requirements_ and _providers_, where requirements are a thing we
need (such as an installed package, running service, etc.), and
providers are able to provide a requirement. Many requirements are
simply environment variable names or package names. Providers are
plugins that know how to take actions to meet requirements, for
example the `ProjectScopedRedisProvider` knows how to start a
dedicated `redis-server` scoped to a particular project.

# Contributing

`python setup.py test` is configured to run all the checks that
have to pass before you commit or push. It also reformats the code
with yapf if necessary.


# Files Anaconda Project cares about

## `PROJECTDIR/project.yml`

A project source directory can contain a `project.yml`
file. `project.yml` contains items which are constant across
machines and users; that is, it's intended to go in source control
or to be distributed when you hand the project directory to
someone else.

## `PROJECTDIR/.anaconda/project-local.yml`

This file contains state that is NOT shared across machines and
users; it's scoped to the project directory and wouldn't go in
source control.

## `PROJECTDIR/.anaconda/run/SERVICE_NAME`

When Anaconda Project launches a service, it will often configure
that service to place its state (such as logs and pid files) in a
directory underneath `.anaconda/run/`

## `PROJECTDIR/conda.recipe/meta.yaml`

Defined by conda, we look in here for info we didn't find in
project.yml to keep people from having to keep the two files in
sync: http://conda.pydata.org/docs/building/meta-yaml.html

# `project.yml` Schema

* `runtime`: Defines runtime requirements, which are provided to
  the running project as environment variables. Contains either a
  list of environment variable names, or a dict with environment
  variable names as keys and options affecting those variables.
  All the listed environment variables have to be set, one way or
  another, before running the project.
* `package`: Some fields in `conda.recipe/meta.yml` can be set
  here instead, if you either don't have a conda recipe or
  want to override it for Anaconda Project purposes.
  Fields we look at right now: `name`, `version`
* `commands`: A dictionary from command names to command
  attributes, where the attributes can be `conda_app_entry` (same
  as app:entry: in meta.yaml), `shell` (shell command line),
  `windows` (windows cmd.exe command line).
* `requirements`: the `run` requirements can be in here or in `meta.yaml`

# `project-local.yml` Schema

* `service_run_states`: Defines a dict from service name to
  service state, where the service name is something unique to the
  provider plugin, and the dict can contain plugin-specific
  information.
  * `service_run_states: SERVICE_NAME: shutdown_commands`: in the
    service run state, there can be a list of shutdown commands,
    where each command is itself a list (suitable for passing to
    exec, that is an argv list). To remove a running service
    the Anaconda Project tools can run the `shutdown_commands` for
    a service run state and then delete the run state.
* `variables`: Defines a dict from environment variable names to
  values. These environment variables will be force-set to the
  provided value (overriding the existing environment).
* `runtime: VAR_NAME: providers: PROVIDER_NAME`: if there's a
  `runtime: VAR_NAME` in the project.yml, this setting in
  project-local.yml holds a dict of options for that provider.
  This is used to save local configuration of the provider.

# Environment Variables Anaconda Project cares about

* `PROJECT_DIR` will be set to the root directory of the project
  we're in
* Currently bundled modules understand how to provide:
   - `REDIS_URL`
   - `CONDA_ENV_PATH`
