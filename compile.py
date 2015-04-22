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

EXCLUDES_27 = [
    'linecache2/tests/inspect_fodder2.py',
    'raven/transport/aiohttp.py',
]
EXCLUDES_34 = [
    'gunicorn/workers/_gaiohttp.py',
]


def compile_files(path):
    return compile_dir(path, maxlevels=50, quiet=True)


def remove_python3_files(path):
    excludes = []
    if sys.version_info < (2, 7):
        excludes.extend(EXCLUDES_27)
    if sys.version_info < (3, 4):
        excludes.extend(EXCLUDES_34)

    for e in excludes:
        fp = os.path.join(path, e)
        for extension in ('', 'c', 'o'):
            name = fp + extension
            if os.path.exists(name):
                print('Removing file %s containing Python 3 syntax.' % name)
                os.remove(name)


def main():
    sp = get_python_lib()
    remove_python3_files(sp)
    status = compile_files(sp)
    sys.exit(not status)


if __name__ == '__main__':
    main()
