
===============
Getting started
===============

This getting started guide walks you through using Anaconda Project for the first time. 

**After completing this guide, you will be able to:**

* Create a project containing a Bokeh app
* Package and share the project
* Run the project with a single command

This guide is for all platforms: Windows, macOS and Linux.

If you have not yet installed and started Anaconda Project, follow the :doc:`Install instructions <install>`.


Create a project containing a Bokeh app
=======================================

We'll create a project directory called ``clustering_app``. At the command prompt, switch to a directory ``clustering_app`` and initialize the project::

    $ mkdir clustering_app
    $ cd clustering_app
    $ anaconda-project init
    Project configuration is in /User/Anaconda/My Anaconda Projects/clustering_app/anaconda-project.yml

Inside your ``clustering_app`` project directory, create and save a new file named ``main.py`` with the `Bokeh clustering example <https://raw.githubusercontent.com/bokeh/bokeh/master/examples/app/clustering/main.py>`_. (You may also wish to learn more about `Bokeh <http://bokeh.pydata.org/en/latest/>`_.)

We need to add the packages that the Bokeh clustering demo depends on: Bokeh, pandas, scikit-learn and NumPy. Open the ``anaconda-project.yml`` file and edit the packages section with:

.. code-block:: yaml

    packages:
      - python=3.5
      - bokeh=0.12.4
      - numpy=1.12.0
      - scikit-learn=0.18.1

To tell ``anaconda-project`` about the Bokeh app, be sure you are in the directory "clustering_app" and type::

    anaconda-project add-command plot .

When prompted, type ``B`` for Bokeh app. The command line session looks like::

    Is `plot` a (B)okeh app, (N)otebook, or (C)ommand line? B
    Added a command 'plot' to the project. Run it with `anaconda-project run plot`.

Now, you can run your project with::

    anaconda-project run

A browser window opens, displaying the clustering app.

Share your project
==================

To share this project with a colleague, first we archive it by typing::

   anaconda-project archive clustering.zip

Send that file to the colleague.

If your colleague has Anaconda Project too, they can unzip the file and type ``anaconda-project run`` (for example), and Anaconda Project will download the data, install needed packages, and run the command.

You can also share projects by uploading them to Anaconda Cloud, using the following command::

    anaconda-project upload

NOTE: You need an Anaconda Cloud account to upload projects.

Run your project
================

Anyone that downloads your project can now have it running locally with only one command, without having to worry about the setup::

    anaconda-project run


Next steps
==========

There's much more that Anaconda Project can do.

 * Learn more with the :doc:`Anaconda Project tutorial <tutorial>`, including how to download data with your project and how to configure your project with environment variables.

 * Read details on :doc:`the anaconda-project.yml format <reference>`.
