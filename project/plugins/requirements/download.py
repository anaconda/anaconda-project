"""File download requirements."""

from __future__ import absolute_import, print_function

import hashlib
import os

from project.plugins.requirement import EnvVarRequirement
from project.plugins.network_util import urlparse


class DownloadRequirement(EnvVarRequirement):
    """A requirement for ``env_var`` to point to a downloaded file."""

    def __init__(self, registry, env_var, options):
        """Extend init by decoupling the hash method if present."""
        # options is a required parameter, no default.
        assert isinstance(options, dict)
        assert 'url' in options

        for method in ['md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512']:
            if method in options:
                options['hash_alg'] = method
                options['hash_value'] = options[method]
                options.pop(method)
                break

        if 'filename' not in options:
            filename = urlparse.urlsplit(options['url']).path
            options['filename'] = os.path.basename(filename)
        super(DownloadRequirement, self).__init__(registry=registry, env_var=env_var, options=options)

    @property
    def title(self):
        """Override superclass to supply our title."""
        return "A downloaded file which is referenced by {}".format(self.env_var)  # pragma: no cover

    def _checksum(self, filename):
        if 'hash_alg' not in self.options:
            return True

        # future: keep track of how much of the file was read in %
        # st = os.stat(filename)
        # size = st.st_size

        read_size = 1024 * 1024
        checksum = getattr(hashlib, self.options['hash_alg'])()
        with open(filename, 'rb') as f:
            data = f.read(read_size)
            while data:
                checksum.update(data)
                data = f.read(read_size)
        digest = checksum.hexdigest()
        return digest == self.options.get('hash_value', None)

    def _why_not_provided(self, environ):
        if self.env_var not in environ:
            return self._unset_message()
        filename = environ[self.env_var]
        if not os.path.exists(filename):
            return 'File not downloaded: {}'.format(filename)

        try:
            if not self._checksum(filename):
                return 'File download checksum error for {}'.format(filename)
        except OSError:
            return 'File referenced by: {} cannot be read ({})'.format(self.env_var, filename)

    def check_status(self, environ, local_state_file):
        """Override superclass to get our status."""
        why_not_provided = self._why_not_provided(environ)

        has_been_provided = why_not_provided is None
        if has_been_provided:
            status_description = ("File downloaded to {}".format(self._get_value_of_env_var(environ)))
        else:
            status_description = why_not_provided
        return self._create_status(environ,
                                   local_state_file,
                                   has_been_provided=has_been_provided,
                                   status_description=status_description,
                                   provider_class_name='DownloadProvider')
