# Anaconda Project

Get rid of that long README! It gets outdated, and people don't
read it carefully anyway.

What if your README's instructions could be as short as "type
`anaconda-project run`"?

With Anaconda Project you can automate project setup such as
installing packages, creating Conda environments, starting a
database server, downloading data files, and so on. Whenever you
(or someone else... or a hosting provider...), wants to run your
project's scripts or apps, they can do so with one command that
performs and verifies the needed setup.

The goal is that if your project runs on your machine, it will
also run on others' machines (or on your future machine after you
reboot a few times and forget how your project works).

*Anaconda Project enables reproducible, executable data science
projects.*

All we mean by "project" is a directory full of related stuff that
you're working on; scripts, notebooks, data files, whatever it may
be. Organize it however you like.

This repository contains command line tools and a library for
manipulating projects.

By the way: there's nothing inherently data-science-specific about
Anaconda Project... but the use-cases we've focused on to start
involve Python and data science tools (especially Bokeh and
notebooks). In the future, we hope to make Anaconda Project
extensible via plugins.

## Put another way...

Traditional build scripts automate "building" the project (going
from source code to something runnable), while Anaconda Project
automates "running" the project (taking build artifacts and doing
any necessary setup prior to executing them).

## Learn more

See ``tutorial.rst`` in this directory for a simple
getting-started walkthrough. TODO tutorial doesn't exist yet...

See ``projects.rst`` in this directory for more detail on the
syntax of the `project.yml` file.

## If you've been using `conda env` and `environment.yml`

Those tools aren't going away since many people are using them,
but if you'd like to try it out, `anaconda-project` has similar
functionality and may be more convenient. The advantage of
`anaconda-project` for environment handling is that it performs
conda operations _and_ records them in a config file in one step.

For example, if you do `anaconda-project add-dependency
bokeh=0.11`, that will install Bokeh with conda, _and_ add
`bokeh=0.11` to an environment spec in `project.yml` (the effect
is comparable to adding it to `environment.yml`). In this way,
"your current conda environment's state" and "your configuration
to be shared with others" won't get out of sync.

`anaconda-project` will also automatically set up environments for
a colleague when they type `anaconda-project run` on their
machine; they don't have to do a separate step to create, update,
or activate environments before they run the code. This may be
especially useful when you change the required dependencies; with
`conda env` people can forget to re-run it and update their
packages, while `anaconda-project run` will automatically add
missing packages every time.

Of course, `anaconda-project` can also perform other kinds of
setup in addition to environment creation. It's a superset of
`conda env` in that sense.

# Contributing

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

# Architecture

The general architecture of Anaconda Project is that there are
_requirements_ and _providers_, where requirements are a thing we
need (such as an installed package, running service, etc.), and
providers are able to provide a requirement. Many requirements are
simply environment variable names or package names. Providers are
plugins that know how to take actions to meet requirements, for
example the `RedisProvider` knows how to start a
dedicated `redis-server` scoped to a particular project.

