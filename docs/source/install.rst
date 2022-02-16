============
Installation
============

:doc:`Anaconda Project <index>` is included in Anaconda\ |reg| versions 4.3.1 and later.

To check that you have ``anaconda-project``:

1. Open a terminal window.

   * (Windows) Open your start menu, type in "cmd", and click the Command Prompt application.
   * (macOS) Open Launchpad and click the Terminal application.
   * (Linux) Search for a Terminal in your Activities or Applications or (in most systems) enter Ctrl-Alt-T.

2. Enter ``conda list``. Your terminal window should looks something like the following:

  .. code-block:: shell

    (base) ~ conda list
    # packages in environment at /Users/jdoe/opt/anaconda3:
    #
    # Name                    Version                   Build  Channel
    _ipyw_jlab_nb_ext_conf    0.1.0            py39hecd8cb5_0
    anaconda                  2021.11                  py39_0
    anaconda-client           1.9.0            py39hecd8cb5_0
    anaconda-navigator        2.1.1                    py39_0
    anaconda-project          0.10.1             pyhd3eb1b0_0
    ...

3. If for some reason your package list doesn't contain ``anaconda-project``, see the section below for instructions on
   how to install it manually.

Installing Anaconda Project Manually
------------------------------------

If you don't have access to conda yet, `installing Miniconda
<https://conda.io/projects/conda/en/latest/user-guide/install/index.html>`_ is the simplest way
to obtain it.

You can install Anaconda Project manually using the ``install`` command in your terminal window.

.. code-block:: shell
  
  (base) ~ conda install anaconda-project
  Collecting package metadata (current_repodata.json): done
  Solving environment: done

  ## Package Plan ##

    environment location: /Users/jdoe/opt/anaconda3

    added / updated specs:
      - anaconda-project


  The following packages will be downloaded:

      package                    |            build
      ---------------------------|-----------------
      anaconda-project-0.10.2    |     pyhd3eb1b0_0         218 KB
      ------------------------------------------------------------
                                             Total:         218 KB

  The following NEW packages will be INSTALLED:

    anaconda-project   pkgs/main/noarch::anaconda-project-0.10.2-pyhd3eb1b0_0
    conda-pack         pkgs/main/noarch::conda-pack-0.6.0-pyhd3eb1b0_0


  Proceed ([y]/n)? 

Enter 'y' to proceed.

.. code-block:: shell

  Downloading and Extracting Packages
  anaconda-project-0.1 | 218 KB    | ##################################### | 100%
  Preparing transaction: done
  Verifying transaction: done
  Executing transaction: done

Test your installation by running ``anaconda-project`` with the ``version``
option::

  anaconda-project --version

A successful installation reports the version number.

.. |reg|	unicode:: U+000AE .. REGISTERED SIGN
