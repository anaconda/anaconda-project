=====================
Working with commands
=====================

.. contents::
   :local:
   :depth: 1

Run all of the commands on this page from within the project
directory.


Adding a command to a project
=============================

A project contains some sort of code, such as Python files,
which have a ``.py`` extension.

You could run your Python code with the command::

  python file.py

NOTE: Replace ``file`` with the name of your file.

However, to gain the benefits of Anaconda Project, use Project
to add code files to your project:

#. Put the code file, application file, or notebook file into
   your project directory.

#. Add a command to run your file::

     anaconda-project add-command name "command"

   NOTE: Replace ``name`` with a name of your choosing for the
   command. Replace ``command`` with the command string.

   EXAMPLE:: To add a command called "notebook" that runs the
   IPython notebook ``mynotebook.ipynb``::

     anaconda-project add-command notebook mynotebook.ipynb

   EXAMPLE: To add a command called "plot" that runs a Bokeh
   app located outside of your project directory::

     anaconda-project add-command plot app-path-filename

   NOTE: Replace ``app-path-filename`` with the path and
   filename of the Bokeh app. By default, Bokeh looks for the
   file ``main.py``, so if your app is called ``main.py``, you do
   not need to include the filename.

#. When prompted for the type of command, type:

   * ``B`` if the command string is a Bokeh app to run.
   * ``N`` if the command string is a Notebook to run.
   * ``C`` if the command string is a Command line instruction to run, such as
     using Python to run a Python .py file.

   EXAMPLE: To add a command called "hello" that runs
   ``python hello.py``::

     $ anaconda-project add-command hello "python hello.py"
     Is `hello` a (B)okeh app, (N)otebook, or (C)ommand line? C
     Added a command 'hello' to the project. Run it with
     `anaconda-project run hello`.

#. OPTIONAL: In a text editor, open ``anaconda-project.yml`` to
   see the new command listed in the commands section.


Using commands that need different environments
===============================================

You can have multiple conda environment specifications in a
project, which is useful if some of your commands use a
different version of Python or otherwise have distinct
dependencies. Add these environment specs with
``anaconda-project add-env-spec``.


Using commands to automatically start processes
===============================================

Project can automatically start processes that your commands
depend on. Currently it only supports starting Redis, for
demonstration purposes.

To see Project automatically start the Redis process::

  anaconda-project add-service redis

More types of services will be supported soon. If there are
particular services that you would find useful, :doc:`let us
know <../../help-support>`.


.. _view-commands-list:

Viewing a list of commands in a project
=======================================

To list all of the commands in a project::

  anaconda-project list-commands

EXAMPLE::

  $ anaconda-project list-commands
  Commands for project: /home/alice/mystuff/iris

  Name      Description
  ====      ===========
  hello     python hello.py
  plot      Bokeh app iris_plot
  showdata  python showdata.py


Running a project command
=========================

Running a project command is the same as :doc:`run-project`.
