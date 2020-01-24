=========
Reference
=========

The ``anaconda-project`` command works with *project directories*, which can
contain scripts, notebooks, data files, and anything that is related to your
project.

Any directory can be made into a project by adding a configuration file
named ``anaconda-project.yml``.

``.yml`` files are in the YAML format and follow the YAML syntax.

TIP: Read more about YAML syntax at http://yaml.org/start.html

TIP: You may want to go through :doc:`the anaconda-project tutorial <tutorial>`
before digging into the details in this document.

``anaconda-project.yml``, ``anaconda-project-local.yml``, ``anaconda-project-lock.yml``
=======================================================================================

Anaconda projects are affected by three configuration files,
``anaconda-project.yml``, ``anaconda-project-local.yml``, and
``anaconda-project-lock.yml``.

The file ``anaconda-project.yml`` contains information about a project that
is intended to be shared across users and machines. If you use
source control, the file ``anaconda-project.yml`` should probably be put in
source control.

The file ``anaconda-project-local.yml``, on the other hand, goes in
``.gitignore`` (or ``.svnignore`` or equivalent), because it
contains your local configuration state that you do not
want to share with others.

The file ``anaconda-project-lock.yml`` is optional and contains
information needed to lock your package dependencies at specific
versions. This "lock file" should go in source control along with
``anaconda-project.yml``.

These files can be manipulated with ``anaconda-project`` commands,
or with Anaconda Navigator, or you can edit them with any text
editor.

Commands and Requirements
=========================

In the ``anaconda-project.yml`` file you can define *commands* and
*requirements* that the commands need in order to run.

For example, let's say you have a script named ``analyze.py``
in your project directory along with a file ``anaconda-project.yml``:

.. code-block:: yaml

  myproject/
     analyze.py
     anaconda-project.yml

The file ``anaconda-project.yml`` tells conda how to run your project:

.. code-block:: yaml

  commands:
    default:
      unix: "python analyze.py"
      windows: "python analyze.py"

There are separate command lines for Unix shells (Linux and
macOS) and for Windows. You may target only one platform, and
are not required to provide command lines for other platforms.

When you send your project to someone else, they can type
``anaconda-project run`` to run your script. The best part
is that ``anaconda-project run`` makes sure that all
prerequisites are set up *before* it runs the script.

Let's say your script requires a certain conda package to be
installed. Add the ``redis-py`` package to ``anaconda-project.yml`` as a
dependency using either the ``packages`` or ``dependencies`` key:

.. code-block:: yaml

  packages:
    - redis-py

Now when someone runs ``anaconda-project run`` the script is
automatically run in a conda environment that has ``redis-py``
installed.

Here's another example. Let's say your script requires a huge
data file that you don't want to put in source control and
you don't want to email. You can add a requirement that the file will be
downloaded locally:

.. code-block:: yaml

  downloads:
    MYDATAFILE:
      url: http://example.com/bigdatafile
      sha1: da39a3ee5e6b4b0d3255bfef95601890afd80709

Now when someone runs ``anaconda-project run``, the file is
downloaded if it hasn't been downloaded already, and the
environment variable ``MYDATAFILE`` is set to the local
filename of the data. In your ``analyze.py`` file you can write
something like this:

.. code-block:: python

   import os
   filename = os.getenv('MYDATAFILE')
   if filename is None:
     raise Exception("Please use 'anaconda-project run' to start this script")
   with open(filename, 'r') as input:
     data = input.read()
     # and so on

``anaconda-project`` supports many other requirements,
too. Instead of writing long documentation about how to set up
your script before others can run it, simply put the requirements in
a ``anaconda-project.yml`` file and let ``anaconda-project`` check and execute
the setup automatically.

Multiple Commands
=================

An ``anaconda-project.yml`` can list multiple commands. Each command has a
name, and ``anaconda-project run COMMAND_NAME`` runs the command named
``COMMAND_NAME``.

``anaconda-project list-commands`` lists commands, along with a
description of each command. To customize a command's description,
add a ``description:`` field in ``anaconda-project.yml``, like this:

.. code-block:: yaml

  commands:
    mycommand:
      unix: "python analyze.py"
      windows: "python analyze.py"
      description: "This command runs the analysis"

Special command types
=====================

Bokeh apps and notebooks have a shorthand syntax:

