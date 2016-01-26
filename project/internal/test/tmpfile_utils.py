import tempfile
import shutil
import os.path


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
            try:
                os.makedirs(os.path.dirname(path))
            except IOError:
                pass
            f = open(path, 'w')
            f.write(file_content)
            f.flush()
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
