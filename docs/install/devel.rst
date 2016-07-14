.. _devel:

===========
Development
===========

Prerequisites
-------------

In order to install a development version of the service, you need to
have a Linux or Mac OS machine and
`install docker <https://docs.docker.com/installation/>`_ and
docker-compose.

On Linux you can use your OS level package manager to install them.

On Mac OS you need to install
`Docker for Mac <https://docs.docker.com/docker-for-mac/>`_.
Docker Toolbox or docker-machine based setups aren't supported
by the documentation and Makefile.


Docker
------

We use docker to run additional development dependencies like
Redis and MySQL with the exact versions we want to test against.

We assume that you can run ``docker`` and ``docker-compose`` on
your command line. Test this via:

.. code-block:: bash

    docker --version
    docker-compose --version


Requirements
------------

In order to run the code you need to have Python 2.6, 2.7 or 3.5 installed
on your system. The default Makefile also assumes a `virtualenv`
command is globally available. If this isn't true for your system,
please create a virtualenv manually inside the ichnaea folder before
continuing (``/path/to/virtualenv --python=python2.6 .``).

In the next step you are going to install a good number of Python libraries,
which depend on various OS level C libraries. These C libraries are best
installed via the OS level package management system. We list the
CentOS/Redhat names, but they should be similar on other OS.

Runtime requirements:

.. code-block:: bash

    openssl, python, libmaxminddb, libffi, atlas-sse3, geos, spatialindex-devel

Build requirements:

.. code-block:: bash

    openssl-devel, gcc, gcc-c++, gcc-gfortran, make, python, python-pip,
    python-virtualenv, git, libmaxminddb, libffi-devel, atlas-devel,
    geos-devel, spatialindex-devel


Code
----

Now run the following command to get the code:

.. code-block:: bash

    git clone https://github.com/mozilla/ichnaea
    cd ichnaea

Then run make, which is going to take quite a while the first time:

.. code-block:: bash

    make

Now you can run the web app for example on port 7001:

.. code-block:: bash

    ICHNAEA_CFG=location.ini bin/gunicorn -b 127.0.0.1:7001 \
        -c python:ichnaea.webapp.settings ichnaea.webapp.app:wsgi_app

The celery processes are started via:

.. code-block:: bash

    ICHNAEA_CFG=location.ini bin/celery -A ichnaea.async.app:celery_app beat

    ICHNAEA_CFG=location.ini bin/celery -A ichnaea.async.app:celery_app worker \
        -Ofair --no-execv --without-mingle --without-gossip


Documentation
-------------

In order to create and test the documentation locally run:

.. code-block:: bash

    make docs

The documentation will be available in ``docs/build/html/index.html``.


Python Dependencies
-------------------

The project uses `requires.io <https://requires.io/github/mozilla/ichnaea/requirements/?branch=master>`_ 
to track whether or not the Python dependencies are outdated.

If they are, update the version pins in the various `requirements/*.txt`
files and rerun `make`, `make docs` or `make test`, depending on which
requirements have changed.


CSS / JS / Images
-----------------

The project depends on a number of external web assets. Those dependencies
are tracked via npm and bower in files under `docker/node`.

In order to install them, run:

.. code-block:: bash

    make css
    make js

This will install build tools and bower assets inside a docker container.
It will also copy, compile and minify files in various folders under
`ichnaea/content/static/`.

To check if the external assets are outdated run:

.. code-block:: bash

    docker run --rm -it mozilla-ichnaea/node:latest bower list


Cleanup
-------

In case the local environment gets into a weird or broken state, it can
be cleaned up by running:

.. code-block:: bash

    make clean

Of course one can also delete the entire git repository and start from
a fresh checkout.


Release Build
-------------

The default `make` / `make build` target installs a local development
version including database setup and testing tools. For a production
environment or release pipeline one can instead use:

.. code-block:: bash

    make release

This will not do any database setup and only install production
dependencies. It will also create a virtualenv and install the ichnaea
code itself via `bin/python setup.py install`, so that a copy will be
installed into `lib/pythonX.Y/site-packages/`.

The step will also compile all py files to pyc files and remove any files
from the tree which aren't compatible with the active Python version
(blocklist in the `compile.py` script). The removal step ensures that
any build tools (for example rpmbuild / mock) that typically call
`compileall.compile_dir` will work, without breaking on the incompatible
files.
