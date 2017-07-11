===============================
Downloading data into a project
===============================

Often data sets are too large to keep locally, so you may want
to download them on demand.

[@electronwill] In the following procedure, we say to execute
the command from within the project directory, but the
command includes an environmental variable that specifies
the path, so it seems like it would not be necessary to
execute the command from within the project directory.
If you aren't sure, please @mention an SME.

To set up your project to download data:

#. From within your project directory, run::

     anaconda-project add-download env-var URL

   NOTE: Replace ``env-var`` with an environment variable that
   contains the path to your project directory. Replace ``URL``
   with the URL for the data to be downloaded.

   Anaconda Project downloads the data file to your project
   directory.

   EXAMPLE: The following command downloads the ``iris.csv`` data
   file from a GitHub repository into the "iris" project, whose
   path is stored in the environment variable IRIS_CSV::

     anaconda-project add-download IRIS_CSV https://raw.githubusercontent.com/bokeh/bokeh/f9aa6a8caae8c7c12efd32be95ec7b0216f62203/bokeh/sampledata/iris.csv
     File downloaded to /home/alice/mystuff/iris/iris.csv
     Added https://raw.githubusercontent.com/bokeh/bokeh/f9aa6a8caae8c7c12efd32be95ec7b0216f62203/bokeh/sampledata/iris.csv to the project file.

#. OPTIONAL: In a text editor, open ``anaconda-project.yml`` to
   see the new entry in the downloads section.
