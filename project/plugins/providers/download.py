"""Download related providers."""
from __future__ import print_function

import os
import functools

from tornado.ioloop import IOLoop

from project.internal.http_client import FileDownloader
from project.plugins.provider import Provider, ProviderAnalysis


class _DownloadProviderAnalysis(ProviderAnalysis):
    """Subtype of ProviderAnalysis showing if a filename exists."""

    def __init__(self, config, missing_to_configure, missing_to_provide, existing_scoped_filename):
        super(_DownloadProviderAnalysis, self).__init__(config, missing_to_configure, missing_to_provide)
        self.existing_scoped_filename = existing_scoped_filename


class DownloadProvider(Provider):
    """Downloads a file according to the specified requirement."""

    def config_section(self, requirement):
        """Special case for section."""
        # downloads:
        #   env_var_name:
        #       url: http://ip:port/path.ext
        #       hash_algorithm: hash_value
        return ["downloads", requirement.env_var]

    def read_config(self, context):
        """Override superclass to return our config."""
        config = {'url': None}
        section = self.config_section(context.requirement)
        config['url'] = context.local_state_file.get_value(section + ['url'])
        for method in ['md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512']:
            value = context.local_state_file.get_value(section + [method])
            if value:
                config['hash_value'] = value
                config['hash_algorithm'] = method
                break

        if 'hash_algorithm' not in config:
            config['hash_value'] = context.local_state_file.get_value(section + ['hash_value'])
            config['hash_algorithm'] = context.local_state_file.get_value(section + ['hash_algorithm'])
        config['filename'] = context.local_state_file.get_value(section + ['filename'])

        return config

    def set_config_values_as_strings(self, context, values):
        """Override superclass to set our config values."""
        section = self.config_section(context.requirement)

        for key, value in values.items():
            context.local_state_file.set_value(section + [key], value)

    def config_html(self, context, status):
        """Override superclass to provide our config html."""
        analysis = status.analysis

        if analysis.existing_scoped_filename is not None:
            project_option = "<form>Previously downloaded file located at {}</form>".format(
                analysis.existing_scoped_filename)
        else:
            project_option = ('<form>'
                              'Download a file at url: <input type="text" name="url"/><br>'
                              'Download to location: <input type="text" name="filename"/><br>'
                              'Verification algorithm: <input type="text" name="hash_algorithm"/><br>'
                              'Checksum value: <input type="text" name="hash_value"/><br>'
                              '</form>')
        return project_option

    def _previous_file_state(self, file_state):
        if 'filename' not in file_state:
            return
        if os.path.exists(file_state['filename']):
            return file_state['filename']

    def analyze(self, requirement, environ, local_state_file):
        """Override superclass to store additional fields in the analysis."""
        analysis = super(DownloadProvider, self).analyze(requirement, environ, local_state_file)
        # future: change run state to something more appropriate.
        file_state = local_state_file.get_service_run_state(requirement.env_var)
        previous_filename = self._previous_file_state(file_state)

        return _DownloadProviderAnalysis(analysis.config,
                                         analysis.missing_env_vars_to_configure,
                                         analysis.missing_env_vars_to_provide,
                                         existing_scoped_filename=previous_filename)

    def _provide_download(self, requirement, context):
        def _ensure_download(requirement, context, run_state):
            filename = context.status.analysis.existing_scoped_filename
            if filename is not None and os.path.exists(filename):
                context.append_log("Previously downloaded file located at {}".format(filename))
                return filename

            url = requirement.options['url']
            filename = requirement.options['filename']
            filename = os.path.join(context.environ['PROJECT_DIR'], filename)
            run_state.clear()
            hash_algorithm = requirement.options.get('hash_algorithm', None)
            download = FileDownloader(url=url, filename=filename, hash_algorithm=hash_algorithm)

            try:
                _ioloop = IOLoop()
                response = _ioloop.run_sync(lambda: download.run(_ioloop))
                if response.code == 200:
                    run_state['filename'] = os.path.abspath(filename)
            except Exception as e:
                print("Error downloading {}: {}".format(url, str(e)))
            finally:
                _ioloop.close()
            return run_state.get('filename', None)

        ensure_download = functools.partial(_ensure_download, requirement, context)

        return context.transform_service_run_state(requirement.env_var, ensure_download)

    def provide(self, requirement, context):
        """Override superclass to start a download..

        If it locates a downloaded file with matching checksum, it sets the
        requirement's env var to that filename.

        """
        assert 'PATH' in context.environ
        filename = self._provide_download(requirement, context)

        if filename is not None:
            context.environ[requirement.env_var] = filename
