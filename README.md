# Anaconda Project

*Reproducible, executable project directories.*

Take any directory full of stuff that you're working on; web apps,
scripts, Jupyter notebooks, data files, whatever it may be.

By adding an `anaconda-project.yml` to this project directory, you
can tell the Anaconda platform how to run it. The simplest way to
run it, using command line tools, is `anaconda-project run`.

Anaconda projects should run in the same way on your machine, on a
colleague's machine, or when deployed to a server.

Running an Anaconda project executes a command specified in the
`anaconda-project.yml` (any arbitrary commands can be configured).

`anaconda-project.yml` automates project setup; Anaconda can
establish all prerequisite conditions for the project's commands
to execute successfully. These conditions could include:

 * creating a conda environment with certain packages in it
 * prompting the user for passwords or other configuration
 * downloading data files
 * starting extra processes such as a database server

The goal is that if your project runs on your machine, it will
also run on others' machines (or on your future machine after you
reboot a few times and forget how your project works).

The command `anaconda-project init DIRECTORY_NAME` creates an
`anaconda-project.yml`, converting your project directory into an
Anaconda project.

## Put another way...

Traditional build scripts such as `setup.py` automate "building"
the project (going from source code to something runnable), while
`anaconda-project` automates "running" the project (taking build
artifacts and doing any necessary setup prior to executing them).

## Why?

 * Do you have a README with setup steps in it? You may find that
   it gets outdated, or that people don't read it, and then you
   have to help them diagnose the problem. `anaconda-project`
   automates the setup steps; the README can say "type
   `anaconda-project run`" and that's it.
 * Do you need everyone working on a project to have the same
   dependencies in their conda environment? `anaconda-project`
   automates environment creation and verifies that environments
   have the right versions of packages.
 * Do you sometimes include your personal passwords or secret keys
   in your code, because it's too complicated to do otherwise?
   With `anaconda-project`, you can `os.getenv("DB_PASSWORD")` and
   configure `anaconda-project` to prompt the user for any missing
   credentials.
 * Do you want improved reproducibility? With `anaconda-project`,
   someone who wants to reproduce your analysis can ensure they
   have exactly the same setup that you have on your machine.
 * Do you want to deploy your analysis as a web application? The
   configuration in `anaconda-project.yml` tells hosting providers how to
   run your project, so there's no special setup needed when
   you move from your local machine to the web.

## Learn more

See http://conda.pydata.org/docs/kapsel/ for a simple
getting-started walkthrough.

See http://conda.pydata.org/docs/kapsel/config.html for more detail on
the syntax of the `anaconda-project.yml` file.

## If you've been using `conda env` and `environment.yml`

`anaconda-project` has similar functionality and may be more
convenient. The advantage of `anaconda-project` for environment
handling is that it performs conda operations, _and_ records them
in a config file for reproducibility, in one step.

For example, if you do `anaconda-project add-packages bokeh=0.11`,
that will install Bokeh with conda, _and_ add `bokeh=0.11` to an
environment spec in `anaconda-project.yml` (the effect is comparable to
adding it to `environment.yml`). In this way, "your current conda
environment's state" and "your configuration to be shared with
others" won't get out of sync.

`anaconda-project` will also automatically set up environments for a
colleague when they type `anaconda-project run` on their machine; they
don't have to do a separate step to create, update, or activate
environments before they run the code. This may be especially
useful when you change the required dependencies; with `conda env`
people can forget to re-run it and update their packages, while
`anaconda-project run` will automatically add missing packages every
time.

In addition to environment creation, `anaconda-project` can perform
other kinds of setup, such as adding data files and running a
database server. It's a superset of `conda env` in that sense.

# Stability note

For the time being, the Anaconda project API and command line syntax
are subject to change in future releases. A project created with
the current “beta” version of Anaconda project may always need to be
run with that version of Anaconda project and not conda
project 1.0. When we think things are solid, we’ll switch from
“beta” to “1.0” and you’ll be able to rely on long-term interface
stability.

# Bug Reports

Please report issues right here on GitHub.

# Contributing

Please join our chat room at https://gitter.im/conda/kapsel if you
have questions, feedback, or just want to say hi.

Here's how to work on the code:

 * `python setup.py test` is configured to run all the checks that
   have to pass before you commit or push. It also reformats the
   code with yapf if necessary. Continuous integration runs this
   command so you should run it and make it pass before you push
   to the repo.
 * To only run the formatter and linter, use `python setup.py test
   --format-only`.
 * To only run the tests, use `python -m pytest -vv anaconda_project`
 * To only run a single file of tests use `python -m pytest
   -vv anaconda_project/test/test_foo.py`
 * To only run a single test function `python -m pytest
   -vv anaconda_project/test/test_foo.py::test_something`
 * There's a script `build_and_upload.sh` that should be used to
   manually make a release. The checked-out revision should have
   a version tag prior to running the script.
