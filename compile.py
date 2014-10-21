from compileall import compile_dir
from distutils.sysconfig import get_python_lib
import os
import os.path
import sys

EXCLUDES = [
    'gunicorn/workers/_gaiohttp.py',
    'pymysql/_socketio.py',
]


def compile_files(path):
    return compile_dir(path, maxlevels=50, quiet=True)


def remove_python3_files(path):
    for e in EXCLUDES:
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
