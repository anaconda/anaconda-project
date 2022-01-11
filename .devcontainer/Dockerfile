ARG MINICONDA_VERSION='latest'
FROM continuumio/miniconda3:${MINICONDA_VERSION}

ARG USERNAME="vscode"
ARG UID=1000
ARG GID=${UID}
ARG PYTHON_VERSION="3.9"
ARG ENV_NAME="dev"
ARG ENV_YAML=''

##########################################
## It is not a good idea to use root since
## the source directory will be mounted
## into the container. Let's make a new
## user.
RUN groupadd --gid ${GID} ${USERNAME} \
    && useradd --gid ${GID} --uid ${UID} -m ${USERNAME} --create-home --shell /bin/bash
WORKDIR /home/${USERNAME}
USER ${USERNAME}
RUN conda config --prepend pkgs_dirs /home/${USERNAME}/.conda/pkgs

# Environment creation is done in two steps.
# 1. create env with desired Python version
# 2. apply required packages from specified environment.yml file
COPY ${ENV_YAML} /tmp/conda-tmp/environment.yml
RUN conda create -n ${ENV_NAME} python=${PYTHON_VERSION} \
    && if [ -f "/tmp/conda-tmp/environment.yml" ]; then \
          conda env update -n ${ENV_NAME} -f /tmp/conda-tmp/environment.yml; \
       fi