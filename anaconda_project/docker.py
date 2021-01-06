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


def build_image(path, tag, command, builder_image='adefusco/anaconda-project-ubi7', build_args=()):
    """Run s2i build."""

    cmd = ['s2i', 'build', '--copy', path, builder_image, tag, '-e', 'CMD={}'.format(command)]
    for arg in build_args:
        cmd.append('--{}'.format(arg))

    start_msg = '''*** {} image build starting.'''.format(tag)
    print(start_msg)

    try:
        _ = subprocess.check_call(cmd)
        msg = '''\nDocker image {} build successful.'''.format(tag)
        return SimpleStatus(success=True, description=msg)
    except subprocess.CalledProcessError as e:
        error_msg = '''\nAn error was encountered building this docker image.'''
        return SimpleStatus(success=False, description=error_msg, errors=[str(e)])
    except FileNotFoundError as e:
        error_msg = """\nERROR: The source-to-image (s2i) executable was not found. It can be installed using
    conda install -c defusco source-to-image"""
        return SimpleStatus(success=False, description=error_msg, errors=[str(e)])
