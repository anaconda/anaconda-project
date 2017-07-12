===============================
Downloading data into a project
===============================

Often data sets are too large to keep locally, so you may want
to download them on demand.

To set up your project to download data:

#. From within your project directory, run::

     anaconda-project add-download env_var URL

   NOTE: Replace ``env_var`` with a name for an environment variable that
   Anaconda Project will create to store the path to your downloaded data file.
   Replace ``URL`` with the URL for the data to be downloaded.

   Anaconda Project downloads the data file to your project
   directory.

   EXAMPLE: The following command downloads the ``iris.csv`` data
   file from a GitHub repository into the "iris" project, and
   stores its new path in the environment variable IRIS_CSV::

     $ anaconda-project add-download IRIS_CSV https://raw.githubusercontent.com/bokeh/bokeh/f9aa6a8caae8c7c12efd32be95ec7b0216f62203/bokeh/sampledata/iris.csv
     File downloaded to /home/alice/mystuff/iris/iris.csv
     Added https://raw.githubusercontent.com/bokeh/bokeh/f9aa6a8caae8c7c12efd32be95ec7b0216f62203/bokeh/sampledata/iris.csv to the project file.

#. OPTIONAL: In a text editor, open ``anaconda-project.yml`` to
   see the new entry in the downloads section.
