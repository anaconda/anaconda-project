"""Download related providers."""
from __future__ import print_function

import os

from tornado.ioloop import IOLoop

from project.internal.http_client import FileDownloader
from project.plugins.provider import EnvVarProvider, ProviderAnalysis


class _DownloadProviderAnalysis(ProviderAnalysis):
    """Subtype of ProviderAnalysis showing if a filename exists."""

    def __init__(self, config, missing_to_configure, missing_to_provide, existing_filename):
        super(_DownloadProviderAnalysis, self).__init__(config, missing_to_configure, missing_to_provide)
        self.existing_filename = existing_filename


class DownloadProvider(EnvVarProvider):
    """Downloads a file according to the specified requirement."""

    def read_config(self, context):
        """Override superclass to return our config."""
        config = super(DownloadProvider, self).read_config(context)

        assert 'source' in config
        assert config['source'] != 'default'

        if config['source'] == 'unset':
            config['source'] = 'download'

        return config

    def set_config_values_as_strings(self, context, values):
        """Override superclass to clear out environ if we decide not to use it."""
        super(DownloadProvider, self).set_config_values_as_strings(context, values)

        if 'source' in values and values['source'] != 'environ':
            # clear out the previous setting; this is sort of a hack. The problem
            # is that we don't want to delete env vars set in actual os.environ on
            # the command line, in our first pass, and in some subtypes of EnvVarProvider
            # (CondaEnvProvider) we also don't want to use it by default. Otherwise
            # we should probably do this in EnvVarProvider. future: rethink this.
            # a possible fix is to track an initial_environ for the whole prepare
            # sequence, separately from the current running environ?
            context.environ.pop(context.requirement.env_var, None)

    def _extra_source_options_html(self, context, status):
        analysis = status.analysis

        if analysis.existing_filename is not None:
            if context.environ.get(context.requirement.env_var, None) == analysis.existing_filename:
                # avoid redundant choice
                extra_html = ""
            else:
                extra_html = """
            <div>
              <label><input type="radio" name="source" value="download"/>Use already-downloaded file {}</label>
            </div>
            """.format(analysis.existing_filename)
        else:
            extra_html = """
            <div>
              <label><input type="radio" name="source" value="download"/>Download {} to {}</label>
            </div>
            """.format(context.requirement.url, context.requirement.filename)

        return extra_html

    def analyze(self, requirement, environ, local_state_file):
        """Override superclass to store additional fields in the analysis."""
        analysis = super(DownloadProvider, self).analyze(requirement, environ, local_state_file)
        filename = os.path.join(environ['PROJECT_DIR'], requirement.filename)
        if os.path.exists(filename):
            existing_filename = filename
        else:
            existing_filename = None
        return _DownloadProviderAnalysis(analysis.config,
                                         analysis.missing_env_vars_to_configure,
                                         analysis.missing_env_vars_to_provide,
                                         existing_filename=existing_filename)

    def _provide_download(self, requirement, context):
        filename = context.status.analysis.existing_filename
        if filename is not None:
            context.append_log("Previously downloaded file located at {}".format(filename))
            return filename

        filename = os.path.abspath(os.path.join(context.environ['PROJECT_DIR'], requirement.filename))
        download = FileDownloader(url=requirement.url, filename=filename, hash_algorithm=requirement.hash_algorithm)

        try:
            _ioloop = IOLoop(make_current=False)
            response = _ioloop.run_sync(lambda: download.run(_ioloop))
            if response.code == 200:
                return filename
            else:
                context.append_error("Error downloading {}: response code {}".format(requirement.url, response.code))
                return None
        except Exception as e:
            context.append_error("Error downloading {}: {}".format(requirement.url, str(e)))
            return None
        finally:
            _ioloop.close()

    def provide(self, requirement, context):
        """Override superclass to start a download..

        If it locates a downloaded file with matching checksum, it sets the
        requirement's env var to that filename.

        """
        super(DownloadProvider, self).provide(requirement, context)

        if requirement.env_var not in context.environ or context.status.analysis.config['source'] == 'download':
            filename = self._provide_download(requirement, context)
            if filename is not None:
                context.environ[requirement.env_var] = filename