.. code-block:: yaml

  commands:
    foo:
      bokeh_app: foo
      description: "Runs the bokeh app in the foo subdirectory"
    bar:
      notebook: bar.ipynb
      description: "Opens the notebook bar.ipynb"

Notebook-specific options
=========================

Notebook commands can annotate that they contain a function
registered with Anaconda Fusion:

.. code-block:: yaml

  commands:
    bar:
      notebook: bar.ipynb
      description: "Notebook exporting an Anaconda Fusion function."
      registers_fusion_function: true

If your notebook contains ``@fusion.register`` when you
``anaconda-project init`` or ``anaconda-project add-command``,
``registers_fusion_function: true`` will be added automatically.


.. _http-commands:

HTTP Commands
=============

``anaconda-project`` can be used to pack up web applications and
run them on a server. Web applications include Bokeh
applications, notebooks, APIs, and anything else that communicates with HTTP.

To make an ``anaconda-project`` command into a deployable web
application, it has to support a list of command-line
options.

Any command with ``notebook:`` or ``bokeh_app:`` automatically
supports these options, because ``anaconda-project`` translates
them into the native options supplied by the Bokeh and Jupyter
command lines.

Shell commands (those with ``unix:`` or ``windows:``) must support the
semantics of these command-line options appropriately. They do *not*
have to support the exact command line syntax used by ``anaconda project
run`` as shell commands support `jinja2
<https://jinja.palletsprojects.com>`_ templating. For instance:

.. code-block:: yaml

  commands:
    myapp:
      unix: launch_flask_app.py --port {{port}} --host {{host}} --address {{address}} 
      description: "Launches a Flask web app"

Here, ``{{port}}``, ``{{host}}`` and ``{{address}}`` are jinja2
variables that are templated into the ``--port``, ``--host`` and
``--address`` arguments of a hypothetical ``launch_flask_app.py``
script. These arguments are just a few of the variables made available
from the ``--anaconda-project-`` flags you can use when executing
``anaconda-project run``:

 * ``--anaconda-project-host=HOST:PORT`` can be specified multiple
   times and indicates a permitted value for the HTTP Host header. The
   value may include a port as well. There will be one
   ``--anaconda-project-host`` option for each host that browsers can
   connect to. This option specifies the application's public
   hostname:port and does not affect the address or port the application
   listens on. The last host specified is made available as the ``host``
   jinja2 variable while the full list of hosts is available as the
   ``hosts`` variable.
 * ``--anaconda-project-port=PORT`` indicates the local port the
   application should listen on; unlike the port which may be
   included in the ``--anaconda-project-host`` option, this port
   will not always be the one that browsers connect to. In a
   typical deployment, applications listen on a local-only port
   while a reverse proxy such as nginx listens on a public port
   and forwards traffic to the local port. In this scenario, the public
   port is part of ``--anaconda-project-host`` and the local port is
   provided as ``--anaconda-project-port``. This setting is available
   for templating as the ``port`` jinja2 variable.}
 * ``--anaconda-project-address=IP`` indicates the IP address the
   application should listen on. Unlike the host which may be
   included in the ``--anaconda-project-host`` option, this address may
   not be the one that browsers connect to. This setting is available
   for templating as the ``address`` jinja2 variable.
 * ``--anaconda-project-url-prefix=PREFIX`` gives a path prefix that
   should be the first part of the paths to all
   routes in your application. For example,
   if you usually have a page ``/foo.html``, and the prefix is ``/bar``,
   you would now have a page ``/bar/foo.html``. This setting is
   available for templating as the ``url_prefix`` jinja2 variable.
 * ``--anaconda-project-no-browser`` means "don't open a web
   browser when the command is run." If your command never opens a web
   browser anyway, you should accept but ignore this option.  This
   setting is available for templating as the ``no_browser`` jinja2
   variable. When this switch is present, the value of ``no_browser`` is
   ``True``.
 * ``--anaconda-project-iframe-hosts=HOST:PORT`` gives a value to
   be included in the ``Content-Security-Policy`` header
   as a value for ``frame-ancestors`` when you serve an HTTP
   response. The effect of this is to allow the page to be embedded in
   an iframe by the supplied HOST:PORT. This setting is available for
   templating as the ``iframe-hosts`` jinja2 variable.
 * ``--anaconda-project-use-xheaders`` tells your application that it's
   behind a reverse proxy and can trust "X-" headers, such as
   ``X-Forwarded-For`` or ``X-Host``.  This setting is available for
   templating as the ``use_xheaders`` jinja2 variable.  When this switch
   is present, the value of ``use_xheaders`` is ``True``.

