=====================
Conda Kapsel Tutorial
=====================

With ``conda kapsel``, anyone who wants to look at your notebooks
or Bokeh plots or other analysis code can type ``conda kapsel
run`` and have it Just Work(tm).

``conda kapsel`` automates setup steps such as installing the
right packages, downloading files, and configuring passwords.

The neat thing is that it *also* makes it easier for you to set up
the project yourself in the first place! **Automation for others
(or your future self) happens as a side effect as you work on your
project.**

Even if you never share your project with others, you may find
that it's more convenient to use ``conda kapsel`` than it is to
manually maintain an environment with commands such as ``conda
install``.

In this tutorial, we'll create a kapsel containing a Bokeh
application, then package it up as a zip file and pretend we've
sent it to an imaginary colleague, who will be able to unpack it
and run it with a single command.

====================
Install conda kapsel
====================

If you haven't, install conda (TODO: link to conda install
instructions), activate any conda environment, then ``conda
install conda_kapsel``.

Be sure you can now run ``conda kapsel --version`` at your
command prompt and see the version information for
``conda kapsel``. It should print a version number.

=======================
Create an empty project
=======================

We'll create a project directory called ``iris``. At the command
prompt, switch to a directory you'd like to contain the ``iris``
project. Now type::

    conda kapsel init --project iris

It will ask you whether to create the ``iris`` directory. Type "y"
to confirm. Your command line session could look something like
this::

    $ cd /home/alice/mystuff
    $ conda kapsel init --project iris
    Create directory '/home/alice/mystuff/iris'? y
    Project configuration is in /home/alice/mystuff/iris/kapsel.yml

At this point, if you like you can look through
``iris/kapsel.yml`` to get oriented. We won't edit
``kapsel.yml`` by hand in this tutorial, but the commands we use
in this tutorial will modify it.

==========================
Get some data to work with
==========================

Often data sets are too large to keep locally, so you might want
to download them on demand.

This data set about iris flowers isn't very large, but we'll set
it up to download on demand anyway to show how it works.

Change into your ``iris`` project directory, then type::

    conda kapsel add-download IRIS_CSV https://raw.githubusercontent.com/bokeh/bokeh/f9aa6a8caae8c7c12efd32be95ec7b0216f62203/bokeh/sampledata/iris.csv

You should see ``conda kapsel`` download the data file and now
there will be an ``iris.csv`` in your directory. If you look at
``kapsel.yml``, you'll see a new entry in the ``downloads:``
section.

Here's what the command line session might look like::

    $ cd /home/alice/mystuff/iris
    $ conda kapsel add-download IRIS_CSV  https://raw.githubusercontent.com/bokeh/bokeh/f9aa6a8caae8c7c12efd32be95ec7b0216f62203/bokeh/sampledata/iris.csv
    File downloaded to /home/alice/mystuff/iris/iris.csv
    Added https://raw.githubusercontent.com/bokeh/bokeh/f9aa6a8caae8c7c12efd32be95ec7b0216f62203/bokeh/sampledata/iris.csv to the project file.

Don't worry about the name ``IRIS_CSV`` yet. It's the name of an
environment variable; we'll get to that in a moment.

=======================
Create a command to run
=======================

A project should contain some sort of code, right? Let's make a
"hello world". Create a file ``hello.py`` with these contents::

    print("hello")

NOTE: If you're using python 2, you may have to add ``from __future__
import print_function`` to the top, or omit the parentheses after
``print``.

You can run ``hello.py`` with ``python hello.py``. But that won't
do any ``conda kapsel`` magic. To be sure things get set up,
add ``hello.py`` as a project command, like this::

    conda kapsel add-command hello "python hello.py"

It will ask you what kind of command it is; choose ``C`` for
command line. The command line session looks like::

    $ conda kapsel add-command hello "python hello.py"
    Is `hello` a (B)okeh app, (N)otebook, or (C)ommand line? C
    Added a command 'hello' to the project. Run it with `conda kapsel run hello`.

