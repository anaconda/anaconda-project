'''Docker utilities'''

import os
import sys
import json
import shutil
import subprocess
from os import path

from anaconda_project.internal.simple_status import SimpleStatus

class _DockerBuildStatus(SimpleStatus):
    def __init__(self, image):
        self.image = image
        logs = []
        if self.image is not None:
            logs.append("Docker image %s was created successfully" % self.image)

        msg = '''\nDocker image {} build successful.'''.format(self.image)
        super(_DockerBuildStatus, self).__init__(success=True, description=msg, logs=logs)


def get_condarc(custom_path):
    '''return contents of condarc

    The following locations are sanned in order
    for the condarc file

    1. provided path
    2. ~/.anaconda-project/condarc
    3. <site-packages>/anaconda_project/condarc.dist (copied to #2)
    '''

    _path = path.expanduser(os.getenv('ANACONDA_PROJECT_CONFIG_DIR') or '~/.anaconda-project')
    user_file = path.join(_path, 'condarc')
    dist_file = path.join(path.dirname(__file__), 'condarc.dist')

    if custom_path:
        if path.exists(custom_path):
            condarc = custom_path
        else:
            msg = 'Custom condarc file {} was not found.'.format(custom_path)
            raise FileNotFoundError(msg)

    elif path.exists(user_file):
        condarc = user_file
    elif path.exists(dist_file):
        shutil.copy(dist_file, user_file)
        condarc = user_file
    else:
        msg = '''condarc was not found in any of the following locations
{}
{}
Please check that the file exists or that anaconda-project was installed properly.
Otherwise, please file a bug report.'''.format(user_file, dist_file)
        raise FileNotFoundError(msg)

    with open(condarc) as f:
        contents = f.read()
    return contents


def get_dockerfile(custom_path=None):
    '''return contents of dockerfile

    The following locations are scanned in order
    for the Dockerfile
    1. provided path
    2. ~/.anaconda-project/Dockerfile
    3. <site-packages>/anaconda_project/Dockerfile.dist (copied to #2)
    '''

    _path = path.expanduser(os.getenv('ANACONDA_PROJECT_CONFIG_DIR') or '~/.anaconda-project')
    user_file = path.join(_path, 'Dockerfile')
    dist_file = path.join(path.dirname(__file__), 'Dockerfile.dist')

    if custom_path:
        if path.exists(custom_path):
            dockerfile = custom_path
        else:
            msg = 'Custom Dockerfile {} was not found.'.format(custom_path)
            raise FileNotFoundError(msg)

    elif path.exists(user_file):
        dockerfile = user_file
    elif path.exists(dist_file):
        shutil.copy(dist_file, user_file)
        dockerfile = user_file
    else:
        msg = '''Dockerfile was not found in any of the following locations
{}
{}
Please check that the file exists or that anaconda-project was installed properly.
Otherwise, please file a bug report.'''.format(user_file, dist_file)
        raise FileNotFoundError(msg)

    with open(dockerfile) as f:
        contents = f.read()
    return contents

def build_image(path, tag, **build_args):
    cmd = ['docker', 'build', path, '-t', tag]
    for arg,value in build_args.items():
        cmd.append('--' + arg)
        cmd.append(value)

    start_msg = '''*** {} image build starting.'''.format(tag)
    print(start_msg)

    try:
        _ = subprocess.check_call(cmd)
        return _DockerBuildStatus(tag)
    except subprocess.CalledProcessError as e:
        error_msg = '''\nAn error was encountered building this docker image.
Check the Dockerfile and condarc.'''
        return SimpleStatus(success=False, description=error_msg, errors=[str(e)])