As an alternative to the templating approach, you may choose to write
``launch_flask_app.py`` in such a way that it supports the above command
line flags and switches directly. In this case, you need to specify
``supports_http_options: true``:


.. code-block:: yaml

  commands:
    myapp:
      unix: {{PROJECT_DIR}}/launch_flask_app.py
      supports_http_options: true
      description: "Launches a Flask web app"

This example illustrates that in addition to the jinja2 variables
described above, all environment variables are also available for
templating, including ``PROJECT_DIR`` and conda related environment
variables such as ``CONDA_PREFIX`` and ``CONDA_DEFAULT_ENV``.


Environments and Channels
=========================

You can configure packages in a top level ``packages`` or ``dependencies``
section of the ``anaconda-project.yml`` file, as we discussed earlier:

.. code-block:: yaml

  packages:
    - redis-py

You can also add specific conda channels to be searched for
packages:

.. code-block:: yaml

  channels:
    - conda-forge

``anaconda-project`` creates an environment in ``envs/default`` by
default. But if you prefer, you can have multiple named
environments available in the ``envs`` directory. To do that,
specify an ``env_specs:`` section of your ``anaconda-project.yml`` file:

.. code-block:: yaml

  env_specs:
    default:
      packages:
        - foo
        - bar
      channels:
        - conda-forge
    python27:
      description: "Uses Python 2 instead of 3"
      packages:
        - python < 3
      channels:
        - https://example.com/somechannel

An environment specification or "env spec" is a description
of an environment, describing the packages that the project
requires to run.  By default, env specs are instantiated as
actual Conda environments in the ``envs`` directory inside
your project.

In the above example we create two env specs, which will
be instantiated as two environments, ``envs/default`` and
``envs/python27``.

To run a project using a specific env spec, use the ``--env-spec`` option:

.. code-block:: bash

  anaconda-project run --env-spec myenvname

If you have top level ``channels`` or ``packages`` sections in
your ``anaconda-project.yml`` file (not in the ``env_specs:`` section),
those channels and packages are added to all env specs.

The default env spec can be specified for each command, like this:

.. code-block:: yaml

  commands:
    mycommand:
      unix: "python ${PROJECT_DIR}/analyze.py"
      windows: "python %PROJECT_DIR%\analyze.py"
      env_spec: my_env_spec_name

Env specs can also inherit from one another. List a single
env spec or a list of env specs to inherit from,
something like this:

.. code-block:: yaml

  env_specs:
    test_packages:
      description: "Packages used for testing"
      packages:
        - pytest
        - pytest-cov
    app_dependencies:
      description: "Packages used by my app"
      packages:
        - bokeh
    app_test_dependencies:
      description: "Packages used to test my app"
      inherit_from: [test_packages, app_dependencies]

  commands:
    default:
       unix: start_my_app.py
       env_spec: app_dependencies
    test:
       unix: python -m pytest myapp/tests
       env_spec: app_test_dependencies


pip packages
============

Underneath any `packages:` or `dependencies:` section, you can add a `pip:`
section with a list of pip requirement specifiers.

.. code-block:: yaml

    packages:
       - condapackage1
       - pip:
         - pippackage1
         - pippackage2

Locking package versions
========================

Any env spec can be "locked", which means it specifies exact
versions of all packages to be installed, kept in
``anaconda-project-lock.yml``.

Hand-creating ``anaconda-project-lock.yml`` isn't
recommended. Instead, create it with the ``anaconda-project lock``
command, and update the versions in the configuration file with
``anaconda-project update``.

Locked versions are distinct from the "logical" versions in
``anaconda-project.yml``. For example, your
``anaconda-project.yml`` might list that you require
``bokeh=0.12``. The ``anaconda-project lock`` command expands
that to an *exact* version of Bokeh such as
``bokeh=0.12.4=py27_0``. It will also list exact versions of all
Bokeh's dependencies transitively, so you'll have a longer
list of packages in ``anaconda-project-lock.yml``. For example:

