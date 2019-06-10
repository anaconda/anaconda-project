
========
Concepts
========


.. contents::
   :local:
   :depth: 1


Project
========

A project is a folder that contains an ``anaconda-project.yml``
configuration file together with scripts, notebooks and other
files.

You can make any folder into a project by adding a configuration file named
``anaconda-project.yml`` to the folder. The configuration file can include the
following sections:

* commands
* variables
* services
* downloads
* packages or dependencies
* channels
* env_specs

Data scientists use projects to encapsulate data science projects
and make them easily portable. A project is usually compressed
into a .tar.bz2 file for sharing and storing.

Anaconda Project automates setup steps, so that data scientists
that you share projects with can run your project with a single
command---``anaconda-project run``.


Configuration files
====================

Projects are affected by 3 configuration files:

* ``anaconda-project.yml``---Contains information about a project
  to be shared across users and machines. If you use source
  control, put ``anaconda-project.yml`` into your system.

* ``anaconda-project-local.yml``---Contains your local
  configuration state, which you do not want to share with
  others. Put this file into .gitignore, .svnignore or the
  equivalent in your source control system.

* ``anaconda-project-lock.yml``---Optional. Contains information
  needed to lock your package dependencies at specific versions.
  Put this file into source control along with
  ``anaconda-project.yml``. For more information on
  ``anaconda-project-lock.yml``, see :doc:`reference`.

To modify these files, use Project commands, Anaconda Navigator,
or any text editor.


Environment variables
=====================

Anything in the "variables" section of an
``anaconda-project.yml`` file is considered to be an environment
variable needed by your project.

EXAMPLE: The variables section of an ``anaconda-project.yml``
file that specifies 2 variables::

  variables:
    - AMAZON_EC2_USERNAME
    - AMAZON_EC2_PASSWORD

When a user runs your project, Project asks them for values to
assign to these variables.

In your script, you can use ``os.getenv()`` to obtain these
variables. This is a much better option than hardcoding passwords
into your script, which can be a security risk.


Comparing Project to conda env and environment.yml
===================================================

Project has similar functionality to the ``conda env`` command
and the ``environment.yml`` file, but it may be more convenient.
The advantage of Project for environment handling is that it
performs conda operations and records them in a configuration
file for reproducibility, all in one step.

EXAMPLE: The following command uses conda to install Bokeh and
adds ``bokeh=0.11`` to an environment spec in
``anaconda-project.yml``::

  anaconda-project add-packages bokeh=0.11

The effect is comparable to adding the environment spec to
``environment.yml``. In this way, the state of your current conda
environment and your configuration to be shared with others will
not get out of sync.

Project also automatically sets up environments for other users
when they type ``anaconda-project run`` on their machines. They
do not have to separately create, update or activate environments
before they run the code. This may be especially useful when you
change the required dependencies. With ``conda env``, users may
forget to rerun it and update their packages, while
``anaconda-project run`` automatically adds missing packages
every time.

In addition to creating environments, Project can perform other
kinds of setup, such as adding data files and running a database
server. In that sense, it is a superset of ``conda env``.
