# Mechanics

Here's how to work on the code:

 * STEP ONE: you need an environment with the right
   dependencies. A trick is that the formatters/linters need to be
   specific versions, or the warnings and errors may have changed
   which will make tests fail.  The simplest way to get the right
   environment is `conda env create environment.yml` but you can
   also look in that file and/or .travis.yml/appveyor.xml to see
   which packages are neded and then create the dev environment
   by hand as you see fit.
 * NOTE: Do make sure to respect the version pins found in the
   `environment.yml` file. In particular, different versions of
   the reformatting package `yapf` may reformat the code in a
   slightly different manner. This will introduce a number of
   spurious changes to your local clone that will break testing
   in CI if committed.

After you've activated your anaconda-project-dev environment,

 * `python scripts/run_tests.py` is configured to run all the checks that
   have to pass before you commit or push. It also reformats the
   code with yapf if necessary. Continuous integration runs this
   command so you should run it and make it pass before you push
   to the repo.
 * To only run the formatter and linter, use `python scripts/run_tests.py
   --format-only`.
 * If you have added but uncommitted changes, you can use use `python scripts/run_tests.py
   --format-only --git-staged-only` to lint only the added files.
 * To only run the tests, use `python -m pytest -vv anaconda_project`
 * To only run a single file of tests use `python -m pytest
   -vv anaconda_project/test/test_foo.py`
 * To only run a single test function `python -m pytest
   -vv anaconda_project/test/test_foo.py::test_something`
 * To run only "fast" tests, use `python -m pytest -vv -k-slow
   anaconda_project` which skips slow tests. Slow tests have to
   pass in CI, but often it's helfpul to get all the fast tests
   working before debugging the slow ones.
 * There's a script `build_and_upload.sh` that should be used to
   manually make a release. The checked-out revision should have
   a version tag prior to running the script.

# Where to start

The "Help Wanted" label on issues
https://github.com/Anaconda-Platform/anaconda-project/issues means
that the issue might be a good first one to tackle if you're
unfamiliar with the codebase.

Please feel free to ask questions about how to approach an issue.

# Making releases

There's `build_and_upload.sh` script; the flow is:

 * create a signed git tag `vX.Y.Z`
 * run `build_and_upload.sh`
 * push the git tag to the repo

`build_and_upload.sh` assumes you're logged in to anaconda.org and
have permissions to publish.

# Code Tour

It can be hard to get started in an unfamiliar codebase. Here are a few guideposts.

## Read the user docs first!

It'll be tough to figure out the code if you haven't tried using
anaconda-project from a user perspective.

See http://anaconda-project.readthedocs.io/en/latest/index.html

The TLDR is that we're trying to run the commands in the
`commands` section of `anaconda-project.yml`, after setting a
bunch of environment variables including `CONDA_PREFIX` based on
the other configuration in `anaconda-project.yml`. All the code
sort of boils down to that.

## Major pieces

 * `anaconda_project` is our toplevel
   namespace. Non-underscore-prefixed functions, classes, and
   variables immediately under this namespace are intended to form
   a public API for working with projects.
 * The most important starting points for the public API are
   `anaconda_project/project_ops.py` (which contains most
   "verbs"), `anaconda_project/project.py` (which contains the
   `Project` class, the primary "noun"), and
   `anaconda_project/prepare.py` (which is maybe the most
   important verb and thus pulled into its own file).
 * `anaconda_project/internal` contains non-public API that is
   subject to change whenever we feel like it, including lots of
   internal utilities.
 * `anaconda_project/internal/cli` contains the command-line frontend.
 * unit tests are always in a `test` subdirectory next to the file
   being tested.

## Use the CLI to get started

If you start with `anaconda_project/internal/cli`, you can see how
the API gets used and how the command-line operations described in
the documentation map to the API.

## Details of the API

 * `print()` is not allowed to happen due to calling public API.
   This is because the API is used by GUI tools, and if you're
   printing stuff, you're creating a bug (printing something GUI
   users will never see). Instead, you should probably be using or
   adding a method to `Project.frontend`, or returning a value.
 * `anaconda_project/api.py` is a duplicate wrapper around the
   rest of the API which puts the whole API in one class.
   Whenever you modify the public API, you'll probably have to
   update the wrapper in `api.py`. (It probably makes sense to
   remove `api.py` and have only one way to do it.)

## "Prepare", Plugins, Requirement, Provider

In `anaconda_project/prepare.py` you'll see the concept of
"preparing" a project. Preparing a project means checking and if
needed providing all prerequisites prior to running a project
command. The most common prerequisite is a conda environment.

There's a notion in the code as it stands that prerequisites
(represented by the `Requirement` class) and
prerequisite-providers (represented by the `Provider` class) would
be extensible plugins, so these are currently in a directory
`anaconda_project/plugins`. Despite the directory name, at the
moment all the Requirement and Provider subtypes are hard-coded,
not plugins. Currently, we're thinking "plugins" will be able to
do a lot more than extend requirements and providers, when we
implement plugins. So the structure here will need to change.