.. code-block:: yaml

    locking_enabled: true

    env_specs:
      default:
        locked: true
        env_spec_hash: eb23ad7bd050fb6383fcb71958ff03db074b0525
        platforms:
        - linux-64
        - win-64
        packages:
          all:
          - backports=1.0=py27_0
          - backports_abc=0.5=py27_0
          - bokeh=0.12.4=py27_0
          - futures=3.0.5=py27_0
          - jinja2=2.9.5=py27_0
          - markupsafe=0.23=py27_2
          - mkl=2017.0.1=0
          - numpy=1.12.1=py27_0
          - pandas=0.19.2=np112py27_1
          - pip=9.0.1=py27_1
          - python-dateutil=2.6.0=py27_0
          - python=2.7.13=0
          - pytz=2016.10=py27_0
          - pyyaml=3.12=py27_0
          - requests=2.13.0=py27_0
          - singledispatch=3.4.0.3=py27_0
          - six=1.10.0=py27_0
          - ssl_match_hostname=3.4.0.2=py27_1
          - tornado=4.4.2=py27_0
          - wheel=0.29.0=py27_0
          unix:
          - openssl=1.0.2k=1
          - readline=6.2=2
          - setuptools=27.2.0=py27_0
          - sqlite=3.13.0=0
          - tk=8.5.18=0
          - yaml=0.1.6=0
          - zlib=1.2.8=3
          win:
          - setuptools=27.2.0=py27_1
          - vs2008_runtime=9.00.30729.5054=0

By locking your versions, you can make your project more portable.
When you share it with someone else or deploy it on a server or
try to use it yourself in a few months, you'll get the same
package versions you've already used for testing. If you don't
lock your versions, you may find that your project stops working
due to changes in its dependencies.

When you're ready to test the latest versions of your
dependencies, run ``anaconda-project update`` to update the
versions in ``anaconda-project-lock.yml`` to the latest available.

If you check ``anaconda-project-lock.yml`` into revision control
(such as git), then when you check out old versions of your project
you'll also get the dependencies those versions were tested with.
And you'll be able to see changes in your dependencies over time
in your revision control history.

Specifying supported platforms
==============================

Whenever you lock or update a project, dependencies are resolved
for all platforms that the project supports. This allows you to do your
work on Windows and deploy to Linux, for example.

``anaconda-project lock`` by default adds a ``platforms:
[linux-64,osx-64,win-64]`` line to ``anaconda-project.yml``. If
you don't need to support these three platforms, or want different
ones, change this line. Updates will be faster if you support
fewer platforms. Also, some projects only work on certain
platforms.

The ``platforms:`` line does nothing when a project is unlocked.

Platform names are the same ones used by ``conda``. Possible
values in ``platforms:`` include ``linux-64``, ``linux-32``,
``win-64``, ``win-32``, ``osx-64``, ``osx-32``, ``linux-armv6l``,
``linux-armv7l``, ``linux-ppc64le``, and so on.

In ``anaconda-project.yml`` a ``platforms:`` list at the root of
the file will be inherited by all env specs, and then each env
spec can add (but not subtract) additional platforms. It works the
same way as the ``channels:`` list in this
respect. ``inherit_from:`` will also cause platforms to be
inherited.

Enabling and disabling locked versions
======================================

If you delete ``anaconda-project-lock.yml``, the project will
become "unlocked."

If you have an ``anaconda-project-lock.yml``, the
``locking_enabled:`` field indicates whether env specs are locked
by default. Individual env spec sections in
``anaconda-project-lock.yml`` can then specify ``locked: true`` or
``locked: false`` to override the default on a per-env-spec basis.

``anaconda-project unlock`` turns off locking for all env specs and
``anaconda-project lock`` turns on locking for all env specs.


Updating locked versions after editing an env spec
==================================================

If you use commands such as ``anaconda-project add-packages`` or
``anaconda-project add-env-spec`` to edit your
``anaconda-project.yml``, then ``anaconda-project-lock.yml`` will
automatically be kept updated.

However, if you edit ``anaconda-project.yml`` by hand and change an
env spec, you'll need to run ``anaconda-project update`` to update
``anaconda-project-lock.yml`` to match.

If locking isn't enabled for the project or for the env spec,
there's no need to ``anaconda-project update`` after editing your
env spec.


Requiring environment variables to be set
=========================================

Anything in the ``variables:`` section of a ``anaconda-project.yml`` file
is considered an environment variable needed by your project.
When someone runs your project, ``anaconda-project`` asks
them to set these variables.

For example:

.. code-block:: yaml

  variables:
    - AMAZON_EC2_USERNAME
    - AMAZON_EC2_PASSWORD

