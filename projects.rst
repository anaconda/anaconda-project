========
Projects
========

The Anaconda platform works with directories called *projects*,
which can contain whatever you like (scripts, notebooks, data
files, whatever you need for your project).

Any directory can work as a project, but you can tell Anaconda
more about your project with a configuration file called
``project.yml``.

``project.yml`` and ``project-local.yml``
=========================================

Project directories are affected by two configuration files,
``project.yml`` and ``project-local.yml``.

``.yml`` files are in YAML format. Read more about YAML syntax
here: http://www.yaml.org/start.html (Useful hint about YAML: it's
a JSON superset, so if in doubt, write JSON instead of trying to
use the YAML syntax. For example you can always put quotes on a
string.)

``project.yml`` contains information about a project that's
intended to be shared across users and machines; if you're using
source control, you'll probably want to put ``project.yml`` in
source control.

``project-local.yml``, on the other hand, would go in
``.gitignore`` (or ``.svnignore`` or equivalent), because it
contains your local configuration state rather than anything you'd
want to share with others. Typically, the tools maintain
``project-local.yml`` for you and there's rarely a reason to edit
it by hand, so we'll focus on ``project.yml`` in this document.

Commands and Requirements
=========================

In ``project.yml`` you can define *commands* and *requirements*
that the commands have in order to run them.

For example, say you have a script called ``analyze.py``, your
project directory contains this script and a ``project.yml``:

  myproject/
     analyze.py
     project.yml

In ``project.yml`` you can tell the Anaconda platform how to run
your project:

  commands:
    default:
      shell: "python ${PROJECT_DIR}/analyze.py"
      windows: "python %PROJECT_DIR%\analyze.py"

Note that there are separate command lines for Unix shell (Linux,
Mac) and for Windows. If you only care about one platform, you
don't have to provide both of these.

Now when you send your project to someone else, they can type
``anaconda-project launch`` and your script will run. Kinda boring
so far, but the cool part is that ``anaconda-project launch`` can
be sure all prerequisites are set up *before* it runs the script.

Let's say your script requires a certain conda package to be
installed. Add the ``redis-py`` package to ``project.yml`` as a
dependency:

  dependencies:
    - redis-py

Now when someone does ``anaconda-project launch`` the script will
automatically run in a conda environment that has ``redis-py``
installed.