Now try ``conda kapsel run hello``. After a short delay, it
should print "hello".

NOTE: Since you have only one command, plain ``conda kapsel
run`` would work too.

When you run the command the first time, you'll notice it takes a
while. That's because it created a dedicated environment for your
project. In your ``iris`` directory, you should now have an
``envs`` subdirectory. This keeps projects from stepping on each
other; every project has its own packages in its own sandbox, by
default.

When you run the command the second time, it should be much
faster.

Have a look in ``kapsel.yml`` and you should see the ``hello``
command in the ``commands:`` section.

You can also list the commands in your project by typing
``conda kapsel list-commands``, here's an example::

    $ conda kapsel list-commands
    Commands for project: /home/alice/mystuff/iris

    Name      Description
    ====      ===========
    hello     python hello.py

========================
Adding required packages
========================

In the next steps, we'll need to use some packages that aren't in
our ``iris/envs/default`` environment yet.

While in your ``iris`` directory, type::

    conda kapsel add-packages bokeh=0.11.1 pandas

The command line session should look something like::

    $ conda kapsel add-packages bokeh=0.11.1 pandas
    conda install: Using Anaconda Cloud api site https://api.anaconda.org
    Using Conda environment /home/alice/mystuff/iris/envs/default.
    Added packages to project file: bokeh=0.11.1, pandas.

If you look at ``kapsel.yml`` you'll see bokeh and pandas listed
under the ``packages:`` section. Also, files such as
``envs/default/bin/bokeh`` will now exist, since the packages have
been installed in your project's environment.

============================================
Environment variables configure your project
============================================

You may have wondered about the string ``IRIS_CSV``. That's the
environment variable that will tell your program where
``iris.csv`` lives. There are also some other environment
variables that ``conda kapsel`` sets automatically, such as
``PROJECT_DIR`` which locates your project directory.

You can grab these variables from within your scripts with
Python's ``os.getenv`` function.

Let's make a script that prints out our data. Call it
``showdata.py`` and put the following code in there::

    import os
    import pandas as pd

    project_dir = os.getenv("PROJECT_DIR")
    env = os.getenv("CONDA_DEFAULT_ENV")
    iris_csv = os.getenv("IRIS_CSV")

    flowers = pd.read_csv(iris_csv)

    print(flowers)
    print("My project directory is {} and my conda environment is {}".format(project_dir, env))

If you run ``python showdata.py`` now, this script probably won't
work; pandas may not be installed, and the environment variables
won't be set.

Tell ``conda kapsel`` how to run it by adding a command::

    conda kapsel add-command showdata 'python showdata.py'

(Choose 'C' for "command line" at the prompt.)

Now run that command::

    conda kapsel run showdata

You should see the data printed out, and then the sentence about
"My project directory is...".

================
Custom variables
================

Say your command needs a database password, or has a tunable
parameter. You can require (or just allow) users to configure
these before the command runs.

Encrypted variables such as passwords are treated differently from
plain variables; encrypted variable values are kept in the system
keychain, while plain variable values are kept in
``kapsel-local.yml``. Let's try out a plain unencrypted variable
first.

Type::

    conda kapsel add-variable COLUMN_TO_SHOW

In ``kapsel.yml`` you should now have a ``COLUMN_TO_SHOW`` in the
``variables:`` section, and ``conda kapsel list-variables``
should list ``COLUMN_TO_SHOW``.

Now modify ``showdata.py`` to use this variable::

    import os
    import pandas as pd

    project_dir = os.getenv("PROJECT_DIR")
    env = os.getenv("CONDA_DEFAULT_ENV")
    iris_csv = os.getenv("IRIS_CSV")
    column_to_show = os.getenv("COLUMN_TO_SHOW")

    flowers = pd.read_csv(iris_csv)

    print("Showing column {}".format(column_to_show))
    print(flowers[column_to_show])
    print("My project directory is {} and my conda environment is {}".format(project_dir, env))

