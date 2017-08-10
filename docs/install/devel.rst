.. _devel:

===========
Development
===========

.. note:: If you want to install a production version of the code,
          please skip these instructions and follow
          :ref:`the deployment docs <deploy>` instead.

Prerequisites
-------------

In order to install a development version of the service, you need to
have a Linux or Mac OS machine and
`install docker <https://docs.docker.com/installation/>`_ and
docker-compose.

On Linux you can use your OS level package manager to install them.

On Mac OS you need to install
`Docker for Mac <https://docs.docker.com/docker-for-mac/>`_.
Docker Toolbox or docker-machine based setups aren't supported.


Docker
------

We use docker to run the main application and additional development
dependencies like Redis and MySQL with the exact versions we want to
test against.

We assume that you can run ``docker`` and ``docker-compose`` on
your command line. Test this via:

.. code-block:: bash

    docker --version
    docker-compose --version


Code
----

Now run the following command to get the code:

.. code-block:: bash

    git clone https://github.com/mozilla/ichnaea
    cd ichnaea
    git submodule update --init --recursive

For a development environment, you need to use the ``./dev`` helper
script to download and create all the required docker containers.
As a first command you can use:

.. code-block:: bash

    ./dev test

The first time around it'll take a good while. This will also start
a container running MySQL and one running Redis.

Please note that running the tests will wipe the database and Redis
instance it is connected to. DO NOT USE the dev helper script for
a production install.

Next up, you can run the entire application, with its three different
application containers:

.. code-block:: bash

    ./dev start

This will start a web, worker and scheduler container.

It will also expose port 8000 of the web container on localhost, so
you can interact with the web site directly, without having to use the
IP address of the web container.

The dev script provides a couple more commands, to control and
interact with the containers.

There are start/stop/restart commands to interact with all containers.
Each of these commands also takes a second argument of either
scheduler, services, web or worker. This allows you to start and stop
only a specific type of container.

The dev script also reacts to a `PULL` environment variable, which
allows you to skip pulling for new docker images during each invocation.
Prefix the command with `PULL=0`, for example:

.. code-block:: bash

    PULL=0 ./dev start

To interact and inspect the application image, there is one more helper
command:

.. code-block:: bash

    ./dev shell

This will drop you into a bash shell inside a container based on the
application image.


Unit Tests
----------

.. note:: The tests clear out the databae and Redis on each test run,
          so don't run these against a production instance or you will
          loose all your data.

If you have a local development environment, you can run all tests
including coverage tests via:

.. code-block:: bash

    ./dev test

Or run individual test modules via for example:

.. code-block:: bash

    ./dev test TESTS=ichnaea.tests.test_geoip

.. note:: Since the tests use a real database and Redis connection,
          you cannot parallelize any tests.


Documentation
-------------

In order to create and test the documentation locally run:

.. code-block:: bash

    ./dev docs

This will create an application container with a volume mount to the
local ``docs/build/html`` directory and update the documentation so
it is available in that local directory.

To view the documentation open ``file://docs/build/html/index.html``
with a web brower.


CSS / JS / Images
-----------------

The project depends on a number of external web assets. Those dependencies
are tracked via npm in files under `docker/node`.

In order to install them, run:

.. code-block:: bash

    ./dev css
    ./dev js

This will install build tools and assets inside a docker container.
It will also copy, compile and minify files in various folders under
`ichnaea/content/static/`.


Database migrations
-------------------

The codebase uses a library called
`alembic <http://alembic.zzzcomputing.com/en/latest/>`_
to faciliate database migrations.

To create a new database migration step, start an application container
with an open shell:

.. code-block:: bash

    ./dev shell

Create a new file via:

.. code-block:: bash

    bin/alembic revision -m 'Drop OCID tables'

Use a short description for the `-m` argument, as it will become part of the
generated file name. The output of the above command should be something
like:

.. code-block:: bash

    Generating /app/ichnaea/alembic/versions/138cb0d71dfb_drop_ocid_tables.py ... done

Copy the generated file out of the running container and into the codebase.
While the container is still running, open a seperate terminal on your
host machine and call:

.. code-block:: bash

    docker cp location_shell:/app/ichnaea/alembic/versions/138cb0d71dfb_drop_ocid_tables.py \
        ichnaea/alembic/versions/

Afterwards you can exit the container. Don't forget to `git add` the new file.


Python Dependencies
-------------------

The project uses `requires.io <https://requires.io/github/mozilla/ichnaea/requirements/?branch=master>`_
to track whether or not the Python dependencies are outdated.

If they are, update the version pins in the various `requirements/*.txt`
files and rerun `./dev test` and `./dev docs`.
