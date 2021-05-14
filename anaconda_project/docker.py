# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2020, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# (See LICENSE.txt for details)
# -----------------------------------------------------------------------------
"""Docker utilities."""

import subprocess

from anaconda_project.internal.simple_status import SimpleStatus

DEFAULT_BUILDER_IMAGE = 'conda/s2i-anaconda-project-ubi8'

try:
    FileNotFoundError  # noqa
except NameError:  # pragma: no cover
    # python 2
    FileNotFoundError = OSError


def build_image(path, tag, command, builder_image=DEFAULT_BUILDER_IMAGE, build_args=None):
    """Run s2i build."""

    cmd = ['s2i', 'build', '--copy', path, builder_image, tag, '-e', 'CMD={}'.format(command)]
    if build_args is not None:
        cmd.extend(build_args)

    start_msg = '''*** {} image build starting.'''.format(tag)
    print(start_msg)
    print(' '.join(cmd))

    try:
        _ = subprocess.check_call(cmd)
        msg = '''\nDocker image {} build successful.'''.format(tag)
        return SimpleStatus(success=True, description=msg)
    except subprocess.CalledProcessError as e:
        error_msg = '''\nAn error was encountered building this docker image.'''
        return SimpleStatus(success=False, description=error_msg, errors=[str(e)])
    except FileNotFoundError as e:
        error_msg = """\nERROR: The source-to-image (s2i) executable was not found. It can be installed using
    conda install -c ctools source-to-image"""
        return SimpleStatus(success=False, description=error_msg, errors=[str(e)])
