# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2017, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import os
import pytest

import anaconda_project.internal.streaming_popen as streaming_popen
from anaconda_project.internal.test.tmpfile_utils import tmp_script_commandline


def add_lineseps(lines):
    return list(map(lambda l: l + os.linesep, lines))


def test_streaming():
    print_stuff = tmp_script_commandline("""from __future__ import print_function
import sys
import time

def flush():
    time.sleep(0.05)
    sys.stdout.flush()
    sys.stderr.flush()

print("a")
flush()
print("x", file=sys.stderr)
flush()
print("b")
flush()
print("y", file=sys.stderr)
flush()
print("c")
flush()
print("z", file=sys.stderr)
flush()
print("d")
flush()

sys.exit(2)
""")

    stdout_from_callback = []

    def on_stdout(line):
        stdout_from_callback.append(line)

    stderr_from_callback = []

    def on_stderr(line):
        stderr_from_callback.append(line)

    (p, out_lines, err_lines) = streaming_popen.popen(print_stuff, on_stdout, on_stderr)

    assert p.returncode is 2

    expected_out = add_lineseps(['a', 'b', 'c', 'd'])
    expected_err = add_lineseps(['x', 'y', 'z'])

    assert expected_out == out_lines
    assert expected_out == stdout_from_callback

    assert expected_err == err_lines
    assert expected_err == stderr_from_callback


def test_bad_utf8():
    print_bad = tmp_script_commandline("""from __future__ import print_function
import os
import sys

print("hello")
sys.stdout.flush()
# write some garbage
os.write(sys.stdout.fileno(), b"\\x42\\xff\\xef\\xaa\\x00\\x01\\xcc")
sys.stdout.flush()
print("goodbye")
sys.stdout.flush()

sys.exit(0)
""")

    stdout_from_callback = []

    def on_stdout(line):
        stdout_from_callback.append(line)

    stderr_from_callback = []

    def on_stderr(line):
        stderr_from_callback.append(line)

    with pytest.raises(UnicodeDecodeError):
        streaming_popen.popen(print_bad, on_stdout, on_stderr)

    expected_out = add_lineseps(['hello'])
    expected_err = []

    assert expected_out == stdout_from_callback
    assert expected_err == stderr_from_callback


def test_callbacks_are_none():
    print_stuff = tmp_script_commandline("""from __future__ import print_function
import sys

print("a")
print("b", file=sys.stderr)

sys.exit(0)
""")

    (p, out_lines, err_lines) = streaming_popen.popen(print_stuff, None, None)

    assert p.returncode is 0

    expected_out = add_lineseps(['a'])
    expected_err = add_lineseps(['b'])

    assert expected_out == out_lines
    assert expected_err == err_lines
