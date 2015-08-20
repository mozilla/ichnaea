from codecs import open
import os.path

import numpy
from setuptools import (
    Extension,
    find_packages,
    setup,
)

here = os.path.abspath(os.path.dirname(__file__))
base = os.path.join(here, 'ichnaea')

with open(os.path.join(here, 'README.rst'), encoding='utf-8') as fd:
    long_description = fd.read()

__version__ = '1.3'

ext_modules = [
    Extension(
        name='ichnaea._geocalc',
        sources=[os.path.join(base, '_geocalc.c')],
        include_dirs=[numpy.get_include()],
    ),
]

setup(
    name='ichnaea',
    version=__version__,
    description='Mozilla Location Service - Ichnaea',
    long_description=long_description,
    url='https://github.com/mozilla/ichnaea',
    author='Mozilla',
    author_email='dev-geolocation@lists.mozilla.org',
    license="Apache 2.0",
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: Implementation :: CPython",
        "Framework :: Pyramid",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application"
    ],
    keywords="web services geo location",
    packages=find_packages(),
    include_package_data=True,
    ext_modules=ext_modules,
    zip_safe=False,
    entry_points={
        'console_scripts': [
            'location_initdb=ichnaea.scripts.initdb:console_entry',
            'location_map=ichnaea.scripts.map:console_entry',
        ],
    },
)
