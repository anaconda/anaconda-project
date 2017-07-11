=====================
Working with packages
=====================

To include packages in your project that are not yet in your
environment:

#. From within your project directory, run::

     anaconda-project add-packages package1 package2

   NOTE: Replace ``package1`` and ``package2`` with the names of
   the packages that you want to include. You can specify as many
   packages as you want.

   The packages are installed in your project's environment, so
   you now see package files in your project folder, such as::

     envs/PATH/package1

   NOTE: Replace PATH with the actual path to your package.

   EXAMPLE: To add the packages Bokeh and pandas::

     $ anaconda-project add-packages bokeh=0.12 pandas
     conda install: Using Anaconda Cloud api site https://api.anaconda.org
     Using Conda environment /home/alice/mystuff/iris/envs/default.
     Added packages to project file: bokeh=0.12, pandas.

#. OPTIONAL: In a text editor, open ``anaconda-project.yml`` to
   see the new packages listed in the packages section.