Because there's no value for ``COLUMN_TO_SHOW``, it will be
mandatory for users to provide one. Try::

   conda kapsel run showdata

The first time you run this, you should see a prompt asking you to
type in a column name. If you enter a column at the prompt (try
"sepal_length"), it will be saved in ``kapsel-local.yml``. Next
time you run, you won't be prompted for a value.

To change the value in ``kapsel-local.yml``, use::

    conda kapsel set-variable COLUMN_TO_SHOW=petal_length

``kapsel-local.yml`` is local to this user and machine, while
``kapsel.yml`` will be shared across all users of a project.

You can also set a default value for a variable in
``kapsel.yml``; if you do this, users will not be prompted for a
value, but can still set the variable to override the default if
they want to. Try setting a default value like this::

   conda kapsel add-variable --default=sepal_width COLUMN_TO_SHOW

Now you should see the default in ``kapsel.yml``.

If you've set the variable in ``kapsel-local.yml``, the default
will be ignored; unset your local override with::

   conda kapsel unset-variable COLUMN_TO_SHOW

The default will then be used when you ``conda kapsel run
showdata``.

============================
An encrypted custom variable
============================

It's good practice to use variables for passwords and secrets in
particular. This way, every user of the project can input their
own password, and it will be kept in their system keychain.

Any variable ending in ``_PASSWORD``, ``_SECRET``, or
``_SECRET_KEY`` will be encrypted by default.

Type::

    conda kapsel add-variable DB_PASSWORD

In ``kapsel.yml`` you should now have a ``DB_PASSWORD`` in the
``variables:`` section, and ``conda kapsel list-variables``
should list ``DB_PASSWORD``.

From here, things work just like the ``COLUMN_TO_SHOW`` example
above, except that the value of ``DB_PASSWORD`` will be saved in
the system keychain rather than ``kapsel-local.yml``.

Try for example::

   conda kapsel run showdata

This should prompt you for a value the first time, and then save
it in the keychain and use it from there on the second run.  You
can also use ``conda kapsel set-variable
DB_PASSWORD=whatever``, ``conda kapsel unset-variable
DB_PASSWORD``, and so on.

Because there's no reason this Iris example needs a database
password, feel free to remove it.

Type::

  conda kapsel remove-variable DB_PASSWORD

NOTE: ``unset-variable`` removes the variable value but keeps the
requirement that ``DB_PASSWORD`` must be set.  ``remove-variable``
removes the variable itself (the project will no longer require a
``DB_PASSWORD`` in order to run).

====================
Creating a Bokeh app
====================

Let's plot that flower data!

Create the directory ``iris_plot`` inside your ``iris`` project
directory, and in it put a file ``main.py`` with these contents::

    import os
    import pandas as pd
    from bokeh.plotting import Figure
    from bokeh.io import curdoc

    iris_csv = os.getenv("IRIS_CSV")

    flowers = pd.read_csv(iris_csv)

    colormap = {'setosa': 'red', 'versicolor': 'green', 'virginica': 'blue'}
    colors = [colormap[x] for x in flowers['species']]

    p = Figure(title = "Iris Morphology")
    p.xaxis.axis_label = 'Petal Length'
    p.yaxis.axis_label = 'Petal Width'

    p.circle(flowers["petal_length"], flowers["petal_width"],
             color=colors, fill_alpha=0.2, size=10)

    curdoc().title = "Iris Example"
    curdoc().add_root(p)

You should now have a file ``iris_plot/main.py`` inside the
project. The ``iris_plot`` directory is a simple Bokeh app. (TODO
link to info on Bokeh apps)

To tell ``conda kapsel`` about the Bokeh app be sure you are in the
directory "iris" and type::

    conda kapsel add-command plot iris_plot

