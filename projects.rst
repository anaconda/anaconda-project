========
Projects
========

The Anaconda platform works with directories named *projects*,
which can contain scripts, notebooks, data files, and anything
that is related to your project.

Any directory can function as a project, and you tell Anaconda
about your project with a configuration file named
``project.yml``.

``.yml`` files are in the YAML format and follow the YAML syntax.

TIP: Read more about YAML syntax at http://yaml.org/start.html

``project.yml`` and ``project-local.yml``
=========================================

Project directories are affected by two configuration files,
``project.yml`` and ``project-local.yml``.

The file ``project.yml`` contains information about a project that
is intended to be shared across users and machines. If you use
source control, the file ``project.yml`` should probably be put in
source control.

The file ``project-local.yml``, on the other hand, goes in
``.gitignore`` (or ``.svnignore`` or equivalent), because it
contains your local configuration state that you do not
want to share with others. Typically, the tools maintain the file
``project-local.yml`` for you and there are few reasons to edit
it by hand, so in this document we'll discuss editing the file
``project.yml``.

Commands and Requirements
=========================

In the ``project.yml`` file you can define the *commands* and
*requirements* that the commands need in order to run them.

For example, let's say you have a script named ``analyze.py``
in your project directory along with a file ``project.yml``:

  myproject/
     analyze.py
     project.yml

The file ``project.yml`` tells Anaconda platform how to run
your project:

  commands:
    default:
      unix: "python ${PROJECT_DIR}/analyze.py"
      windows: "python %PROJECT_DIR%\analyze.py"

There are separate command lines for Unix shell (Linux and
Mac) and for Windows. If you only care about one platform, you
are not required to provide command lines for other platforms.

When you send your project to someone else, they can type
``anaconda-project launch`` to run your script. The cool part
is that ``anaconda-project launch`` makes sure that all
prerequisites are set up *before* it runs the script.

Let's say your script requires a certain conda package to be
installed. Add the ``redis-py`` package to ``project.yml`` as a
dependency:

  dependencies:
    - redis-py

Now when someone runs ``anaconda-project launch`` the script is
automatically run in a conda environment that has ``redis-py``
installed.

