==================================
Working with environment variables
==================================

.. contents::
   :local:
   :depth: 1

Run all of the commands on this page from within the project
directory.

Anaconda Project sets some environment variables
automatically:

* PROJECT_DIR specifies the location of your project directory.

* CONDA_ENV_PATH is set to the file system location of the
  current conda environment.

* PATH includes the binary directory from the current conda
  environment.

These variables always exist and can always be used in your
Python code.


Using variables in scripts
===========================

Use Python's os.getenv() function to obtain variables from within
your scripts.

EXAMPLE: The following script, called ``showdata.py``, prints out
data::

  import os
  import pandas as pd

  project_dir = os.getenv("PROJECT_DIR")
  env = os.getenv("CONDA_DEFAULT_ENV")
  iris_csv = os.getenv("IRIS_CSV")

  flowers = pd.read_csv(iris_csv)

  print(flowers)
  print("My project directory is {} and my conda environment is {}".format(project_dir, env))

If you tried to run this example script with
``python showdata.py``, it would not work if pandas was not
installed and the environment variables were not set.


Adding a variable
=================

If a command needs a user-supplied parameter, you can
require---or just allow---users to provide values for these
before the command runs.

NOTE: Encrypted variables such as passwords are treated
differently from other custom variables. See :ref:`encrypted-vars`.

#. Add the unencrypted variable to your project::

     anaconda-project add-variable VARIABLE

   NOTE: Replace VARIABLE with the name of the variable that you
   want to add.

   EXAMPLE: To add a variable called COLUMN_TO_SHOW::

     anaconda-project add-variable COLUMN_TO_SHOW

#. OPTIONAL: In a text editor, open ``anaconda-project.yml`` to
   see the new variable listed in the variables section.

#. OPTIONAL: Use the command ``anaconda-project list-variables``
   to see the new variables listed.

#. Include the new variable in your script in the same way as you
   would for any other variable.

The first time a user runs your project, they are prompted to
provide a value for your custom variable. On subsequent runs,
the user will not be prompted.

All environment variables are available for `jinja2
<https://jinja.palletsprojects.com/>`_ templating as shown
in the :ref:`http-commands` section.


.. _encrypted-vars:

Adding an encrypted variable
============================

Use variables for passwords and other secret information so that
each user can input their own private information.

Encrypted variable values are kept in the system keychain, while
other variable values are kept in the
``anaconda-project-local.yml`` file. In all other respects,
working with encrypted variables is the same as for unencrypted
variables.

Any variable ending in ``_PASSWORD``, ``_SECRET``, or
``_SECRET_KEY`` is automatically encrypted.

To create an encrypted variable::

    anaconda-project add-variable VARIABLE_encrypt-flag

NOTE: Replace VARIABLE with the name of the variable that you
want to add. Replace ``_encrypt-flag`` with ``_PASSWORD``,
``_SECRET`` or ``_SECRET_KEY``.

EXAMPLE: To create an encrypted variable called ``DB_PASSWORD``::

    anaconda-project add-variable DB_PASSWORD


Adding a variable with a default value
======================================

You can set a default value for a variable, which is stored with
the variable in ``anaconda-project.yml``. If you set a default,
users are not prompted to provide a value, but they can override
the default value if they want to.

To add a variable with a default value::

   anaconda-project add-variable --default=default_value VARIABLE

NOTE: Replace ``default_value`` with the default value to be set
and ``VARIABLE`` with the name of the variable to create.

EXAMPLE: To add the variable ``COLUMN_TO_SHOW`` with the default
value ``petal_width``::

  anaconda-project add-variable --default=petal_width COLUMN_TO_SHOW

If you or a user sets the variable in
``anaconda-project-local.yml``, the default is ignored. However,
you can unset the local override so that the default is used::

   anaconda-project unset-variable VARIABLE

NOTE: Replace VARIABLE with the variable name.

EXAMPLE: To unset the ``COLUMN_TO_SHOW`` variable::

   anaconda-project unset-variable COLUMN_TO_SHOW


Changing a variable's value
===========================

The variable values entered by a user are stored in the user's
``anaconda-project-local.yml`` file. To change a variable's value
in the user's file::

  anaconda-project set-variable VARIABLE=value

NOTE: Replace ``VARIABLE`` with the variable name and ``value``
with the new value for that variable.

EXAMPLE: To set ``COLUMN_TO_SHOW`` to ``petal_length``::

  anaconda-project set-variable COLUMN_TO_SHOW=petal_length


Removing a variable's value
===========================

Use the ``unset-variable`` command to remove the value that has
been set for a variable. Only the value is removed. The project
still requires a value for the variable in order to run.

Removing a variable
===================

Use the ``remove-variable`` command to remove the variable
from ``anaconda-project.yml`` so that the project no longer
requires the variable value in order to run.
