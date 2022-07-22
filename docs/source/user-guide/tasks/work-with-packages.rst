.. _Packages:

=====================
Working with packages
=====================

The ``anaconda-project.yml`` file enables specification
of required packages and multiple Conda environments, referred
to as ``env_specs``.

For example the following ``anaconda-project.yml`` file will
install ``python`` version 3.8, and latest version ``pandas``
and ``notebook`` into the default environment when you execute
``anaconda-project prepare`` on the command line.

.. code-block:: yaml

  name: ExampleProject

  packages:
    - python=3.8
    - notebook
    - pandas
  
  env_specs:
    default: {}

When ``anaconda-project prepare`` is run a new environment is created
called ``default`` in the ``envs`` subdirectory of your project.
See :ref:`Configuration` to change the default location of the Conda environments.

***************
Adding packages
***************

To add packages to your project that are not yet in your
``packages:`` list there are two approaches.

#. From within your project directory, run::

     anaconda-project add-packages package1 package2

   NOTE: Replace ``package1`` and ``package2`` with the names of
   the packages that you want to include. You can specify as many
   packages as you want.

   EXAMPLE: To add the packages hvplot=0.7 and dask::

     $ anaconda-project add-packages hvplot=0.7 dask
     Collecting package metadata (current_repodata.json): ...working... done
     Solving environment: ...working... done
     ...
     Executing transaction: ...working... done
     Using Conda environment /Users/adefusco/Desktop/iris/envs/default.
     Added packages to project file: hvplot=0.7, dask.

#. Instead of using the ``add-packages`` command you can edit the ``anaconda-project.yml``
   file directly using any text editor and add package names to the ``packages:`` list.
   To complete the installation of these new packages into your activate environment run
   ``anaconda-project prepare`` on the command line after saving the file.

In addition to adding Conda packages as shown above Pip packages
can be specified using the ``--pip`` flag::

  anaconda-project add-packages --pip package1 package2

NOTE: Replace ``package1`` and ``package2`` with the names of
the packages that you want to include. You can specify as many
packages as you want.

EXAMPLE: To add the ``requests`` package to the default environment::

  $ anaconda-project add-packages --pip requests
  Collecting requests
    Using cached requests-2.25.1-py2.py3-none-any.whl (61 kB)
  Requirement already satisfied: certifi>=2017.4.17 in ./envs/default/lib/python3.8/site-packages (from requests) (2020.12.5)
  Collecting idna<3,>=2.5
    Using cached idna-2.10-py2.py3-none-any.whl (58 kB)
  Collecting chardet<5,>=3.0.2
    Using cached chardet-4.0.0-py2.py3-none-any.whl (178 kB)
  Collecting urllib3<1.27,>=1.21.1
    Using cached urllib3-1.26.4-py2.py3-none-any.whl (153 kB)
  Installing collected packages: urllib3, idna, chardet, requests
  Successfully installed chardet-4.0.0 idna-2.10 requests-2.25.1 urllib3-1.26.4
  Using Conda environment /Users/adefusco/Desktop/testproj/envs/default.
  Added packages to project file: requests.

Optionally, you can edit the ``anaconda-project.yml`` file to add packages using
the ``pip:`` key within the ``packages:`` list. For example,

.. code-block:: yaml

  name: ExampleProject

  packages:
    - python=3.8
    - notebook
    - pandas
    - pip:
      - requests
  
  env_specs:
    default: {}

Then run ``anaconda-project prepare`` to install the new packages into the environment.

****************
Package Channels
****************

.. note::

  *Breaking Change in version 0.11.0*. All channels you wish to search through for packages must be supplied on the CLI
  or in the project YAML file.  To support reproducible projects that build the same way for different users, Anaconda Project will not respect channels declared in your ``.condarc`` file.

Up till now we have not instructed Conda to install packages from specific channels so all packages are installed from
the Conda default channels because a specific channel was not requested with ``anaconda-project add-packages`` and
because there is no ``channels:`` key in the ``anaconda-project.yml`` file.

