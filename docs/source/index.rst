================
Anaconda Project
================

:emphasis:`Reproducible and executable project directories`

Anaconda Project encapsulates data science projects and makes 
them easily portable. Project automates setup steps such as 
installing the right packages, downloading files, setting 
environment variables and running commands.

Project makes it easy to reproduce your work, share projects with 
others and run them on different platforms. It also simplifies 
deployment to servers. Anaconda projects run the same way on your 
machine, on another user's machine or when deployed to a server.

Traditional build scripts such as ``setup.py`` automate building 
the project---going from source code to something 
runnable---while Project automates running the project---taking 
build artifacts and doing any necessary setup before executing 
them.

You can use Project on Windows, macOS and Linux.

Project is supported and offered by Anaconda, Inc\ |reg| 
and contributors under a 3-clause BSD license.


Benefits of Project
====================

 * A ``README`` file that contains setup steps can become 
   outdated, or users might not read it and then you have to help 
   them diagnose problems. Project automates the setup steps so 
   that the ``README`` file need only say "Type 
   ``anaconda-project run``."

 * Project facilitates collaboration by ensuring that all users
   working on a project have the same dependencies in their conda 
   environments. Project automates environment creation and 
   verifies that environments have the right versions of packages.

 * You can run ``os.getenv("DB_PASSWORD")`` and configure Project 
   to prompt the user for any missing credentials. This allows 
   you to avoid including your personal passwords or secret keys 
   in your code.

 * Project improves reproducibility. Someone who wants to 
   reproduce your analysis can ensure that they have the same 
   setup that you have on your machine.

 * Project simplifies deployment of your analysis as a web 
   application. The configuration in ``anaconda-project.yml`` 
   tells hosting providers how to run your project, so no special 
   setup is needed when you move from your local machine to the 
   web.


How Project works
=================

By adding an ``anaconda-project.yml`` configuration file to your 
project directory, a single ``anaconda-project run`` command can 
set up all dependencies and then launch the project. Running an 
Anaconda project executes a command specified in the 
``anaconda-project.yml`` file, where you can also configure any 
arbitrary commands. 

Project automates project setup by establishing all prerequisite 
conditions for the project's commands to execute successfully. 
These conditions could include:

* Creating a conda environment that includes certain packages.
* Prompting the user for passwords or other configuration.
* Downloading data files.
* Starting extra processes such as a database server.


Stability
=========

Currently, the Project API and command-line syntax are subject to 
change in future releases. A project created with the current 
beta version of Project may always need to be run with that 
version of Project and not Project 1.0. When we think things are 
solid, we will switch from beta to version 1.0, and you will be 
able to rely on long-term interface stability.


.. toctree::
   :maxdepth: 1
   :hidden:

   install
   user-guide/index
   help-support

.. |reg|	unicode:: U+000AE .. REGISTERED SIGN
