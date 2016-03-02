import tempfile
import shutil
import os.path

from project.internal.makedirs import makedirs_ok_if_exists
from project.local_state_file import LocalStateFile


class TmpDir(object):
    def __init__(self, prefix):
        self._dir = tempfile.mkdtemp(prefix=prefix)

    def __exit__(self, type, value, traceback):
        shutil.rmtree(path=self._dir)

    def __enter__(self):
        return self._dir


def with_directory_contents(contents, func):
    with (TmpDir(prefix="project-test-tmpdir-")) as dirname:
        for filename, file_content in contents.items():
            path = os.path.join(dirname, filename)
            makedirs_ok_if_exists(os.path.dirname(path))
            f = open(path, 'w')
            f.write(file_content)
            f.flush()
            f.close()
        func(dirname)


def with_temporary_file(func, dir=None):
    import tempfile
    f = tempfile.NamedTemporaryFile(dir=dir)
    try:
        func(f)
    finally:
        f.close()


def with_file_contents(contents, func, dir=None):
    def with_file_object(f):
        f.write(contents.encode("UTF-8"))
        f.flush()
        func(f.name)

    with_temporary_file(with_file_object, dir=dir)


def tmp_local_state_file():
    import tempfile
    f = tempfile.NamedTemporaryFile(dir=None)
    local_state = LocalStateFile(f.name)
    f.close()
    return local_state