Now in your script, you can use ``os.getenv()`` to get these variables.

NOTE: This is a much better option than hardcoding passwords into your
script, which can be a security risk.


Variables that contain credentials
==================================

Variables that end in ``_PASSWORD``, ``_ENCRYPTED``,
``_SECRET_KEY``, or ``_SECRET`` are treated sensitively by
default. This means that if ``anaconda-project`` stores a value
for them in ``anaconda-project.yml`` or ``anaconda-project-local.yml`` or elsewhere,
that value is encrypted. NOTE: ``anaconda-project-local.yml`` stores and
encrypts the value that you enter when prompted.

To force a variable to be encrypted or not encrypted, add the
``encrypted`` option to it in ``anaconda-project.yml``, like this:

.. code-block:: yaml

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
in the environment or in ``anaconda-project-local.yml`` overrides
these defaults. To omit a default for a variable, set
its value to either ``null`` or ``{}``.

For example:

.. code-block:: yaml

  variables:
    ALPHA: "default_value_of_alpha"
    BRAVO: null # no default for BRAVO
    CHARLIE: {} # no default for CHARLIE
    # default as part of options dict, needed if you also
    # want to set some options such as 'encrypted: true'
    DELTA: { default: "default_value_of_delta" }
    ECHO: { default: "default_value_of_echo", encrypted: true }


Variables can have custom description strings
=============================================

A variable can have a 'description' field, which will be used in UIs
which display the variable.

For example:

.. code-block:: yaml

  variables:
    SALES_DB_PASSWORD: {
       description: "The password for the sales database. Ask jim@example.com if you don't have one."
    }


Variables that are always set
=============================

``anaconda-project`` ensures that the following variables are always set:

 * ``PROJECT_DIR`` is set to the top level directory of your project
 * ``CONDA_ENV_PATH`` is set to the filesystem location of the current conda environment
 * ``PATH`` includes the binary directory from the current conda environment

These variables always exist and can always be used in your Python code.
For example, to get a file from your project directory, try this in your
Python code (notebook or script):

.. code-block:: python

  import os
  project_dir = os.getenv("PROJECT_DIR")
  my_file = os.path.join(project_dir, "my/file.txt")


Services
========

TIP: Services are a proof-of-concept demo feature for now.

Services can be automatically started, and their address
can be provided to your code by using an environment variable.

For example, you can add a services section to your ``anaconda-project.yml`` file:

.. code-block:: yaml

  services:
    REDIS_URL: redis

Now when someone else runs your project, ``anaconda-project``
offers to start a local instance of ``redis-server`` automatically.

There is also a long form of the above service configuration:

.. code-block:: yaml

  services:
    REDIS_URL: { type: redis }

and you can set a default and any options a service may have:

.. code-block:: yaml

  services:
    REDIS_URL:
       type: redis
       default: "redis://localhost:5895"

Right now there is only one supported service (Redis) as a
demo. We expect to support more soon.


File Downloads
==============

The ``downloads:`` section of the ``anaconda-project.yml`` file lets you define
environment variables that point to downloaded files. For example:

.. code-block:: yaml

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

.. code-block:: yaml

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
run your project with an existing file path in the environment.
On Linux or Mac, that looks like:

.. code-block:: bash

  MYDATAFILE=/my/already/downloaded/file.csv anaconda-project run

Conda can auto-unzip a zip file as it is downloaded.  This is the
default if the URL path ends in ".zip" unless the filename
also ends in ".zip". For URLs that do not end in ".zip", or to
change the default, you can specify the "unzip" flag:

.. code-block:: yaml

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

By default, ``anaconda-project`` names your project with the same
name as the directory in which it is located. You can give it a
different name in ``anaconda-project.yml``:

.. code-block:: yaml

  name: myproject

You can also have an icon file, relative to the project directory:

.. code-block:: yaml

  icon: images/myicon.png


No need to edit ``anaconda-project.yml`` directly
=================================================

You can edit ``anaconda-project.yml`` with the ``anaconda-project`` command.

To add a download to ``anaconda-project.yml``:

.. code-block:: bash

  anaconda-project add-download MYFILE http://example.com/myfile

To add a package:

.. code-block:: bash

  anaconda-project add-packages redis-py

To ask for a running Redis instance:

.. code-block:: bash

  anaconda-project add-service redis
