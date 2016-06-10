=================
Projects Tutorial
=================

With ``anaconda-project``, anyone who wants to look at your
notebooks or Bokeh plots or other analysis code can type
``anaconda-project run`` and have it Just
Work(tm). ``anaconda-project`` automates setup steps such as
installing the right packages, downloading files, and configuring
passwords.

The neat thing is that it _also_ makes it easier for you to set up
the project yourself in the first place! *Automation for others
(or your future self) happens as a side effect as you work on your
project.*

Even if you never share your project with others, you
may find that it's more convenient to use ``anaconda-project``
than it is to use ``conda`` directly.

In this tutorial, we'll create a project directory containing a
Bokeh application, then package it up as a zip file and pretend
we've sent it to an imaginary colleague, who will be able to
unpack it and run it with a single command.

========================
Install anaconda-project
========================

If you haven't, install conda (TODO: link to conda install
instructions), activate any conda environment, then ``conda
install anaconda_project``.

Be sure you can now run ``anaconda-project --version`` at your
command prompt and see the version information for
``anaconda-project``. It should print a version number like
``0.1``.

=======================
Create an empty project
=======================

We'll create a project directory called ``iris``. At the command
prompt, switch to the directory you'd like to contain the ``iris``
project. Now type:

    anaconda-project init --project iris

It will ask you whether to create the ``iris`` directory. Type "y"
to confirm. Your command line session could look something like
this:

    $ cd /home/alice/mystuff
    $ anaconda-project init --project iris
    Create directory '/home/alice/mystuff/iris'? y
    Project configuration is in /home/alice/mystuff/iris/project.yml

At this point, if you like you can browse ``iris/project.yml`` to
get oriented. We won't edit ``project.yml`` by hand in this
tutorial, but the commands we use in this tutorial will modify it.

==========================
Get some data to work with
==========================

Often data sets are too large to keep locally, so you might want
to download them on demand.

This data set about iris flowers isn't very large, but we'll set
it up to download on demand anyway to show how it works.

Change into your ``iris`` project directory, then type:

    anaconda-project add-download IRIS_CSV https://raw.githubusercontent.com/bokeh/bokeh/f9aa6a8caae8c7c12efd32be95ec7b0216f62203/bokeh/sampledata/iris.csv

You should see ``anaconda-project`` download the data file and now
there will be an ``iris.csv`` in your directory. If you look at
``project.yml``, you'll see a new entry in the ``downloads:``
section.

Here's what the command line session might look like:

    $ cd /home/alice/mystuff/iris
    $ anaconda-project add-download IRIS_CSV  https://raw.githubusercontent.com/bokeh/bokeh/f9aa6a8caae8c7c12efd32be95ec7b0216f62203/bokeh/sampledata/iris.csv
    File downloaded to /home/hp/checkout/iris/iris.csv
    Added https://raw.githubusercontent.com/bokeh/bokeh/f9aa6a8caae8c7c12efd32be95ec7b0216f62203/bokeh/sampledata/iris.csv to the project file.

Don't worry about the name ``IRIS_CSV`` yet. It's the name of an
environment variable; we'll get to that in a moment.

=======================
Create a command to run
=======================

Our project should contain some sort of code, right? Let's make a
"hello world". Create a file ``hello.py`` with these contents:

    print("hello")

NOTE: If you're using python 2, you may have to add ``from __future__
import print_function`` to the top, or omit the parentheses after
``print``.

You can run ``hello.py`` with ``python hello.py``. But that won't
do any ``anaconda-project`` magic. To be sure things get set up,
add ``hello.py`` as a project command, like this:

    anaconda-project add-command hello "python hello.py"

It will ask you what kind of command it is; choose ``C`` for
command line. The command line session looks like:

    $ anaconda-project add-command hello "python hello.py"
    Is `hello` a (B)okeh app, (N)otebook, or (C)ommand line? C
    Added a command 'hello' to the project. Run it with `anaconda-project run --command hello`.

Now try ``anaconda-project run --command hello``. It should print
"hello".

NOTE: Since you have only one command, plain ``anaconda-project
run`` would work too.

When you run the command the first time, you'll notice it takes a
while. That's because it created a dedicated environment for your
project. In your ``iris`` directory, you should now have an
``envs`` subdirectory. This keeps projects from stepping on each
other; every project has its own packages in its own sandbox, by
default.

When you run the command the second time, it should be much
faster.

Have a look in ``project.yml`` and you should see the ``hello``
command in the ``commands:`` section.

You can also list the commands in your project by typing
``anaconda-project list-commands``, here's an example:

    $ anaconda-project list-commands
    Commands for project: /home/alice/mystuff/iris

    Name      Description
    ====      ===========
    hello     python hello.py

========================
Adding required packages
========================

In the next steps, we'll need to use some packages that aren't in
our ``iris/envs/default`` environment yet.

While in your ``iris`` directory, type:

    anaconda-project add-dependencies bokeh pandas

The command line session should look something like:

    $ anaconda-project add-dependencies bokeh=0.11 pandas
    conda install: Using Anaconda Cloud api site https://api.anaconda.org
    Using Conda environment /home/alice/mystuff/iris/envs/default.
    Added dependencies to project file: bokeh=0.11, pandas.

If you look at ``project.yml`` you'll see bokeh and pandas listed
under the ``dependencies:`` section. Also, files such as
``envs/default/bin/bokeh`` will now exist, since the packages have
been installed in your project's environment.

============================================
Environment variables configure your project
============================================