The code is set up with the idea that checking requirements and
providing them are separate operations. This is to allow
requirements to be met in multiple ways, potentially.

Currently, all requirements boil down to environment variables.
Even creating a conda environment is framed in the code as
"setting CONDA_PREFIX."

The "prepare" operation returns a new dictionary of environment
variables (as `PrepareResult.environ`), where these env variables
should be set in order to run a project command.

### Prepare Modes

There's a notion that there are three ways to "prepare":

 * Production defaults: this won't autostart toy/test databases
   and stuff like that, it will insist that these things are
   preconfigured.
 * Development defaults: autostarts local toy/test services if needed.
 * Check: doesn't do anything, only checks current status.

### Prepare UI

UI considerations affect the prepare API in a couple of ways.

One is that there's a "prepare with browser" notion, which we want
to get rid of
(https://github.com/Anaconda-Platform/anaconda-project/issues/60
).  The turned-out-to-be-useless "browser UI" also motivates some
funky stuff around "configuring" providers that you'll see in the
code. If possible, ignore `anaconda_project/internal/ui_server.py`
and everything associated with it.

Two is that there's a notion of "PrepareStage", which is supposed
to allow breaking up the prepare into phases, so a UI could move
the user through them asking questions as it goes. It's not clear
that this is useful yet, but it might be, or might be with
modifications.

## Use of conda

Right now, all use of conda goes through an interface called
`CondaManager`, which is intended to allow a frontend app to
replace it with a UI-aware alternate conda backend. It's not clear
how practical this really is, since we rely heavily on the
detailed semantics of our `DefaultCondaManager`. But in any case,
the library code isn't supposed to be using
`anaconda_project.internal.conda_api` directly.

## File parsing

The raw YAML handling is in `anaconda_project/yaml_file.py`,
`anaconda_project/project_file.py`,
`anaconda_project/project_lock_file.py` and
`anaconda_project/local_state_file.py`. The semantic sense-making
is in `anaconda_project/project.py`, where we load all of these
files at once and make sense of them (or not) as a whole.

Some of the goals of the file-handling code:

 * give very good error messages; at least _try_ to do better than
   generic "schema was violated" kind of messages
 * often, we can offer to auto-fix problems
 * support the most human-friendly syntax we can, even when it
   would be sort of a headache to describe in a schema language
 * do not ever write out a corrupt file to disk. In
   `project_ops.py` we preflight that the `Project` class can
   reload a proposed modified file before we save it; in
   `yaml_file.py` we preflight that the yaml parser can re-parse a
   file before we save it. So we preflight proposed new files on
   both the syntactic and semantic level before we save.
   We also perform the save atomically (via rename) to avoid
   a half-written file.

## Smart import and auto-fix

There's an idea in the code that if you have a project which is
not an Anaconda Project, that `anaconda-project init` will try to
make sense out of it. For example, it would import your existing
`environment.yml` and add your notebooks and stuff like that.

The initial project init is implemented by creating a default
`anaconda-project.yml` and then saying "yes" to all the "do you
want to fix xyz?" prompts. This means that the same code handles
initial init and also handles later-appearing situations (such as
adding a new notebook file).

However, some things about this are a little weird. An example is
that if you're going through `Project.problems` applying
auto-fixes, fixing one thing could actually change the list of
problems you're iterating over. So the mechanism here may need
some massaging over time depending on what you're trying to do.

## Result objects

Often the code uses return values (such as the `Status` or
`PrepareResult` classes) to return error states, rather than
exceptions. These are easier to deal with when an error is
"expected" and may need to be processed by multiple layers of
code.

## Tests

CI enforces 100% test coverage, which is good because there are
lots of corner cases to worry about! You can modify Anaconda
Project with pretty good confidence because if you break it, the
tests will almost always break.

The main goal of 100% test coverage is to test error handling
codepaths, to be sure they work, and continue to work when
refactoring.  80%-ish coverage generally neglects error codepaths.

Tips for reaching 100% coverage on your new code:

 * monkeypatch! Learn to use pytest's `monkeypatch` feature. Look
   through the existing tests for lots of examples.
 * if you can't figure out how to test some code, are you sure
   it's actually possible for that code to run? Maybe you can
   delete it... more common than you might think.
 * consider changing "if (foo) raise" to "assert not foo";
   use assertions for invariants and impossible situations.

Don't be misled by the 100% number though; you can reach 100%
while leaving quite a few important codepaths untested. That's
because test coverage just means you ran some code on each line in
each file. But it doesn't mean you encountered every condition
_within_ the line, and it doesn't mean you tested all the
important corner cases.

Always first think about important cases that need to work, write
those tests that seem logical, and then run the code coverage
analysis and add tests for anything you missed.

### Avoiding environment creation in tests

Creating conda environments can be pretty slow, so you'll see a
lot of tests use a function called
`project_no_dedicated_env`. This creates a project and sets a flag
in the local state file `inherit_environment`, which means to use
the env that's running the test, instead of making a new one. This
is a hack to speed things up. For tests where you don't want to do
this, and need to create an environment, it's probably good to
mark them with `@pytest.mark.slow`.
