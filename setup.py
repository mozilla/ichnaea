from codecs import open
import os
import os.path

import numpy

from setuptools import (
    Extension,
    find_packages,
    setup,
)

here = os.path.relpath(os.path.abspath(os.path.dirname(__file__)))

with open(os.path.join(here, 'README.rst'), encoding='utf-8') as fd:
    long_description = fd.read()

__version__ = '1.5.1'

numpy_include = numpy.get_include()
ext_modules = [
    Extension(
        name='ichnaea.geocalc',
        sources=['ichnaea/geocalc.c'],
        include_dirs=[numpy_include],
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
            'location_dump=ichnaea.scripts.dump:console_entry',
            'location_map=ichnaea.scripts.datamap:console_entry',
            'location_region_json=ichnaea.scripts.region_json:console_entry',
        ],
    },
)