.. code-block:: yaml

  name: ExampleProject

  packages:
    - python=3.8
    - notebook
    - pandas
    - pip:
      - requests
  
  env_specs:
    default: {}

To install packages from one or more channels use the ``-c <channel-name>`` flag, just like
``conda install``. To specify multiple channels add more ``-c <channel-name>`` flags. The order
in which the flags appear is the order that Conda will check for available packages. Optionally,
you can edit the ``anaconda-project.yml`` to supply a list of channels in the ``channels:`` key.

For example::

  anaconda-project add-packages -c defaults -c conda-forge fastapi

The resulting ``anaconda-project.yml`` file is now

.. code-block:: yaml

  name: ExampleProject

  packages:
    - python=3.8
    - notebook
    - pandas
    - pip:
      - requests

  channels:
    - defaults
    - conda-forge

  env_specs:
    default: {}


*****************
Removing packages
*****************

To remove packages from the ``packages:`` list run::

  anaconda-project remove-packages package1 package2

NOTE: Replace ``package1`` and ``package2`` with the names of
the packages that you want to include. You can specify as many
packages as you want.

EXAMPLE: To remove the package hvplot::

  $ anaconda-project remove-packages hvplot
  Using Conda environment /Users/adefusco/Desktop/testproj/envs/default.
  Removed packages from project file: hvplot.

EXAMPLE: To remove the ``requests`` pip package from the default environment::

  $ anaconda-project remove-packages --pip requests
  Found existing installation: requests 2.25.1
  Uninstalling requests-2.25.1:
    Successfully uninstalled requests-2.25.1
  Using Conda environment /Users/adefusco/Desktop/testproj/envs/default.
  Removed packages from project file: requests.


Pip package specifications
==========================

Pip packages can specified in a number of ways.

* From PyPI (or other indexes)
* Direct URL to the package archive
* Revision Control services (for example git and svn)

To install a package from a revision control service::

  anaconda-project add-packages --pip git+<protocol>://<revision-control-domain>/<repository.git>[version-branch]#egg=<package-name>

Where

* ``<protocol>`` is the web protocol of the domain: i.e, ``http`` or ``https``
* ``<revision-control-domain>`` is the URL of the service: i.e. ``github.com``
* ``<repository.git>`` is the name of the revision control repository, you can include the branch name or release tag here.
* ``[version-branch]`` optionally install a specific version or branch of the repository
* ``<package>`` is the name of the package as declared in ``setup.py``

NOTE: It is required that you use ``#egg=<package>`` to install a revision control hosted
package. This is considered `best practice by pip <https://pip.pypa.io/en/latest/cli/pip_install/#vcs-support>`_ and allows the pip dependency solver to 
correctly identify the package if it is a dependency of another package in your project.

EXAMPLE: Add the tranquilizer package to your project directly from Github::

  $ anaconda-project add-packages --pip git+https://github.com/continuumio/tranquilizer.git@0.5.0#egg=tranquilizer
  Collecting tranquilizer
  Cloning https://github.com/continuumio/tranquilizer.git (to revision 0.5.0) to /private/var/folders/lk/s__7f9fx15x_zrw6q5xkmm500000gp/T/pip-install-5ncd7pbt/tranquilizer_d037aa7b85d048c1acd4e2f0044c4cea
  Using Conda environment /Users/adefusco/Desktop/testproj/envs/default.
  Added packages to project file: git+https://github.com/continuumio/tranquilizer.git@0.5.0#egg=tranquilizer.

Alternatively for github you can use the URL of the repository archive. For example, to install
from the master branch of tranquilizer::

  $ anaconda-project add-packages --pip https://github.com/continuumio/tranquilizer/archive/master.zip#egg=tranquilizer
  Collecting tranquilizer
  Downloading https://github.com/continuumio/tranquilizer/archive/master.zip
  Using Conda environment /Users/adefusco/Desktop/testproj/envs/default.
  Added packages to project file: https://github.com/continuumio/tranquilizer/archive/master.zip#egg=tranquilizer.
