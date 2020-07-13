# Anaconda Project

*Tool for encapsulating, running, and reproducing data science projects.*

## Build status

[![Build status](https://github.com/Anaconda-Platform/anaconda-project/workflows/Build%20and%20test/badge.svg)](https://github.com/Anaconda-Platform/anaconda-project/actions)
[![codecov](https://codecov.io/gh/Anaconda-Platform/anaconda-project/branch/master/graph/badge.svg)](https://codecov.io/gh/Anaconda-Platform/anaconda-project)

## Project information

[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)

## Description

Take any directory full of stuff that you're working on; web apps,
scripts, Jupyter notebooks, data files, whatever it may be.

By adding an `anaconda-project.yml` to this project directory,
a single `anaconda-project run`command will be able to set
up all dependencies and then launch the project.

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

## Learn more from the complete docs

Check out the complete documentation, including a tutorial
and reference guide, at:
http://anaconda-project.readthedocs.io/en/latest/index.html

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

Please see CONTRIBUTING.md in this directory.