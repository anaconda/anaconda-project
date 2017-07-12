===============
Getting started
===============

This getting started guide walks you through using Anaconda
Project for the first time.

After completing this guide, you will be able to:

* Create a project containing a Bokeh app.
* Run the project with a single command.
* Package and share the project.

If you have not yet installed and started Project,
follow the :doc:`Installation instructions <../install>`.

For more information on Bokeh, see `Welcome to Bokeh
<http://bokeh.pydata.org/en/latest/>`_.


Creating a project containing a Bokeh app
===========================================

To create a project called "clustering_app":

#. Open a Command Prompt or terminal window.

#. Create a directory called ``clustering_app``, switch to it
   and then initialize the project::

     $ mkdir clustering_app
     $ cd clustering_app
     $ anaconda-project init
     Project configuration is in /User/Anaconda/My Anaconda Projects/clustering_app/anaconda-project.yml

#. Inside the ``clustering_app`` project directory, create and
   save a file named ``main.py`` that contains the code from the
   `Bokeh clustering example
   <https://raw.githubusercontent.com/bokeh/bokeh/master/examples/app/clustering/main.py>`_.

#. Add the packages that the Bokeh clustering demo depends on::

     anaconda-project add-packages python=3.5 bokeh=0.12.4 numpy=1.12.0 scikit-learn=0.18.1

#. Tell Project about the Bokeh app::

     anaconda-project add-command plot .

   NOTE: By default, Bokeh looks for the file ``main.py``, so you
   do not need to include this in the command string after the
   "plot" command name.

#. When prompted, type ``B`` for Bokeh app::

     Is `plot` a (B)okeh app, (N)otebook, or (C)ommand line? B
     Added a command 'plot' to the project.
     Run it with `anaconda-project run plot`.

#. Run your new project::

     anaconda-project run

   NOTE: If your project included more than one command, you
   would need to specify which command to run. For more
   information, see :doc:`tasks/run-project`.

   A browser window opens, displaying the clustering app.


Sharing your project
====================

To share this project with a colleague:

#. Archive the project::

     anaconda-project archive clustering.zip

#. Send the archive file to your colleague.

You can also share a project by uploading it to Anaconda Cloud.
For more information, see :doc:`tasks/share-project`.


Running your project
====================

Anyone with Project---your colleague or someone who downloads
your project from Cloud---can run your project by unzipping the
project archive file and then running a single command, without
having to do any setup::

     anaconda-project run

NOTE: If your project contained more than one command, the person
using your project would need to specify which command to run.
For more information, see :doc:`tasks/run-project`.

Project downloads the data, installs the necessary packages and
runs the command.


Next steps
==========

* Learn more about :doc:`what you can do in Project
  <tasks/index>`, including how to :doc:`download data
  <tasks/download-data>` with your project and how to
  :doc:`configure your project with environment variables
  <tasks/work-with-variables>`.

* Learn more about :doc:`the anaconda-project.yml format
  <reference>`.
