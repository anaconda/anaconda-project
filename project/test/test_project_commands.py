from __future__ import absolute_import, print_function

from project.project_commands import CommandExecInfo

import os
import pytest


def test_execvpe_with_shell(monkeypatch):
    executed = {}

    def mock_execvpe(file, args, env):
        executed['file'] = file
        executed['args'] = args
        executed['env'] = env

    monkeypatch.setattr('os.execvpe', mock_execvpe)
    info = CommandExecInfo(cwd=os.getcwd(), args=['foo', 'bar'], shell=True, env=dict(FOO='bar'))
    info.execvpe()

    assert executed['file'] == '/bin/sh'
    assert executed['args'] == ['/bin/sh', '-c', 'foo', 'bar']
    assert executed['env'] == dict(FOO='bar')


def test_execvpe_with_shell_on_windows(monkeypatch):
    def mock_platform_system():
        return 'Windows'

    monkeypatch.setattr('platform.system', mock_platform_system)

    info = CommandExecInfo(cwd='/somewhere', args=['foo', 'bar'], shell=True, env=dict(FOO='bar'))
    with pytest.raises(NotImplementedError) as excinfo:
        info.execvpe()

    assert 'exec on Windows is not implemented' in repr(excinfo.value)