When asked, type ``B`` for Bokeh app. The command line session
should look like::

    $ conda kapsel add-command plot iris_plot
    Is `plot` a (B)okeh app, (N)otebook, or (C)ommand line? B
    Added a command 'plot' to the project. Run it with `conda kapsel run plot`.

NOTE: we use the app directory path, not the script path
``iris_plot/main.py``, to refer to a Bokeh app. Bokeh looks for
the file ``main.py`` by convention.

To see your plot, try this command::

    conda kapsel run plot --show

``--show`` gets passed to the ``bokeh serve`` command, and tells
Bokeh to open a browser window. Other options for ``bokeh serve``
can be appended to the ``conda kapsel run`` command line as
well, if you like.

You should get a browser window displaying the Iris plot.

===================
Clean and reproduce
===================

You've left a trail of breadcrumbs in ``kapsel.yml`` describing
how to reproduce your project. Look around in your ``iris``
directory and you'll see you have ``envs/default`` and
``iris.csv``, which you didn't create manually. Let's get rid of
them.

Type::

    conda kapsel clean

``iris.csv`` and ``envs/default`` should now be gone.

Run one of your commands again, and they'll come back. Type::

    conda kapsel run showdata

You should have ``iris.csv`` and ``envs/default`` back as they
were before.

You could also redo the setup steps without running a
command. Clean again::

    conda kapsel clean

``iris.csv`` and ``envs/default`` should be gone again. Then re-prepare the project::

    conda kapsel prepare

You should have ``iris.csv`` and ``envs/default`` back again, but
this time without running a command.

=========================
Zip it up for a colleague
=========================

To share this project with a colleague, you might want a zip file
containing it. Of course you won't want to include
``envs/default``, because conda environments don't work if moved
between machines, plus they are large. If ``iris.csv`` were a
larger file, you might not want to include that either. The
``conda kapsel archive`` command automatically omits the files
it can reproduce automatically.

Type::

   conda kapsel archive iris.zip

You should now have a file ``iris.zip``. If you list the files in
the zip, you'll see that the automatically-generated ones aren't
in there::

    $ unzip -l iris.zip
    Archive:  iris.zip
      Length      Date    Time    Name
    ---------  ---------- -----   ----
           16  06-10-2016 10:04   iris/hello.py
          281  06-10-2016 10:22   iris/showdata.py
          222  06-10-2016 09:46   iris/.projectignore
         4927  06-10-2016 10:31   iris/kapsel.yml
          557  06-10-2016 10:33   iris/iris_plot/main.py
    ---------                     -------
         6003                     5 files

NOTE: there's a ``.projectignore`` file you can use to manually
exclude anything you don't want in your archives.

NOTE: ``conda kapsel`` also supports creating ``.tar.gz`` and
``.tar.bz2`` archives. The archive format will match the filename
you provide.

When your colleague unzips the archive, they could list the
commands in it::

    $ conda kapsel list-commands
    Commands for project: /home/bob/projects/iris

    Name      Description
    ====      ===========
    hello     python hello.py
    plot      Bokeh app iris_plot
    showdata  python showdata.py


And then your colleague can type ``conda kapsel run
showdata`` (for example), and it will download the data, install
needed packages, and run the command.

==========
Next steps
==========

There's more that ``conda kapsel`` can do.

 * It can automatically start processes that your commands depend
   on. Right now it only supports starting Redis, for demo
   purposes. Use the ``conda kapsel add-service redis``
   command to play with this. More kinds of service will be
   supported soon! Let us know if there are particular ones you'd
   find useful.
 * You can have multiple Conda environment specs in your project,
   if for example some of your commands use a different version of
   Python or otherwise have distinct dependencies.
   ``conda kapsel add-env-spec`` adds these additional
   environment specs.
 * Because projects are self-describing, hosting providers such as
   Anaconda can automatically deploy them to a server.
   ``conda kapsel upload`` starts this process.  A deployment
   will use a particular command, particular env spec, and
   customized values for your environment variables.