You may have wondered about the string ``IRIS_CSV`. That's the
environment variable that will tell your program where
``iris.csv`` lives. There are also some other environment
variables that ``anaconda-project`` sets automatically, such as
``PROJECT_DIR`` which locates your project directory.

You can grab these variables from within your scripts with
Python's ``os.getenv`` function.

Let's make a script that prints out our data. Call it
``showdata.py`` and put the following code in there:

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

Tell ``anaconda-project`` how to run it by adding a command:

    anaconda-project add-command showdata 'python showdata.py'

Now run that command:

    anaconda-project run --command showdata

You should see the data printed out, and then the sentence about
"My project directory is...".

================
Custom variables
================

Say your command needs a database password, or has a tunable
parameter. You can require (or just allow) users to configure
these before the command runs.

Type ``anaconda-project add-variable COLUMN_TO_SHOW``. In
``project.yml`` you should now have a ``COLUMN_TO_SHOW`` in the
``variables:`` section, and ``anaconda-project list-variables``
should list ``COLUMN_TO_SHOW``.

Now modify ``showdata.py`` to use this variable:

    import os
    import pandas as pd

    project_dir = os.getenv("PROJECT_DIR")
    env = os.getenv("CONDA_DEFAULT_ENV")
    iris_csv = os.getenv("IRIS_CSV")
    column_to_show = os.getenv("COLUMN_TO_SHOW")

    flowers = pd.read_csv(iris_csv)

    print(flowers[column_to_show])
    print("My project directory is {} and my conda environment is {}".format(project_dir, env))

On Linux and Mac, users can set the environment variable like this:

    COLUMN_TO_SHOW=petal_length anaconda-project run --command showdata

They can also configure a value to be used on their local machine,
by typing:

    anaconda-project set-variable COLUMN_TO_SHOW=sepal_length

``set-variable`` sets a value in ``project-local.yml``, which is a
file local to this user and machine. When an environment variable
isn't set, the value (if any) from ``project-local.yml`` will be
used.

NOTE: it's good practice to use variables for passwords and
secrets in particular! It isn't very secure to put your personal
passwords directly in your code.

====================
Creating a Bokeh app
====================

Let's plot that flower data!

Create the directory ``iris_plot`` and in it put a file
``main.py`` with these contents:

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

You should now have a file ``iris_plot/main.py``. The
``iris_plot`` directory is a simple Bokeh app. (TODO link to info
on Bokeh apps)

To tell ``anaconda-project`` about the Bokeh app, type:

    anaconda-project add-command plot iris_plot

When asked, type ``B`` for Bokeh app. The command line session
should look like:

    $ anaconda-project add-command plot iris_plot
    Is `plot` a (B)okeh app, (N)otebook, or (C)ommand line? B
    Added a command 'plot' to the project. Run it with `anaconda-project run --command plot`.

NOTE: we use the app directory path, not the script path
``iris_plot/main.py``, to refer to a Bokeh app. Bokeh looks for
the file ``main.py`` by convention.

To see your plot, try this command:

    anaconda-project run --command plot -- --show

The double hyphen ``--`` means to pass subsequent command line
arguments down to your command. ``--show`` gets passed to the
``bokeh`` command, and tells Bokeh to open a browser window.

You should get a browser window displaying the Iris plot.

===================
Clean and reproduce
===================

You've left a trail of breadcrumbs in ``project.yml`` describing
how to reproduce your project. Look around in your ``iris``
directory and you'll see you have ``envs/default`` and
``iris.csv``, which you didn't create manually. Let's get rid of
them.

Type:

    anaconda-project clean

``iris.csv`` and ``envs/default`` should now be gone.

Run one of your commands again, and they'll come back. Type:

    anaconda-project run --command showdata

You should have ``iris.csv`` and ``envs/default`` back as they
were before.

You could also redo the setup steps without running a
command. Clean again:

    anaconda-project clean

``iris.csv`` and ``envs/default`` should be gone again. Then re-prepare the project:

    anaconda-project prepare

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
``anaconda-project bundle`` command automatically omits the files
it can reproduce automatically.

Type:

   anaconda-project bundle iris.zip

You should now have a file ``iris.zip``. If you list the files in
the zip, you'll see that the automatically-generated ones aren't
in there:

    $ unzip -l iris.zip
    Archive:  iris.zip
      Length      Date    Time    Name
    ---------  ---------- -----   ----
           16  06-10-2016 10:04   hello.py
          281  06-10-2016 10:22   showdata.py
          222  06-10-2016 09:46   .projectignore
         4927  06-10-2016 10:31   project.yml
          557  06-10-2016 10:33   iris_plot/main.py
    ---------                     -------
         6003                     5 files

NOTE: there's a ``.projectignore`` file you can use to manually
exclude anything you don't want in your archives.

NOTE: ``anaconda-project`` also supports creating ``.tar.gz`` and
``.tar.bz2`` archives.

When your colleague unzips the archive, they could list the
commands in it:

    $ anaconda-project list-commands
    Commands for project: /home/bob/projects/iris

    Name      Description
    ====      ===========
    hello     python hello.py
    plot      Bokeh app iris_plot
    showdata  python showdata.py


And then your colleague can type ``anaconda-project run --command
showdata`` (for example), and it will download the data, install
needed dependencies, and run the command.

==========
Next steps
==========

There's more that ``anaconda-project`` can do.

 * It can automatically start processes that your commands depend
   on. Right now it only supports starting Redis, for demo
   purposes. Use the ``anaconda-project add-service redis``
   command to play with this. More kinds of service will be
   supported soon! Let us know which you'd like to have. (TODO link)
 * You can have multiple Conda environment specs in your project,
   if for example some of your commands use a different version of
   Python or otherwise have distinct dependencies.
   ``anaconda-project add-env-spec`` adds these additional
   environment specs.
 * Because projects are self-describing, hosting providers such as
   Anaconda can automatically deploy them to a server.
   ``anaconda-project upload`` starts this process.
