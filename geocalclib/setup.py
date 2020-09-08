from setuptools import (
    Extension,
    find_packages,
    setup,
)

import numpy

numpy_include = numpy.get_include()
ext_modules = [
    Extension(
        name="geocalc",
        sources=["geocalc.c"],
        include_dirs=[numpy_include],
    ),
]

setup(
    name="geocalc",
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
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
    ],
    packages=find_packages(),
    include_package_data=True,
    ext_modules=ext_modules,
    zip_safe=False,
)
