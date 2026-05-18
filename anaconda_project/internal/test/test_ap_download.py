# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2026, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Tests for the ap_download.py helper script.

The helper is what `pixi run prepare` invokes for each declared download
in a converted project. We exercise the unit behaviors directly here —
argument parsing, checksum verification, error handling — rather than
through a full export-and-run flow, which would cost a network round-trip.
"""
import hashlib
import os

import pytest

from anaconda_project.internal import ap_download


def _write(path, data):
    with open(path, 'wb') as f:
        f.write(data)


def _hexdigest(data, algo):
    h = hashlib.new(algo)
    h.update(data)
    return h.hexdigest()


class TestParseArgs:
    def test_two_positional(self):
        result = ap_download._parse_args(['url', 'file'])
        assert result == (['url', 'file'], None, None)

    def test_three_positional(self):
        result = ap_download._parse_args(['url', 'file', 'description'])
        assert result == (['url', 'file', 'description'], None, None)

    def test_with_sha256(self):
        result = ap_download._parse_args(['url', 'file', '--sha256', 'abc123'])
        assert result == (['url', 'file'], 'sha256', 'abc123')

    def test_hash_value_lowercased(self):
        # checksums in the yml may be uppercase; helpers compute lowercase
        # hex, so normalize at parse time so the comparison succeeds.
        result = ap_download._parse_args(['url', 'file', '--md5', 'ABCDEF'])
        assert result[2] == 'abcdef'

    def test_too_few_positional_returns_none(self):
        assert ap_download._parse_args(['url']) is None

    def test_too_many_positional_returns_none(self):
        assert ap_download._parse_args(['url', 'file', 'desc', 'extra']) is None

    def test_unknown_flag_returns_none(self):
        assert ap_download._parse_args(['url', 'file', '--bogus', 'x']) is None

    def test_flag_without_value_returns_none(self):
        assert ap_download._parse_args(['url', 'file', '--md5']) is None

    def test_multiple_hash_flags_returns_none(self):
        assert ap_download._parse_args(
            ['url', 'file', '--md5', 'a', '--sha256', 'b']) is None

    def test_flag_before_positional(self):
        # Flag/positional ordering shouldn't matter.
        result = ap_download._parse_args(['--sha1', 'deadbeef', 'url', 'file'])
        assert result == (['url', 'file'], 'sha1', 'deadbeef')


class TestChecksumOnExistingFile:
    def test_existing_file_matching_checksum_succeeds(self, tmp_path):
        target = tmp_path / 'data.bin'
        payload = b'hello world'
        _write(str(target), payload)
        sha = _hexdigest(payload, 'sha256')
        rc = ap_download.main(['unused-url', str(target), '--sha256', sha])
        assert rc == 0
        assert target.exists()

    def test_existing_file_mismatched_checksum_fails(self, tmp_path):
        target = tmp_path / 'data.bin'
        _write(str(target), b'hello world')
        rc = ap_download.main(['unused-url', str(target), '--sha256', 'deadbeef'])
        assert rc == 1
        # Existing files are NOT removed on mismatch — they may have been
        # edited intentionally; refuse rather than destroying user data.
        assert target.exists()


class TestChecksumOnDownload:
    def test_downloaded_file_matching_checksum_succeeds(self, tmp_path, monkeypatch):
        target = tmp_path / 'data.bin'
        payload = b'fetched content'

        def fake_urlretrieve(url, filename):
            with open(filename, 'wb') as f:
                f.write(payload)

        monkeypatch.setattr(ap_download.urllib.request, 'urlretrieve',
                            fake_urlretrieve)
        sha = _hexdigest(payload, 'sha256')
        rc = ap_download.main(['http://x/data', str(target), '--sha256', sha])
        assert rc == 0
        assert target.exists()
        with open(str(target), 'rb') as f:
            assert f.read() == payload

    def test_downloaded_file_mismatched_checksum_fails_and_cleans_up(
            self, tmp_path, monkeypatch):
        target = tmp_path / 'data.bin'

        def fake_urlretrieve(url, filename):
            with open(filename, 'wb') as f:
                f.write(b'wrong content')

        monkeypatch.setattr(ap_download.urllib.request, 'urlretrieve',
                            fake_urlretrieve)
        rc = ap_download.main(
            ['http://x/data', str(target), '--sha256', 'deadbeef'])
        assert rc == 1
        # Freshly-downloaded files DO get removed on mismatch — they
        # came from the network, not the user.
        assert not target.exists()

    def test_no_checksum_skips_verification(self, tmp_path, monkeypatch):
        target = tmp_path / 'data.bin'
        payload = b'content'

        def fake_urlretrieve(url, filename):
            with open(filename, 'wb') as f:
                f.write(payload)

        monkeypatch.setattr(ap_download.urllib.request, 'urlretrieve',
                            fake_urlretrieve)
        rc = ap_download.main(['http://x/data', str(target)])
        assert rc == 0
        assert target.exists()


class TestSkipsExisting:
    def test_existing_file_no_checksum_skips_download(self, tmp_path):
        target = tmp_path / 'data.bin'
        _write(str(target), b'whatever')
        # No urlretrieve patched — if it tried to download, we'd hit
        # the network. The skip guards against that.
        rc = ap_download.main(['http://x/data', str(target)])
        assert rc == 0


class TestUsage:
    def test_no_args_returns_2(self, capsys):
        rc = ap_download.main([])
        assert rc == 2
        err = capsys.readouterr().err
        assert 'usage:' in err
