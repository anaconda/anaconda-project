# Anaconda Projects

This project contains command line tools and a library for
manipulating projects. A project in this sense is a directory full
of Python scripts, notebooks, Bokeh applications, or other
runnable items. Anaconda Project knows how to resolve
requirements - including runtime requirements such as services and
configuration - before running the project's code.

See ``projects.rst`` in this directory for more detail.

# Contributing

`python setup.py test` is configured to run all the checks that
have to pass before you commit or push. It also reformats the code
with yapf if necessary.

# Architecture

The general architecture of Anaconda Project is that there are
_requirements_ and _providers_, where requirements are a thing we
need (such as an installed package, running service, etc.), and
providers are able to provide a requirement. Many requirements are
simply environment variable names or package names. Providers are
plugins that know how to take actions to meet requirements, for
example the `RedisProvider` knows how to start a
dedicated `redis-server` scoped to a particular project.

