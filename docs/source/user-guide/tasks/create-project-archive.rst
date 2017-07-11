==========================
Creating a project archive
==========================

To share a project with others, you likely want to put it into an
archive file, such as a .zip file. Anaconda Project can create
.zip, .tar.gz and .tar.bz2 archives. The archive format matches
the file extension that you provide.


Excluding files from the archive
================================

Do not include the ``envs/default`` directory in the archive,
because conda environments are large and do not work if moved
between machines. If your project works with large downloaded
files, you might not want to include those either.

The ``anaconda-project archive`` command automatically omits the
files that Project can reproduce automatically, which includes
the ``envs/default`` directory and any downloaded data.

To manually exclude any other files that you do not want to be
in the archive, create a ``.projectignore`` file.


Creating the archive file
=========================

To create a project archive, run the following command from
within your project directory::

  anaconda-project archive filename.zip

NOTE: Replace ``filename`` with the name for your archive file.
If you want to create a .tar.gz or .tar.bz2 archive instead of a
zip archive, replace ``zip`` with the appropriate file extension.

EXAMPLE: To create a zip archive called "iris"::

  anaconda-project archive iris.zip

Project creates the archive file.

If you list the files in the archive, you will see that
automatically generated files are not listed.

EXAMPLE::

  $ unzip -l iris.zip
  Archive:  iris.zip
    Length      Date    Time    Name
  ---------  ---------- -----   ----
         16  06-10-2016 10:04   iris/hello.py
        281  06-10-2016 10:22   iris/showdata.py
        222  06-10-2016 09:46   iris/.projectignore
       4927  06-10-2016 10:31   iris/anaconda-project.yml
        557  06-10-2016 10:33   iris/iris_plot/main.py
  ---------                     -------
       6003                     5 files
