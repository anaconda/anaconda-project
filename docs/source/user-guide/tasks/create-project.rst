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