(TODO the above is a lie for now because ``anaconda-project
launch`` just complains, while ``anaconda-project prepare`` runs
the UI to set up the environment. See also
https://github.com/Anaconda-Server/anaconda-project/issues/54)

Here's another example. Let's say your script requires a huge
data file that you don't want to put in source control and
you don't want to email. You can add a requirement to be
downloaded locally:

  downloads:
    MYDATAFILE:
      url: http://example.com/bigdatafile
      sha1: da39a3ee5e6b4b0d3255bfef95601890afd80709

Now when someone runs ``anaconda-project launch``, the file is
downloaded if it hasn't been downloaded already, and the
environment variable ``MYDATAFILE`` is set to the local
filename of the data. In your ``analyze.py`` file you can write
something like this:

   import os
   filename = os.getenv('MYDATAFILE')
   if filename is None:
     raise Exception("Please use anaconda-project launch to start this script")
   with open(filename, 'r') as input:
     data = input.read()
     # and so on

``anaconda-project`` supports many other requirements,
too. Instead of writing long documentation about how to set up
your script before others can run it, simply put the requirements in
a ``project.yml`` file and let ``anaconda-project`` check the setup
automatically.

Multiple Commands
=================

TODO describe
https://github.com/Anaconda-Server/anaconda-project/issues/80
and https://github.com/Anaconda-Server/anaconda-project/issues/81
when those are implemented

TODO mention that commands can have a 'description' field.

Environments and Channels
=========================

You can configure dependencies in a top level ``dependencies``
section of the ``project.yml`` file, as we discussed earlier:

  dependencies:
    - redis-py

You can also add specific conda channels to be searched for
dependencies:

  channels:
    - https://conda.anaconda.org/asmeurer

``anaconda-project`` creates an environment in ``envs/default``
by default. But if you prefer, you can have
multiple named environments available in the ``envs``
directory. To do that, specify an ``environments:`` section of
your ``project.yml`` file:

  environments:
    default:
      dependencies:
        - foo
        - bar
      channels:
        - https://conda.anaconda.org/asmeurer
    python27:
      dependencies:
        - python < 3
      channels:
        - https://example.com/somechannel

In the above example we create two environments, ``envs/default``
and ``envs/python27``.

To run a project in a specific environment, use the ``environment`` option:

  anaconda-project launch --environment myenvname

https://github.com/Anaconda-Server/anaconda-project/issues/97

If you have top level ``channels`` or ``dependencies`` sections
in your ``project.yml`` file (not in the ``environments:`` section),
those channels and dependencies are added to all environments.


Requiring environment variables to be set
=========================================

Anything in the ``variables:`` section of a ``project.yml`` file
is considered an environment variable needed by your project.
When someone launches your project, ``anaconda-project`` asks
them to set these variables.

For example:

  variables:
    - AMAZON_EC2_USERNAME
    - AMAZON_EC2_PASSWORD

Now in your script, you can ``os.getenv()`` these variables.

NOTE: This is a much better option than hardcoding passwords into your
script, which can be a security risk.


Variables that contain credentials
==================================

TODO this section is partly about project-local.yml despite the
intro that says we will only discuss project.yml in this document.

Variables that end in ``_PASSWORD``, ``_ENCRYPTED``,
``_SECRET_KEY``, or ``_SECRET`` are treated sensitively by
default. This means that if ``anaconda-project`` stores a value
for them in ``project.yml`` or ``project-local.yml`` or elsewhere,
that value is encrypted. NOTE: ``project-local.yml stores and
encrypts the value that you enter when prompted.

To force a variable to be encrypted or not encrypted, add the
``encrypted`` option to it in ``project.yml``, like this:

  variables:
    # let's encrypt the password but not the username
    AMAZON_EC2_USERNAME: { encrypted: false }
    AMAZON_EC2_PASSWORD: { encrypted: true }

NOTE: The value of the environment variable is NOT encrypted
when passed to your script; the encryption happens only when we
save the value to a config file.


Variables with default values
=============================

If you make the ``variables:`` section a dictionary instead of a
list, you can give your variables default values. Anything
in the environment or in ``project-local.yml`` overrides
these defaults. To omit a default for a variable, set
its value to either ``null`` or ``{}``.

For example:

  variables:
    FOO: "default_value_of_foo"
    BAR: null # no default for BAR
    BAZ: {} # no default for BAZ
    # default as part of options dict, needed if you also
    # want to set some options such as 'encrypted: true'
    BLAH: { default: "default_value_of_blah" }


Variables can have custom description strings
======================================

A variable can have a 'description' field, which will be used in UIs
which display the variable.

For example:

  variables:
    SALES_DB_PASSWORD: {
       description: "The password for the sales database, ask jim@example.com if you don't have one."
    }


Variables that are always set
=============================

``anaconda-project`` ensures that the following variables
are always set:

 * ``PROJECT_DIR`` is set to the top level directory of your
   project
 * ``CONDA_ENV_PATH`` is set to the filesystem location of
   the current conda environment
 * ``PATH`` includes the binary directory from the current
   conda environment

These variables always exist, so for example to get a
file from your project directory, try this in your Python code
(notebook or script):

  import os
  project_dir = os.getenv("PROJECT_DIR")
  my_file = os.path.join(project_dir, "my/file.txt")


Services
========

Services can be automatically started, and their address
can be provided to your code by using an environment variable.

For example, you can add a services section to your ``project.yml`` file:

  services:
    REDIS_URL: redis

Now when someone else launches your project, ``anaconda-project``
offers to start a local instance of ``redis-server`` automatically.

There is also a long form of the above service configuration:

  services:
    REDIS_URL: { type: redis }

and you can set a default and any options a service may have:

  services:
    REDIS_URL:
       type: redis
       default: "redis://localhost:5895"

The full list of supported services includes:

 * REDIS_URL
 * (TODO right now it's only ``REDIS_URL`` of course, haven't added
more!)
 * TODO DB_URL
 * TODO BLAZE_URL


File Downloads
==============

The ``downloads:`` section of the ``project.yml`` file lets you define
environment variables that point to downloaded files. For example:

  downloads:
    MYDATAFILE:
      url: http://example.com/bigdatafile
      sha1: da39a3ee5e6b4b0d3255bfef95601890afd80709

Rather than `sha1`, you can use whatever integrity hash you have;
supported hashes are ``md5``, ``sha1``, ``sha224``, ``sha256``,
``sha384``, ``sha512``.

NOTE: The download is checked for integrity ONLY if you specify a hash.

You can also specify a filename to download to, relative to your
project directory. For example:

  downloads:
    MYDATAFILE:
      url: http://example.com/bigdatafile
      filename: myfile.csv

This downloads to ``myfile.csv``, so if your project is in
``/home/mystuff/foo`` and the download succeeds, ``MYDATAFILE``
is set to ``/home/mystuff/foo/myfile.csv``.

If you do not specify a filename, ``anaconda-project`` picks a
reasonable default based on the URL.

To avoid the automated download, it's also possible for someone to
launch your project with an existing file path in the environment;
on Linux or Mac, that looks like:

  MYDATAFILE=/my/already/downloaded/file.csv anaconda-project launch

Anaconda Project can auto-unzip a zip file as it is downloaded.
This is the default if the the URL path ends in ".zip"
unless the filename also ends in ".zip". For URLs that do not
end in ".zip", or to change the default, you can specify the "unzip"
flag:

  downloads:
    MYDATAFILE:
      url: http://example.com/bigdatafile
      unzip: true

The ``filename`` is used as a directory and the zip file is unpacked
into the same directory, unless the zip contains a
single file or directory with the same name as ``filename``. In that
case, then the two are consolidated.

EXAMPLE: If your zip file contains a single directory
``foo`` with file ``bar`` inside that, and you specify downloading
to filename ``foo``, then you'll get ``PROJECT_DIR/foo/bar``, not
``PROJECT_DIR/foo/foo/bar``.


Describing the Project
======================

By default, Anaconda names your project with the same name as
the directory in which it is located. You can give it a
different name though in ``project.yml``:

  name: myproject

You can also have an icon file, relative to the project directory:

  icon: images/myicon.png

This is used by graphical tools in the Anaconda platform,
when showing a list of projects.


No need to edit ``project.yml`` directly
========================================

You can edit ``project.yml`` with the ``anaconda-project`` command.

To add a download to ``project.yml``:

  anaconda-project add-download MYFILE http://example.com/myfile

To add a dependency:

  anaconda-project add-dependencies redis-py

To ask for a running Redis instance:

  anaconda-project add-service redis


Fallback to meta.yaml
=====================

If you package your project with conda, you may have some
information already in ``conda.recipe/meta.yaml``;
``anaconda-project`` uses some of this information too, so you
do not need to duplicate this information in ``project.yml``.

``anaconda-project`` currently reads these fields in ``meta.yaml``:

 * `package: name:`
 * `app: entry:`
 * `app: icon:`

For more about ``meta.yaml`` see http://conda.pydata.org/docs/building/meta-yaml.html
