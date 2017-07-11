=================
Running a project
=================

Run all of the commands on this page from within the project 
directory.

To run a project:

#. If necessary, extract the files from the project archive 
   file---.zip, .tar.gz or .tar.bz2.

#. If you do not know the exact name of the command you want to
   run, :ref:`list the commands <view-commands-list>` in the 
   project.

#. If there is only one command in the project, run::    

     anaconda-project run

#. If there are multiple commands in the project, include the 
   command name::

     anaconda-project run command-name

   NOTE: Replace ``command-name`` with the actual command name.

   EXAMPLE: To run a command called "showdata", which could 
   download data, install needed packages and run the command::

     anaconda-project run showdata

#. For a command that runs a Bokeh app, you can include options 
   for ``bokeh serve`` in the run command.

   EXAMPLE: The following command passes the ``--show`` option 
   to the ``bokeh serve`` command, to tell Bokeh to open a 
   browser window::

     anaconda-project run plot --show
   
When you run a project for the first time, there is a short delay 
as the new dedicated project is created, and then the command is 
executed. The command will run much faster on subsequent runs 
because the dedicated project is already created.

In your project directory, you now have an ``envs`` subdirectory. 
By default every project has its own packages in its own sandbox 
to ensure that projects do not interfere with one another.
