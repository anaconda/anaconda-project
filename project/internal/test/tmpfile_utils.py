import tempfile
import shutil
import os

from project.internal.makedirs import makedirs_ok_if_exists
from project.local_state_file import LocalStateFile

local_tmp = os.path.abspath("./build/tmp")
makedirs_ok_if_exists(local_tmp)


class TmpDir(object):
    def __init__(self, prefix):
        self._dir = tempfile.mkdtemp(prefix=prefix, dir=local_tmp)

    def __exit__(self, type, value, traceback):
        shutil.rmtree(path=self._dir)

    def __enter__(self):
        return self._dir


def with_directory_contents(contents, func):
    with (TmpDir(prefix="test-")) as dirname:
        for filename, file_content in contents.items():
            path = os.path.join(dirname, filename)
            makedirs_ok_if_exists(os.path.dirname(path))
            f = open(path, 'w')
            f.write(file_content)
            f.flush()
            f.close()
        func(os.path.realpath(dirname))


def with_temporary_file(func, dir=None):
    if dir is None:
        dir = local_tmp
    import tempfile
    # Windows throws a permission denied if we use delete=True for
    # auto-delete, and then try to open the file again ourselves
    # with f.name. So we manually delete in the finally block
    # below.
    f = tempfile.NamedTemporaryFile(dir=dir, delete=False)
    try:
        func(f)
    finally:
        f.close()
        os.remove(f.name)


def with_file_contents(contents, func, dir=None):
    def with_file_object(f):
        f.write(contents.encode("UTF-8"))
        f.flush()
        # Windows will get mad if we try to rename it without closing,
        # and some users of with_file_contents want to rename it.
        f.close()
        func(f.name)

    with_temporary_file(with_file_object, dir=dir)


def tmp_local_state_file():
    import tempfile
    f = tempfile.NamedTemporaryFile(dir=local_tmp)
    local_state = LocalStateFile(f.name)
    f.close()
    return local_state
