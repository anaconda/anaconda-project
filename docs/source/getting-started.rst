===============
Getting started
===============

This getting started guide walks you through using Anaconda
Project for the first time.

After completing this guide, you will be able to:

* Create a new reproducible project.
* Run the project with a single command.
* Package and share the project.

If you have not yet installed and started Project,
follow the :doc:`Installation instructions <install>`.


Create a new project
====================

The following steps will create a project called "demo_app":

#. Open a Command Prompt or terminal window.

#. Initialize the project in a new directory::

     $ anaconda-project init -y --directory demo_app

#. Navigate into your project directory::

     $ cd demo_app

#. Add the package dependencies::

     $ anaconda-project add-packages python=3.8 notebook hvplot=0.7.3 panel=0.12.6 xarray=0.20 pooch=1.4 netCDF4

Create an example notebook-based Panel app
==========================================

In this section, we will create a new notebook called
``Interactive.ipynb`` via **either** of the following methods:

* Download this `quickstart`_ example:
  
  * Right-click the link and "Save As", naming the file ``Interactive.ipynb`` and saving it into your new demo_app folder, or
  
  * Use the ``curl`` command below. *This can be used on a unix-like platform.*
  
  ::

    $ curl https://raw.githubusercontent.com/Anaconda-Platform/anaconda-project/master/examples/quickstart/Interactive.ipynb -o Interactive.ipynb

 .. note:: This example is taken from a larger, more full-featured
   `hvPlot interactive`_, one that will work as well, if you would prefer
   to download that.

* Alternatively, you can launch a Jupyter notebook session with::

    $ anaconda-project run jupyter notebook

 Click the New button and choose the Python3 option. Paste the following contents into a cell and click File|Save as..., naming the file ``Interactive``.

 .. code-block:: python

    import xarray as xr, hvplot.xarray, hvplot.pandas, panel as pn, panel.widgets as pnw

    ds     = xr.tutorial.load_dataset('air_temperature')
    diff   = ds.air.interactive.sel(time=pnw.DiscreteSlider) - ds.air.mean('time')
    kind   = pnw.Select(options=['contourf', 'contour', 'image'], value='image')
    plot   = diff.hvplot(cmap='RdBu_r', clim=(-20, 20), kind=kind)

    hvlogo = pn.panel("https://hvplot.holoviz.org/assets/hvplot-wm.png", width=100)
    pnlogo = pn.panel("https://panel.holoviz.org/_static/logo_stacked.png", width=100)
    text   = pn.panel("## Select a time and type of plot", width=400)

    pn.Column(
        pn.Row(hvlogo, pn.Spacer(width=20), pn.Column(text, plot.widgets()), pnlogo),
        plot.panel()).servable()

 You can exit the running Jupyter Notebook program using CTRL+C in your terminal or command line.

.. _hvPlot interactive: https://raw.githubusercontent.com/holoviz/hvplot/master/examples/user_guide/Interactive.ipynb
.. _quickstart: https://raw.githubusercontent.com/Anaconda-Platform/anaconda-project/master/examples/quickstart/Interactive.ipynb

Run your project
================

1. Register a new command to launch the notebook as a `Panel`_ app::

     $ anaconda-project add-command --type unix dashboard "panel serve Interactive.ipynb"

  .. note:: The ``unix`` command type may be used for linux & macOS. For Windows, replace ``--type unix`` with ``--type windows``

2. Run your new project::

     $ anaconda-project run dashboard --show

   Your application should now be running and available at http://localhost:5006/Interactive. Once you're finished 
   with it, you can close the running program using CTRL+C in your terminal or command line.

.. _Panel: https://panel.holoviz.org

Sharing your project
====================

To share this project with a colleague:

#. Archive the project::

     $ anaconda-project archive interactive.zip

#. Send the archive file to your colleague.

You can also share a project by uploading it to Anaconda Cloud.
For more information, see :doc:`user-guide/tasks/share-project`.

Anyone with Project---your colleague or someone who downloads
your project from Cloud---can run your project by unzipping the
project archive file and then running a single command, without
having to do any setup::

     $ anaconda-project unarchive interactive.zip
     $ cd demo_app
     $ anaconda-project run

.. note:: If your project contains more than one command, the person
   using your project will need to specify which command to run.
   For more information, see :doc:`user-guide/tasks/run-project`.

Project downloads the data, installs the necessary packages and
runs the command.


Next steps
==========

* Learn more about :doc:`what you can do in Project
  <user-guide/tasks/index>`, including how to :doc:`download data
  <user-guide/tasks/download-data>` with your project and how to
  :doc:`configure your project with environment variables
  <user-guide/tasks/work-with-variables>`.

* Learn more about :doc:`the anaconda-project.yml format
  <user-guide/reference>`.
