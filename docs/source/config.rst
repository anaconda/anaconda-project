=============
Configuration
=============

Anaconda Project has only one modifiable configuration setting. Currently
this setting is controlled exclusively by an environment variable.

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
  * If an environment with the requeted name is found nowhere in the path, 
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
