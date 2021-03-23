==========================
Creating a project archive
==========================

To share a project with others, you likely want to put it into an
archive file, such as a .zip file. Anaconda Project can create
.zip, .tar.gz and .tar.bz2 archives. The archive format matches
the file extension that you provide.


Excluding files from the archive
================================

Do not include the ``envs/`` directory in the archive,
because Conda environments are large and do not work if moved
between machines. If your project works with large downloaded
files, you might not want to include those either.

The ``anaconda-project archive`` command automatically omits the
files that Project can reproduce automatically, which includes
the ``envs/`` directory and any downloaded data. It also
excludes ``anaconda-project-local.yml``, which is intended to
hold local configuration state only.

To manually exclude any other files that you do not want to be
in the archive, create a ``.projectignore`` file or a
``.gitignore`` file.

.. note::

  If you anticipate that this project will be managed as a Git
  repository, use of ``.gitignore`` is preferred over
  ``.projectignore``. However, use of ``.gitignore`` outside
  of a Git repository is not supported.

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

Extracting the archive file
===========================

It is recommended that you unarchive Anaconda Project bundles using
the ``unarchive`` command::

  anaconda-project unarchive <bundle>

This will unarchive any compression format (``.zip``, ``.tar.gz``, and
``.tar.bz2``) on all supported platforms.


Experimental: Packaging environments
====================================

There are cases where it may be preferable to package the
Conda environments directly into the archive. For example,
when the target system cannot connect to the repository to
download and install Conda packages.

To bundle the environments into the archive use the ``--pack-envs``
flag. This will utilize `conda-pack <https://conda.github.io/conda-pack/index.html>`_
to create separate sub-archives for each ``env_spec`` in the project
and add them to the Anaconda Project bundle.

.. note::

  When using ``--pack-envs`` your Anaconda Project bundles may be
  very large.

When the project bundle is extracted using ``anaconda-project unarchive`` if
environment archives are found they will be extracted to the ``envs/`` directory.

To disable extracting env bundles use ``anaconda-project unarchive --no-unpack-envs``.

.. note::

  The environment bundles will only be extracted when the project bundle
  is unarchived from the same platform type (Mac, Linux, Windows) where it
  was archived. For example, if you run ``archive --pack-envs`` on Windows
  and ``unarchive`` on Linux the environment bundles are ignored.