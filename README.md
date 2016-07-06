# Conda Kapsel

Get rid of that long README! It gets outdated, and people don't
read it carefully anyway.

What if your README's instructions could be as short as "type
`conda kapsel run`"?

A _conda kapsel_ is a project directory with some configuration in
a `kapsel.yml`, allowing [conda](https://github.com/conda/conda)
to run the project. Running a project can mean executing any
arbitrary command.

`kapsel.yml` tells conda how to automate project setup; conda can
establish all prerequisite conditions for the project's commands
to execute successfully. These conditions could include:

 * creating a conda environment with certain packages in it
 * prompting the user for passwords or other configuration
 * downloading data files
 * starting extra processes such as a database server

The goal is that if your project runs on your machine, it will
also run on others' machines (or on your future machine after you
reboot a few times and forget how your project works).

*Conda kapsels are reproducible, executable projects.*

All we mean by "project" is a directory full of related stuff that
you're working on; scripts, notebooks, data files, whatever it may
be. Organize it however you like. The command `conda kapsel init
DIRECTORY_NAME` creates a `kapsel.yml`, which includes kapsel
configuration.

## Put another way...

Traditional build scripts such as `setup.py` automate "building"
the project (going from source code to something runnable), while
conda kapsel automates "running" the project (taking build
artifacts and doing any necessary setup prior to executing them).

## Learn more

See ``tutorial.rst`` in this directory for a simple
getting-started walkthrough.

See ``project-config.rst`` in this directory for more detail on
the syntax of the `kapsel.yml` file.

## If you've been using `conda env` and `environment.yml`

`conda kapsel` has similar functionality and may be more
convenient. The advantage of `conda kapsel` for environment
handling is that it performs conda operations _and_ records them
in a config file in one step.

For example, if you do `conda kapsel add-packages bokeh=0.11`,
that will install Bokeh with conda, _and_ add `bokeh=0.11` to an
environment spec in `kapsel.yml` (the effect is comparable to
adding it to `environment.yml`). In this way, "your current conda
environment's state" and "your configuration to be shared with
others" won't get out of sync.

`conda kapsel` will also automatically set up environments for a
colleague when they type `conda kapsel run` on their machine; they
don't have to do a separate step to create, update, or activate
environments before they run the code. This may be especially
useful when you change the required dependencies; with `conda env`
people can forget to re-run it and update their packages, while
`conda kapsel run` will automatically add missing packages every
time.

In addition to environment creation, `conda kapsel` can also
perform other kinds of setup, such as adding data files and
running a database server. It's a superset of `conda env` in that
sense.

# Bug Reports

Please report issues right here on GitHub.

# Contributing

This repository contains command line tools and a library for
manipulating conda kapsels.

 * `python setup.py test` is configured to run all the checks that
   have to pass before you commit or push. It also reformats the
   code with yapf if necessary. Continuous integration runs this
   command so you should run it and make it pass before you push
   to the repo.
 * To only run the formatter and linter, use `python setup.py test
   --format-only`.
 * To only run the tests, use `python -m pytest -vv conda_kapsel`
 * To only run a single file of tests use `python -m pytest
   -vv conda_kapsel/test/test_foo.py`
 * To only run a single test function `python -m pytest
   -vv conda_kapsel/test/test_foo.py::test_something`
 * There's a script `build_and_upload.sh` that should be used to
   manually make a release. The checked-out revision should have
   a version tag prior to running the script.
