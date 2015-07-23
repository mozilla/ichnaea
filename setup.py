import os
from setuptools import setup, find_packages

__version__ = '1.3'

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'README.rst')) as f:
    README = f.read()


setup(
    name='ichnaea',
    version=__version__,
    description='Mozilla Location Service - Ichnaea',
    long_description=README,
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
    author='Mozilla',
    author_email='dev-geolocation@lists.mozilla.org',
    url='https://github.com/mozilla/ichnaea',
    license="Apache 2.0",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    entry_points="""\
    [console_scripts]
    location_initdb = ichnaea.scripts.initdb:console_entry
    location_map = ichnaea.scripts.map:console_entry
    """,
)
