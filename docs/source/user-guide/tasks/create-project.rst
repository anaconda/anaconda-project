==================
Creating a project
==================

#. Create a project directory::

     anaconda-project init --directory directory-name

   NOTE: Replace ``directory-name`` with the name of your project
   directory.

   EXAMPLE: To create a project directory called "iris"::

     $ cd /home/alice/mystuff
     $ anaconda-project init --directory iris
     Create directory '/home/alice/mystuff/iris'? y
     Project configuration is in /home/alice/mystuff/iris/anaconda-project.yml

   You can also turn any existing directory into a project by
   switching to the directory and then running
   ``anaconda-project init`` without options or arguments.

#. OPTIONAL: In a text editor, open ``anaconda-project.yml`` to
   see what the file looks like for an empty project. As you work
   with your project, the ``anaconda-project`` commands you use
   will modify this file.

By default the ``init`` command will add the ``anaconda`` metapackage
to the default environment. This metapackage will install over 200 of the
most commonly used data science and scientific computing packages.

The ``anaconda-project.yml`` file will include the following sections

.. code-block:: yaml

  name: iris

  packages:
    - anaconda
  channels: []

  env_specs:
    default:
      description: Default environment spec for running commands
      packages: []
      channels: []
      platforms: []

To create an ``anaconda-project.yml`` file with no default packages run::

  anaconda-project init --empty-environment --directory iris

*******************
Prepare environment
*******************

Once the project directory and ``anaconda-project.yml`` file have been created
``cd`` into the new directory and install the packages::

  anaconda-project prepare

This will create a new Conda environment in a subdirectory of your project
directory called ``envs/default``.

For more information about adding and removing packages and environments (``env_specs``)
see :ref:`Packages`.

See :ref:`Configuration` to change the default location of the Conda environments.
