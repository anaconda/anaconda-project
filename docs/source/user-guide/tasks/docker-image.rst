======================
Creating Docker Images
======================

*Available since version XYZ*

Use the ``dockerize`` command to create a Docker image from
the project. Images created from Anaconda Projects are
configured to execute a single :doc:`defined command <work-with-commands>`
in the ``anaconda-project.yml`` file chosen at build time.

The ``dockerize`` command uses `source-to-image (s2i) <https://github.com/openshift/source-to-image#source-to-image-s2i>`_
to build Docker images using the `s2i-anaconda-project builder images <https://github.com/Anaconda-Platform/s2i-anaconda-project>`_
that have been uploaded to Docker Hub.

Images built with ``dockerize`` will have a fully prepared ``env_spec`` for the desired
command and expose port 8086 if the command listens for HTTP requests.


Prerequisites
-------------

In order to utilize the ``dockerize`` command you will need to
have Docker and source-to-image (s2i) installed.

* `Docker <https://docs.docker.com/get-docker/>`_
* `source-to-image <https://github.com/openshift/source-to-image#source-to-image-s2i>`_

You can install s2i using Conda

.. code-block:: text

  conda install -c ctools source-to-image


Quickstart
----------

#. Build a docker image to run a supplied command

   .. code-block:: text

     anaconda-project dockerize --command <command-name> -t <image name>

#. Run the Docker image and publish port 8086

   .. code-block:: text

     docker run -p 8086:8086 <image name>

It is necessary to add ``-p 8086:8086`` in order to publish port 8086 from the anaconda-project container
out to the host. The second entry in the ``-p`` flag must be ``8086`` while the first entry
can be any valid unused port on the host. See `the Docker container networking docs for more details. <https://docs.docker.com/config/containers/container-networking/>`_


Build Docker images
-------------------

By default running the ``dockerize`` command will create a
Docker image to execute the *default* command.

The *default* command is determined in the following order

#. The command named ``default``
#. The first command listed in the project file if no command is named ``default``

The ``s2i-anaconda-project`` builder images have Miniconda and ``anaconda-project`` installed. When the ``dockerize``
command is run the following steps are performed.

#. The project is archived to a temporary directory to ensure that files listed in your ``.projectignore`` (including
   the local ``envs`` directory) are not copied into the Docker image.
#. The ``s2i build`` command is run from the temporary directory to construct a new Docker image from the builder image.

The steps in the ``s2i build`` process are

#. The temporary project directory is added to the image.
#. The `s2i assemble script <https://github.com/Anaconda-Platform/s2i-anaconda-project/blob/master/s2i/bin/assemble>`_ is run to prepare the ``env_spec`` for the desired command.
#. Conda clean is run to reduce the size of the output Docker image.


Options
^^^^^^^

The ``dockerize`` command accepts several optional arguments

``--command``
  The named command to execute in the ``RUN`` layer of the Docker image.
  Default: ``default``
  See the HTTP commands section below.

``-t`` or ``--tag``
  The name of the output Docker image in the format ``name:tag``. By default
  Default: "<project-name>:latest", where <project-name> is taken from the name
  tag in the anaconda-project.yml file.

``--builder-image``
  The s2i builder image name to use.
  Default: ``conda/s2i-anaconda-project-ubi7``
  By default this is image is pulled from DockerHub when ``dockerize`` is run.
  See the Custom Builder Image section below to construct your own builder images.

s2i build arguments
  Any further arguments or those supplied after ``--`` will be given to the ``s2i build`` command.
  See the `s2i build documentation for available build flags. <https://github.com/openshift/source-to-image/blob/master/docs/cli.md#build-flags>`_

Builder images
^^^^^^^^^^^^^^

The default builder image for ``anaconda-project dockerize`` is ``conda/s2i-anaconda-project-ubi7``. To see
other available builder images on DockerHub `click here <https://hub.docker.com/search?q=conda%2Fs2i-anaconda-project&type=image>`_.


HTTP options
^^^^^^^^^^^^

When the docker image is run the `s2i run script <https://github.com/Anaconda-Platform/s2i-anaconda-project/blob/master/s2i/bin/run>`_
is executed with the supplied command. The full run command is

.. code-block:: bash

  anaconda-project run $CMD --anaconda-project-port 8086 --anaconda-project-address 0.0.0.0 --anaconda-project-no-browser --anaconda-project-use-xheaders

This ensures that the command communicates over port 8086 if it supports the :ref:`http-commands`.

If your desired command is not an HTTP command or you wish not to use the Jinja2 template features you must add
``supports_http_options: false`` to the command specification in the ``anaconda-project.yml`` file. When
``supports_http_options`` is set to ``false`` the HTTP arguments are completely ignored when the command is executed.


Configuring Conda
^^^^^^^^^^^^^^^^^

In addition to the channel configuration available in the ``anaconda-project.yml``
file you may need to supply custom `Conda configuration parameters <https://docs.conda.io/projects/conda/en/latest/user-guide/configuration/use-condarc.html>`_
in order to build the Docker image.

To provide a custom Conda configuration, place a ``.condarc`` file at the top-level
of your project directory.

For example, you can use the ``.condarc`` to configure access to
`Anaconda Team Edition <https://team-docs.anaconda.com/en/latest/user/conda.html>`_ or `Anaconda Commercial Edition <https://docs.anaconda.com/anaconda-commercial/quickstart/#setting-up-condarc-for-commercial-edition>`_.

Custom builder images
---------------------

If you want to customize the builder images you can clone the `s2i-anaconda-project repository <https://github.com/Anaconda-Platform/s2i-anaconda-project>`_,
build the images. The custom builder images can be provided to ``anaconda-project dockerize`` using the ``--builder-image``
flag.
