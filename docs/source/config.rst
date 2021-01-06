=============
Configuration
=============

Anaconda Project has two modifiable configuration settings. Currently
these setting are controlled exclusively by environment variables.

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
  When using ``ANACONDA_PROJECT_ENVS_PATH`` one or more of the envs directories
  may contain read-only environments. These environments can be created on shared
  systems to speed-up project preparation steps by providing a pre-built environment
  matching an ``env_spec`` defined in a user's ``anaconda-project.yml`` file.

  For the scenario where a user specifies an ``env_spec`` that is found in a read-only
  directory and when the package list differs from the environment on disk the
  ``ANACONDA_PROJECT_READONLY_ENVS_POLICY`` variable controls what action is taken.

  The ``ANACONDA_PROJECT_READONLY_ENVS_POLICY`` variable accepts two values ``fail``
  and ``clone``. The default behavior is ``fail`` if this variable is not set.

  ``fail``
    If a user requests changes to be made to a read-only environment the action will
    fail with a message that the requested changes cannot be made. 

  ``clone``
    If a user requests changes to be make to a read-only environment anaconda-project
    will first clone the read-only environment to the first writable path in the
    ``ANACONDA_PROJECT_ENVS_PATH`` list before making modifications. If no modifications
    to a read-only environment are requested then the environment will not be cloned.
