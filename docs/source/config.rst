=============
Configuration
=============

Environment variables
---------------------

Anaconda Project has modifiable configuration settings, which
are currently controlled exclusively by environment variables.

``ANACONDA_PROJECT_DISABLE_OVERRIDE_CHANNELS``
  Starting in version 0.11.0 Anaconda Project ignores any CondaRC
  configuration settings for ``channels:`` by default. Packages will only be
  installed from channels listed in the ``anaconda-project.yml`` file.
  Set this environment variable to a true value (1, or ``'True'``) to disable
  the override and allow the user or global CondaRC configuration to control
  channels from which Anaconda Project can install packages.

``ANACONDA_PROJECT_ENVS_PATH``
  This variable provides a list of directories to search for environments
  to use in projects, and where to build them when needed. The format
  is identical to a standard ``PATH`` variable on the host
  operating system---a list of directories separated by ``:`` on Unix systems
  and ``;`` on Windows---except that empty entries are permitted. The paths
  are interpreted as follows:

  * If a path is empty, it is interpreted as the default value ``envs``.  
  * If a path is relative, it is interpreted relative to the root directory
    of the project itself (``PROJECT_DIR``). For example, a path entry
    ``envs`` is interpreted as

    * ``$PROJECT_DIR/envs`` (Unix)
    * ``%PROJECT_DIR%\envs`` (Windows)

  * When searching for an environment, the directories are searched in
    left-to-right order.
  * If an environment with the requested name is found nowhere in the path, 
    one will be created as a subdirectory of the first entry in the path.

  For example, given a Unix machine with
  
  ::

      ANACONDA_PROJECT_ENVS_PATH=/opt/envs::envs2:/home/user/conda/envs

  Then Anaconda Project will look for an environment named ``default``
  in the following locations:
  
  * ``/opt/envs/default``
  * ``$PROJECT_DIR/envs/default``
  * ``$PROJECT_DIR/envs2/default``
  * ``/home/user/conda/envs/default``

  If no such environment exists, one will be created as ``/opt/envs/default``,
  instead of the default location of ``$PROJECT_DIR/envs/default``.

``ANACONDA_PROJECT_READONLY_ENVS_POLICY``
  When an ``anaconda-project.yml`` specifies the use of an existing environment,
  but that environment is missing one or more of the requested packages,
  Anaconda Project attempts to remedy the deficiency by installing the missing
  packages. If the specified environment is *read-only*, however, such an
  installation would fail. The value of the environment variable
  ``ANACONDA_PROJECT_READONLY_ENVS_POLICY`` governs what action should be
  taken in such a case.

  ``fail``
    The attempt will fail, and a message returned indicating that the requested
    changes could not be made.

  ``clone``
    A clone of the read-only environment will be made, and additional packages
    will be installed into this cloned environment. Note that a clone will occur
    *only* if additional packages are required.

  ``replace``
    An entirely new environment will be created.

  If this environment variable is empty or contains any other value than these,
  the ``fail`` behavior will be assumed. Note that for ``clone`` or ``replace``
  to succeed, a writable environment location must exist somewhere in the
  ``ANACONDA_PROJECT_ENVS_PATH`` path.


Read-only environments
----------------------

On some systems, it is desirable to provide Anaconda Project access to one
or more *read-only* environments. These environments can be centrally
managed by administrators, and will speed up environment preparation
for users that elect to use them.

On Unix, a read-only environment is quite easy to enforce with standard
POSIX permissions settings. Unfortunately, our experience on Windows
systems suggests it is more challenging to enforce. For this reason,
we have adopted a simple approach that allows environments to be
explicitly marked as read-only with a flag file:

- If a file called ``.readonly`` is found in the root of an environment,
  that environment will be considered read-only.
- If a file called ``.readonly`` is found in the *parent* of an environment
  directory, the environment will be considered read-only.
- An attempt is made to write a file ``var/cache/anaconda-project/status``
  within the environment, creating the subdirectories as needed. If
  successful, the environment is considered read-write; otherwise, it
  is considered read-only.

This second test is particularly useful when centrally managing and entire
directory of environments. With a single ``.readonly`` flag file, all new
environments created within that directory will be treated as read-only.
Of course, for the best protection, POSIX or Windows read-only permissions
should be applied nevertheless.
