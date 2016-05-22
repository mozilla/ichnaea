"""
This script is used as part of the "make release" command used as part of
building an rpm of this entire virtualenv.

The rpm building process compiles all *.py files found anywhere in the
source tree, independent of whether or not these would actually be used.
It finds some Python files which aren't meant for the specific Python
version being build this way and would abort the build process.

We therefor specifically remove files from our site-packages directory,
which aren't meant for the current Python version and include incompatible
Python syntax.
"""

from compileall import compile_dir
from distutils.sysconfig import get_python_lib
import os
import os.path
import sys

# files excluded when run under Python 2.x
PYTHON_2_INCOMPATIBLE = [
    'gevent/_socket3.py',
    'gunicorn/workers/_gaiohttp.py',
    'linecache2/tests/inspect_fodder2.py',
    'pymysql/tests/test_cursor.py',
]
# files excluded when run under Python 3.x
PYTHON_3_INCOMPATIBLE = [
    'gevent/_util_py2.py',
]


def compile_files(path):
    return compile_dir(path, maxlevels=50, quiet=True)


def remove_incompatible_files(path):
    excludes = []
    if sys.version_info < (3, 0):
        excludes.extend(PYTHON_2_INCOMPATIBLE)
    if sys.version_info >= (3, 0):
        excludes.extend(PYTHON_3_INCOMPATIBLE)

    for e in excludes:
        fp = os.path.join(path, e)
        for extension in ('', 'c', 'o'):
            name = fp + extension
            if os.path.exists(name):
                print('Removing file %s with incompatible syntax.' % name)
                os.remove(name)


def main():
    sp = get_python_lib()
    remove_incompatible_files(sp)
    status = compile_files(sp)
    sys.exit(not status)


if __name__ == '__main__':
    main()