(TODO the above is a lie for now because ``anaconda-project
launch`` just complains, while ``anaconda-project prepare`` runs
the UI to set up the environment. See also
https://github.com/Anaconda-Server/anaconda-project/issues/54)

Or let's say your script requires a huge data file that you don't
want to put in source control or don't want to email around. You
can add a requirement that it's downloaded locally:

  downloads:
    MYDATAFILE:
      url: http://example.com/bigdatafile
      sha1: da39a3ee5e6b4b0d3255bfef95601890afd80709

Now when someone does ``anaconda-project launch``, the file will
be downloaded if it hasn't been, and the environment variable
``MYDATAFILE`` will be set to the local filename of the data.
In your ``analyze.py`` you could write something like this:

   import os
   filename = os.getenv('MYDATAFILE')
   if filename is None:
     raise Exception("Please use anaconda-project launch to start this script")
   with open(filename, 'r') as input:
     data = input.read()
     # and so on

``anaconda-project`` supports lots of other requirements,
too. Instead of writing documentation about how to set up your
script before running it, put the requirements in ``project.yml``
and let ``anaconda-project`` check them.

Multiple Commands
=================

TODO describe
https://github.com/Anaconda-Server/anaconda-project/issues/80
and https://github.com/Anaconda-Server/anaconda-project/issues/81
when those are implemented

Environments and Channels
=========================

You can configure dependencies in a toplevel ``dependencies``
section, as shown earlier:

  dependencies:
    - redis-py

You can also add Conda channels which will be searched for
dependencies:

  channels:
    - https://conda.anaconda.org/asmeurer

``anaconda-project`` will create an environment in
``envs/default`` by default. But if you like, you can have
multiple named environments available in the ``envs``
directory. To do that, specify an ``environments:`` section:

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

This means we can create two environments, ``envs/default`` and
``envs/python27``.

To run a project in a certain environment, use:
https://github.com/Anaconda-Server/anaconda-project/issues/97

If there are toplevel ``channels`` or ``dependencies`` sections
(not underneath the ``environments`` section), those channels and
dependencies will be added to all environments.


Requiring environment variables to be set
=========================================

Anything in the ``variables:`` section will be considered an
environment variable that your project needs. When someone
launches your project, ``anaconda-project`` will ask them to set
these variables.

For example:

  variables:
    - AMAZON_EC2_USERNAME
    - AMAZON_EC2_PASSWORD

Now in your script, you can ``os.getenv()`` these variables.

This is a much better option than hardcoding passwords in your
script, because it means you don't have to put passwords in source
control. Malicious people are constantly scanning sites such as
GitHub for accidentally-checked-in credentials; don't be a victim.


Variables that contain credentials
==================================

Variables which end in ``_PASSWORD``, ``_ENCRYPTED``,
``_SECRET_KEY``, or ``_SECRET`` will be treated sensitively by
default. This means that if ``anaconda-project`` stores a value
for them in ``project-local.yml`` or elsewhere, it will encrypt
that value.

To force a variable to be encrypted or not, add the ``encrypted``
option to it, like this:

  variables:
    # let's be contrary here and encrypt the username but
    # not encrypt the password
    AMAZON_EC2_USERNAME: { encrypted: true }
    AMAZON_EC2_PASSWORD: { encrypted: false }

The value of the environment variable will NOT be encrypted when
passed to your script; the encryption is only when we save the value
to a config file.


Variables with default values
=============================

If you make the ``variables:`` section a dictionary instead of a
list, you can give your variables default values. Anything
in the environment or in ``project-local.yml`` will override
these defaults though. To omit a default for a variable, set
its value to either ``null`` or ``{}``.

For example:

  variables:
    FOO: "default_value_of_foo"
    BAR: null # no default for BAR
    BAZ: {} # no default for BAZ
    # default as part of options dict, needed if you also
    # want to set some options such as 'encrypted: true'
    BLAH: { default: "default_value_of_blah" }


Variables that imply a running service
======================================

Certain variable names represent the address of a running service;
``anaconda-project`` treats these as special.

For example, you can do this:

  variables:
    - REDIS_URL

Now when someone launches the project, ``anaconda-project`` can
offer to start a local instance of ``redis-server`` automatically.

The full list of supported services includes:

 * REDIS_URL
 * (TODO right now it's only ``REDIS_URL`` of course, haven't added
more!)
 * TODO DB_URL
 * TODO BLAZE_URL


Variables that are always set
=============================

``anaconda-project`` ensures that the following are always set:

 * ``PROJECT_DIR`` will be set to the toplevel directory of your
   project
 * ``CONDA_ENV_PATH`` will be set to the filesystem location of
   the current Conda environment
 * ``PATH`` will include the binary directory from the current
   Conda environment

You can rely on these variables existing, for example to grab a
file from your project directory, try this:

  import os
  project_dir = os.getenv("PROJECT_DIR")
  my_file = os.path.join(project_dir, "my/file.txt")


File Downloads
==============

The ``downloads:`` section lets you define environment variables
pointing to downloaded files. For example:

  downloads:
    MYDATAFILE:
      url: http://example.com/bigdatafile
      sha1: da39a3ee5e6b4b0d3255bfef95601890afd80709

Rather than `sha1`, you can use whatever integrity hash you have;
supported hashes are ``md5``, ``sha1``, ``sha224``, ``sha256``,
``sha384``, ``sha512``. If you don't specify a hash, the download
won't be checked for integrity. It's up to you whether to live on
the edge like this.

You can also specify a filename to download to, relative to your
project directory. For example:

  downloads:
    MYDATAFILE:
      url: http://example.com/bigdatafile
      filename: myfile.csv

This will download to ``myfile.csv``, so if your project is in
``/home/mystuff/foo`` and the download succeeds, ``MYDATAFILE``
would be set to ``/home/mystuff/foo/myfile.csv``.

If you don't specify a filename, ``anaconda-project`` picks a
reasonable default based on the URL.

To avoid the automated download, it's also possible for someone to
launch your project with an existing file path in the environment;
on Unix, that looks like:

  MYDATAFILE=/my/already/downloaded/file.csv anaconda-project launch


Describing the Project
======================

By default, Anaconda will name your project after the directory
it's inside. You can give it a different name though in
``project.yml``:

  name: myproject

You can also have an icon file, relative to the project directory:

  icon: images/myicon.png

This will be used by graphical tools in the Anaconda platform,
when showing a list of projects.


No need to edit ``project.yml`` directly
========================================

TODO this is not true yet; see
https://github.com/Anaconda-Server/anaconda-project/issues/20

To add a download to ``project.yml`` try this:

  anaconda-project download http://example.com/myfile

To add a dependency, try this:

  anaconda-project install redis-py

To ask for a running Redis instance, try this:

  anaconda-project service-start redis


Fallback to meta.yaml
=====================

If you package your project with Conda, you may have some
information already in ``conda.recipe/meta.yaml``;
``anaconda-project`` will use some of this information too, so you
don't have to duplicate it in ``project.yml``.

For more on ``meta.yaml`` see http://conda.pydata.org/docs/building/meta-yaml.html

``anaconda-project`` currently pays attention to these fields in
``meta.yaml``:

 * `package: name:`
 * `app: entry:`
 * `app: icon:`

