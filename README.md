# Anaconda Projects

With Anaconda Project you can automate project setup such as
installing packages, starting a database server, downloading data
files, and so on. Whenever you (or someone else, or a hosting
provider), wants to run your project's scripts or apps, they can
do so with one command that performs and verifies the needed
setup.

The goal is that if your project works on your machine, it will
also work on others' machines (or on your future machine after you
reboot a few times and forget how your project works).

This repository contains command line tools and a library for
manipulating projects. A project in this sense is a directory full
of Python scripts, notebooks, Bokeh applications, or other
runnable items.

Traditional build scripts automate "building" the project (going
from source code to something runnable), while Anaconda Project
automates "running" the project (taking build artifacts and doing
anything necessary to execute them).

See ``projects.rst`` in this directory for more detail.

# Contributing

 * `python setup.py test` is configured to run all the checks that
   have to pass before you commit or push. It also reformats the
   code with yapf if necessary. Continuous integration runs this
   command so you should run it and make it pass before you push
   to the repo.
 * To only run the formatter and linter, use `python setup.py test
   --format-only`.
 * To only run the tests, use `python -m pytest anaconda_project`
 * To only run a single file of tests use `python -m pytest
   anaconda_project/test/test_foo.py`
 * To only run a single test function `python -m pytest
   anaconda_project/test/test_foo.py::test_something`

# Architecture

The general architecture of Anaconda Project is that there are
_requirements_ and _providers_, where requirements are a thing we
need (such as an installed package, running service, etc.), and
providers are able to provide a requirement. Many requirements are
simply environment variable names or package names. Providers are
plugins that know how to take actions to meet requirements, for
example the `RedisProvider` knows how to start a
dedicated `redis-server` scoped to a particular project.

