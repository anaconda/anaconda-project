# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""File download requirements."""

from __future__ import absolute_import, print_function

import os

from anaconda_project.requirements_registry.requirement import EnvVarRequirement
from anaconda_project.requirements_registry.network_util import urlparse

from anaconda_project.internal.py2_compat import is_string

_hash_algorithms = ('md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512')


class DownloadRequirement(EnvVarRequirement):
    """A requirement for ``env_var`` to point to a downloaded file."""
    @classmethod
    def _parse(cls, varname, item, problems):
        """Parse an item from the downloads: section."""
        url = None
        filename = None
        hash_algorithm = None
        hash_value = None
        unzip = None
        description = None
        if is_string(item):
            url = item
        elif isinstance(item, dict):
            url = item.get('url', None)
            if url is None:
                problems.append("Download item {} doesn't contain a 'url' field.".format(varname))
                return None

            description = item.get('description', None)
            if description is not None and not is_string(description):
                problems.append("'description' field for download item {} is not a string".format(varname))
                return None

            for method in _hash_algorithms:
                if method not in item:
                    continue

                if hash_algorithm is not None:
                    problems.append("Multiple checksums for download {}: {} and {}.".format(
                        varname, hash_algorithm, method))
                    return None
                else:
                    hash_value = item[method]
                    if is_string(hash_value):
                        hash_algorithm = method
                    else:
                        problems.append("Checksum value for {} should be a string not {}.".format(varname, hash_value))
                        return None

            filename = item.get('filename', None)
            unzip = item.get('unzip', None)
            if unzip is not None and not isinstance(unzip, bool):
                problems.append("Value of 'unzip' for download item {} should be a boolean, not {}.".format(
                    varname, unzip))
                return None

        if url is None or not is_string(url):
            problems.append(("Download name {} should be followed by a URL string or a dictionary " +
                             "describing the download.").format(varname))
            return None

        if url == '':
            problems.append("Download item {} has an empty 'url' field.".format(varname))
            return None

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

        return dict(env_var=varname,
                    url=url,
                    filename=filename,
                    hash_algorithm=hash_algorithm,
                    hash_value=hash_value,
                    unzip=unzip,
                    description=description)

    def __init__(self,
                 registry,
                 env_var,
                 url,
                 filename,
                 hash_algorithm=None,
                 hash_value=None,
                 unzip=False,
                 description=None):
        """Extend init to accept url and hash parameters."""
        options = None
        if description is not None:
            options = dict(description=description)
        super(DownloadRequirement, self).__init__(registry=registry, env_var=env_var, options=options)
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
    def description(self):
        """Override superclass to supply our description."""
        return self._description("A downloaded file which is referenced by {}.".format(self.env_var))

    @property
    def ignore_patterns(self):
        """Override superclass with our ignore patterns."""
        return set(['/' + self.filename, '/' + self.filename + ".part"])

    def _why_not_provided(self, environ):
        if self.env_var not in environ:
            return self._unset_message()
        filename = environ[self.env_var]
        if not os.path.exists(filename):
            return 'File not found: {}'.format(filename)

    def check_status(self, environ, local_state_file, default_env_spec_name, overrides, latest_provide_result=None):
        """Override superclass to get our status."""
        why_not_provided = self._why_not_provided(environ)

        has_been_provided = why_not_provided is None
        if has_been_provided:
            status_description = ("File downloaded to {}".format(self._get_value_of_env_var(environ)))
        else:
            status_description = why_not_provided
        return self._create_status(environ,
                                   local_state_file,
                                   default_env_spec_name,
                                   overrides=overrides,
                                   has_been_provided=has_been_provided,
                                   status_description=status_description,
                                   provider_class_name='DownloadProvider',
                                   latest_provide_result=latest_provide_result)
