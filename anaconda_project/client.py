# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
"""Talking to the Anaconda server."""
from __future__ import absolute_import, print_function

import os
import tarfile
import zipfile

import requests
import binstar_client.utils as binstar_utils
import binstar_client.requests_ext as binstar_requests_ext
from binstar_client.errors import BinstarError, Unauthorized

from anaconda_project.internal.simple_status import SimpleStatus


class _Client(object):
    def __init__(self, site=None):
        assert hasattr(binstar_utils, 'get_server_api'), "Please upgrade anaconda-client"
        self._api = binstar_utils.get_server_api(site=site)
        self._user_info = None

    def _username(self):
        """Get username if known, otherwise raise Unauthorized."""
        if self._user_info is None:
            self._user_info = self._api.user()
        assert self._user_info is not None
        username = self._user_info.get('login', None)
        if username is None:
            raise Unauthorized()
        else:
            return username

    def _check_response(self, res, allowed=(200, 201)):
        # using a little private API here.
        self._api._check_response(res, allowed=list(allowed))

    # HACK ALERT: using this is a workaround for
    # https://github.com/Anaconda-Platform/anaconda-server/issues/2229
    def _exists(self, project_name):
        url = "{}/apps/{}/projects/{}".format(self._api.domain, self._username(), project_name)
        res = self._api.session.get(url)
        return res.status_code == 200

    def create(self, project):
        assert not project.problems

        url = "{}/apps/{}/projects".format(self._api.domain, self._username())
        json = {'name': project.name, 'access': 'public', 'profile': {'description': project.description}}
        data, headers = binstar_utils.jencode(json)
        res = self._api.session.post(url, data=data, headers=headers)
        self._check_response(res)
        return res

    def _file_count(self, bundle_filename):
        for suffix in (".tar", ".tar.gz", ".tar.bz2"):
            if bundle_filename.lower().endswith(suffix):
                with tarfile.open(bundle_filename, 'r') as tf:
                    return len(tf.getnames())
        if bundle_filename.lower().endswith(".zip"):
            with zipfile.ZipFile(bundle_filename, 'r') as zf:
                return len(zf.namelist())
        assert False, ("unsupported bundle filename %s" % bundle_filename)  # pragma: no cover (should not be reached)

    def stage(self, project, bundle_filename):
        assert not project.problems

        url = "{}/apps/{}/projects/{}/stage".format(self._api.domain, self._username(), project.name)
        config = project.publication_info().copy()
        config['size'] = os.path.getsize(bundle_filename)
        file_count = self._file_count(bundle_filename)
        if file_count is not None:
            config['num_of_files'] = file_count
        json = {'basename': ("%s.tar" % project.name), 'configuration': config, 'size': config['size']}
        data, headers = binstar_utils.jencode(json)
        res = self._api.session.post(url, data=data, headers=headers)
        self._check_response(res)
        return res

    def commit(self, project_name, revision_id):

        url = "{}/apps/{}/projects/{}/commit".format(self._api.domain, self._username(), project_name)
        data, headers = binstar_utils.jencode({'revision_id': revision_id})
        res = self._api.session.post(url, data=data, headers=headers)
        self._check_response(res)
        return res

    def _put_on_s3(self, bundle_filename, url, s3data):
        with open(bundle_filename, 'rb') as f:
            _hexmd5, b64md5, size = binstar_utils.compute_hash(f, size=os.path.getsize(bundle_filename))

        s3data = s3data.copy()  # don't modify our parameters
        s3data['Content-Length'] = size
        s3data['Content-MD5'] = b64md5

        with open(bundle_filename, 'rb') as bundle_file_object:
            data_stream, headers = binstar_requests_ext.stream_multipart(
                s3data,
                files={'file': (os.path.basename(bundle_filename), bundle_file_object)})

            res = requests.post(url,
                                data=data_stream,
                                verify=self._api.session.verify,
                                timeout=10 * 60 * 60,
                                headers=headers)
            self._check_response(res)
        return res

    def upload(self, project, bundle_filename):
        """Upload bundle_filename created from project, throwing BinstarError."""
        assert not project.problems

        if not self._exists(project.name):
            res = self.create(project=project)
            assert res.status_code in (200, 201)

        res = self.stage(project=project, bundle_filename=bundle_filename)
        assert res.status_code in (200, 201)

        stage_info = res.json()

        res = self._put_on_s3(bundle_filename, url=stage_info['post_url'], s3data=stage_info['form_data'])
        assert res.status_code in (200, 201)

        res = self.commit(project.name, stage_info['form_data']['revision_id'])
        assert res.status_code in (200, 201)

        return res.json()


# This function is supposed to encapsulate the binstar API (don't
# require any other files to import binstar_client).
def _upload(project, bundle_filename, site=None):
    client = _Client(site=site)
    try:
        json = client.upload(project, bundle_filename)
        logs = []
        if 'url' in json:
            logs.append("Project is at %s" % json['url'])
        return SimpleStatus(success=True, description="Upload successful.", logs=logs)
    except Unauthorized as e:
        return SimpleStatus(success=False,
                            description='Please log in with the "anaconda login" command.',
                            errors=["Not logged in."])
    except BinstarError as e:
        return SimpleStatus(success=False, description="Upload failed.", errors=[str(e)])
