import os
import sys
from setuptools import setup, find_packages

__version__ = '1.0'

here = os.path.abspath(os.path.dirname(__file__))

requires = [
    'celery',
    'Chameleon',
    'circus',
    'colander',
    'configparser',
    'gunicorn',
    'heka-py',
    'konfig',
    'PyMySQL',
    'SQLAlchemy',
]

if sys.version_info < (2, 7):
    requires.append('argparse')
    requires.append('unittest2')

test_requires = requires + [
    'beautifulsoup4',
    'coverage',
    'nose',
    'unittest2',
    'Webtest',
]

with open(os.path.join(here, 'README.rst')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.rst')) as f:
    CHANGES = f.read()


setup(
    name='ichnaea',
    version=__version__,
    description='Mozilla Location Service - Ichnaea',
    long_description=README + '\n\n' + CHANGES,
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: Implementation :: CPython",
        "Framework :: Pyramid",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application"
    ],
    keywords="web services geo location",
    author='Mozilla Cloud Services',
    author_email='services-dev@mozilla.org',
    url='https://github.com/mozilla/ichnaea',
    license="Apache 2.0",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=requires,
    tests_require=test_requires,
    test_suite="ichnaea",
    extras_require={'test': test_requires},
    entry_points="""\
    [console_scripts]
    location_import = ichnaea.scripts.importer:console_entry
    location_initdb = ichnaea.scripts.initdb:console_entry
    location_map = ichnaea.scripts.map:console_entry
    """,
)
