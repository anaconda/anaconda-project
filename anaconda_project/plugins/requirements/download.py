# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""File download requirements."""

from __future__ import absolute_import, print_function

import hashlib
import os

from anaconda_project.plugins.requirement import EnvVarRequirement
from anaconda_project.plugins.network_util import urlparse

_hash_algorithms = ('md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512')


class DownloadRequirement(EnvVarRequirement):
    """A requirement for ``env_var`` to point to a downloaded file."""

    @classmethod
    def _parse(cls, registry, varname, item, problems, requirements):
        """Parse an item from the downloads: section."""
        url = None
        filename = None
        hash_algorithm = None
        hash_value = None
        unzip = None
        if isinstance(item, str):
            url = item
        elif isinstance(item, dict):
            url = item.get('url', None)
            if url is None:
                problems.append("Download item {} doesn't contain a 'url' field.".format(varname))
                return

            for method in _hash_algorithms:
                if method not in item:
                    continue

                if hash_algorithm is not None:
                    problems.append("Multiple checksums for download {}: {} and {}.".format(varname, hash_algorithm,
                                                                                            method))
                    return
                else:
                    hash_value = item[method]
                    if isinstance(hash_value, str):
                        hash_algorithm = method
                    else:
                        problems.append("Checksum value for {} should be a string not {}.".format(varname, hash_value))
                        return

            filename = item.get('filename', None)
            unzip = item.get('unzip', None)
            if unzip is not None and not isinstance(unzip, bool):
                problems.append("Value of 'unzip' for download item {} should be a boolean, not {}.".format(varname,
                                                                                                            unzip))
                return

        if url == '':
            problems.append("Download item {} has an empty 'url' field.".format(varname))
            return

        # urlsplit doesn't seem to ever throw an exception, but it can
        # return pretty nonsensical stuff on invalid urls, in particular
        # an empty path is very possible
        url_path = os.path.basename(urlparse.urlsplit(url).path)
        url_path_is_zip = url_path.lower().endswith(".zip")

        if filename is None:
            if url_path != '':
                filename = url_path
                if url_path_is_zip:
                    if unzip is None:
                        # url is a zip and neither filename nor unzip specified, assume unzip
                        unzip = True
                    if unzip:
                        # unzip specified True, or we guessed True, and url ends in zip;
                        # take the .zip off the filename we invented based on the url.
                        filename = filename[:-4]
        elif url_path_is_zip and unzip is None and not filename.lower().endswith(".zip"):
            # URL is a zip, filename is not a zip, unzip was not specified, so assume
            # we want to unzip
            unzip = True

        if filename is None:
            filename = varname

        if unzip is None:
            unzip = False

        requirements.append(DownloadRequirement(registry,
                                                env_var=varname,
                                                url=url,
                                                filename=filename,
                                                hash_algorithm=hash_algorithm,
                                                hash_value=hash_value,
                                                unzip=unzip))

    def __init__(self, registry, env_var, url, filename, hash_algorithm=None, hash_value=None, unzip=False):
        """Extend init to accept url and hash parameters."""
        super(DownloadRequirement, self).__init__(registry=registry, env_var=env_var)
        assert url is not None
        assert filename is not None
        assert len(url) > 0
        assert len(filename) > 0
        self.url = url
        self.filename = filename
        assert hash_algorithm is None or hash_algorithm in _hash_algorithms
        self.hash_algorithm = hash_algorithm
        self.hash_value = hash_value
        self.unzip = unzip

    @property
    def title(self):
        """Override superclass to supply our title."""
        return "A downloaded file which is referenced by {}".format(self.env_var)  # pragma: no cover

    def _checksum_error_or_none(self, filename):
        if self.hash_algorithm is None:
            return None

        # future: keep track of how much of the file was read in %
        # st = os.stat(filename)
        # size = st.st_size

        read_size = 1024 * 1024
        checksum = getattr(hashlib, self.hash_algorithm)()
        with open(filename, 'rb') as f:
            data = f.read(read_size)
            while data:
                checksum.update(data)
                data = f.read(read_size)
        digest = checksum.hexdigest()
        if digest == self.hash_value:
            return None
        else:
            return 'File checksum error for {}, expected {} but was {}'.format(filename, self.hash_value, digest)

    def _why_not_provided(self, environ):
        if self.env_var not in environ:
            return self._unset_message()
        filename = environ[self.env_var]
        if not os.path.exists(filename):
            return 'File not found: {}'.format(filename)

        try:
            return self._checksum_error_or_none(filename)
        except OSError:
            return 'File referenced by: {} cannot be read ({})'.format(self.env_var, filename)

    def check_status(self, environ, local_state_file, latest_provide_result=None):
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
                                   provider_class_name='DownloadProvider',
                                   latest_provide_result=latest_provide_result)
