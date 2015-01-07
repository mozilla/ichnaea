"""
This script is used as part of the "make wheel" command, used as part
of the travis-ci setup to create a cached wheelhouse which survives
consecutive builds and speeds up the build process.

It creates local wheels for all the Python dependencies containing
C extensions. Unfortunately "bin/pip wheel" doesn't recognize that
it already has a local wheel for these dependencies and would build
them again, so we manually check the presence of the wheel files.

This only works with requirement files containing exact version pins.
"""

from glob import glob
from optparse import OptionParser
import os
import os.path
import sys

from pip.req import parse_requirements


def absolute_path(path):
    return os.path.abspath(os.path.expanduser(path))


def build_wheels(command, wheelhouse, files):
    print command, wheelhouse, files
    if not os.path.isdir(wheelhouse):
        print('Wheelhouse %s not found.' % wheelhouse)
        return 0

    for filename in files:
        if not os.path.isfile(filename):
            print('Requirements file not found: %s' % filename)
            return 1
        for req in list(parse_requirements(filename, session=object())):
            reqname = req.name
            specs = req.req.specs
            if len(specs) != 1:
                print('Skipping wheel, multiple requirements for %s' % reqname)
            op, version = specs[0]
            if op != '==':
                print('Skipping wheel, non-exact requirement for %s' % reqname)
            pattern = os.path.join(wheelhouse,
                                   '%s-%s-*.whl' % (reqname, version))
            found = glob(pattern)
            if found:
                print ('Skipping build, wheel already exists: %s' % found)
                continue
            os.system('%s %s==%s' % (command, reqname, version))

    return 0


def main():
    parser = OptionParser()
    parser.add_option('-c', '--command', dest='command')
    parser.add_option('-w', '--wheelhouse', dest='wheelhouse')
    parser.add_option('-f', '--file', dest='files',
                      action='append', default=[])

    (options, _) = parser.parse_args()
    if not options.command or not options.wheelhouse or not options.files:
        parser.error('options -c, -w and -f are required')

    command = options.command
    wheelhouse = absolute_path(options.wheelhouse)
    files = [absolute_path(f) for f in options.files]

    status = build_wheels(command, wheelhouse, files)
    sys.exit(status)


if __name__ == '__main__':
    main()
