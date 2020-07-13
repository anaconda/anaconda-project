# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Download related providers."""
from __future__ import print_function

import os
import shutil

from tornado.ioloop import IOLoop

from anaconda_project.internal.http_client import FileDownloader
from anaconda_project.internal.ziputils import unpack_zip
from anaconda_project.internal.simple_status import SimpleStatus
from anaconda_project.requirements_registry.provider import EnvVarProvider, ProviderAnalysis
from anaconda_project.provide import PROVIDE_MODE_CHECK
from anaconda_project.frontend import _new_error_recorder


class _DownloadProviderAnalysis(ProviderAnalysis):
    """Subtype of ProviderAnalysis showing if a filename exists."""
    def __init__(self, config, missing_to_configure, missing_to_provide, existing_filename):
        super(_DownloadProviderAnalysis, self).__init__(config, missing_to_configure, missing_to_provide)
        self.existing_filename = existing_filename


class DownloadProvider(EnvVarProvider):
    """Downloads a file according to the specified requirement."""
    def read_config(self, requirement, environ, local_state_file, default_env_spec_name, overrides):
        """Override superclass to return our config."""
        config = super(DownloadProvider, self).read_config(requirement, environ, local_state_file,
                                                           default_env_spec_name, overrides)

        assert 'source' in config
        assert config['source'] != 'default'

        if config['source'] == 'unset':
            config['source'] = 'download'

        return config

    def set_config_values_as_strings(self, requirement, environ, local_state_file, default_env_spec_name, overrides,
                                     values):
        """Override superclass to clear out environ if we decide not to use it."""
        super(DownloadProvider, self).set_config_values_as_strings(requirement, environ, local_state_file,
                                                                   default_env_spec_name, overrides, values)

        if 'source' in values and values['source'] != 'environ':
            # clear out the previous setting; this is sort of a hack. The problem
            # is that we don't want to delete env vars set in actual os.environ on
            # the command line, in our first pass, and in some subtypes of EnvVarProvider
            # (CondaEnvProvider) we also don't want to use it by default. Otherwise
            # we should probably do this in EnvVarProvider. future: rethink this.
            # a possible fix is to track an initial_environ for the whole prepare
            # sequence, separately from the current running environ?
            environ.pop(requirement.env_var, None)

    def analyze(self, requirement, environ, local_state_file, default_env_spec_name, overrides):
        """Override superclass to store additional fields in the analysis."""
        analysis = super(DownloadProvider, self).analyze(requirement, environ, local_state_file, default_env_spec_name,
                                                         overrides)
        filename = os.path.join(environ['PROJECT_DIR'], requirement.filename)
        if os.path.exists(filename):
            existing_filename = filename
        else:
            existing_filename = None
        return _DownloadProviderAnalysis(analysis.config,
                                         analysis.missing_env_vars_to_configure,
                                         analysis.missing_env_vars_to_provide,
                                         existing_filename=existing_filename)

    def _provide_download(self, requirement, context, frontend):
        filename = context.status.analysis.existing_filename
        if filename is not None:
            frontend.info("Previously downloaded file located at {}".format(filename))
            return filename

        filename = os.path.abspath(os.path.join(context.environ['PROJECT_DIR'], requirement.filename))
        if requirement.unzip:
            download_filename = filename + ".zip"
        else:
            download_filename = filename
        download = FileDownloader(url=requirement.url,
                                  filename=download_filename,
                                  hash_algorithm=requirement.hash_algorithm)

        try:
            _ioloop = IOLoop(make_current=False)
            response = _ioloop.run_sync(download.run)
            if response is None:
                for error in download.errors:
                    frontend.error(error)
                return None
            elif response.code == 200:
                if requirement.hash_value is not None and requirement.hash_value != download.hash:
                    frontend.error("Error downloading {}: mismatched hashes. Expected: {}, calculated: {}".format(
                        requirement.url, requirement.hash_value, download.hash))
                    return None
                if requirement.unzip:
                    unzip_errors = []
                    if unpack_zip(download_filename, filename, unzip_errors):
                        os.remove(download_filename)
                        return filename
                    else:
                        for error in unzip_errors:
                            frontend.error(error)
                        return None
                return filename
            else:
                frontend.error("Error downloading {}: response code {}".format(requirement.url, response.code))
                return None
        except Exception as e:
            frontend.error("Error downloading {}: {}".format(requirement.url, str(e)))
            return None
        finally:
            _ioloop.close()

    def provide(self, requirement, context):
        """Override superclass to start a download..

        If it locates a downloaded file with matching checksum, it sets the
        requirement's env var to that filename.

        """
        super_result = super(DownloadProvider, self).provide(requirement, context)

        if context.mode == PROVIDE_MODE_CHECK:
            return super_result
        # we do the download in both prod and dev mode

        frontend = _new_error_recorder(context.frontend)
        if requirement.env_var not in context.environ or context.status.analysis.config['source'] == 'download':
            filename = self._provide_download(requirement, context, frontend)
            if filename is not None:
                context.environ[requirement.env_var] = filename

        return super_result.copy_with_additions(errors=frontend.pop_errors())

    def unprovide(self, requirement, environ, local_state_file, overrides, requirement_status=None):
        """Override superclass to delete the downloaded file."""
        project_dir = environ['PROJECT_DIR']
        filename = os.path.abspath(os.path.join(project_dir, requirement.filename))
        try:
            if os.path.isdir(filename):
                shutil.rmtree(filename)
            elif os.path.isfile(filename):
                os.remove(filename)
            else:
                return SimpleStatus(success=True,
                                    description=("No need to remove %s which wasn't downloaded." % filename))
            return SimpleStatus(success=True, description=("Removed downloaded file %s." % filename))
        except Exception as e:
            return SimpleStatus(success=False, description=("Failed to remove %s: %s." % (filename, str(e))))
