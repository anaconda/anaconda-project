# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2017, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import subprocess
from threading import Thread

try:
    from queue import Queue
except ImportError:  # pragma: no cover (py2 only)
    from Queue import Queue  # pragma: no cover (py2 only)

from anaconda_project.internal import logged_subprocess


def read_and_queue_line(pipe, queue):
    try:
        while True:
            line = pipe.readline()
            if len(line) == 0:
                break
            line = line.decode('utf-8')
            queue.put((pipe, line, None))
        queue.put((pipe, None, None))
    except Exception as e:
        queue.put((pipe, None, e))
    finally:
        pipe.close()


def reader_thread(pipe, queue):
    t = Thread(target=read_and_queue_line, args=(pipe, queue))
    t.daemon = True
    t.start()
    return t


def popen(args, stdout_callback, stderr_callback, **kwargs):
    """Run a command, invoking callbacks for lines of output."""
    p = logged_subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    queue = Queue()

    stdout_thread = reader_thread(p.stdout, queue)
    stderr_thread = reader_thread(p.stderr, queue)

    stdout_buffer = []
    stderr_buffer = []

    first_error = None
    while stdout_thread.is_alive() or stderr_thread.is_alive():
        (which, line, error) = queue.get()
        if error is not None and first_error is None:
            first_error = error
        if line is None:
            if which is p.stdout:
                stdout_thread.join()
                assert not stdout_thread.is_alive()
            else:
                assert which is p.stderr
                stderr_thread.join()
                assert not stderr_thread.is_alive()
        else:
            if which is p.stdout:
                stdout_callback(line)
                stdout_buffer.append(line)
            else:
                assert which is p.stderr
                stderr_callback(line)
                stderr_buffer.append(line)

    p.wait()

    if first_error is not None:
        raise first_error

    return (p, stdout_buffer, stderr_buffer)
