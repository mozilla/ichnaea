from codecs import open
import os
import os.path

from setuptools import find_packages, setup

here = os.path.relpath(os.path.abspath(os.path.dirname(__file__)))

with open(os.path.join(here, 'README.rst'), encoding='utf-8') as fd:
    long_description = fd.read()

__version__ = '2.2.1'

setup(
    name='ichnaea',
    version=__version__,
    description='Mozilla Location Service - Ichnaea',
    long_description=long_description,
    url='https://github.com/mozilla/ichnaea',
    author='Mozilla',
    license="Apache 2.0",
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: Implementation :: CPython",
        "Framework :: Pyramid",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application"
    ],
    keywords="web services geo location",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'console_scripts': [
            'location_dump=ichnaea.scripts.dump:console_entry',
            'location_map=ichnaea.scripts.datamap:console_entry',
            'location_region_json=ichnaea.scripts.region_json:console_entry',
        ],
    },
)
