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

Next you need to use the ``./server`` helper script to download and
create all the required docker containers. As a first command you
can use:

.. code-block:: bash

    ./server test

The first time around it'll take a good while. This will also start
a container running MySQL and one running Redis.

Next up, you can run the entire application, with its three different
application containers:

.. code-block:: bash

    ./server start

This will start a web, celery worker and celery scheduler container.
It will also expose port 8000 of the web container on localhost, so
you can interact with the web site directly, without having to use the
IP address of the web container.

The server script provides a couple more commands, to control and
interact with the containers.

There are start/stop/restart commands to interact with all containers.
Each of these commands also takes a second argument of either
scheduler, services, web or worker. This allows you to start and stop
only a specific type of container.

To interact and inspect the application image, there is one more helper
command:

.. code-block:: bash

    ./server shell

This will drop you into a bash shell inside a container based on the
application image.


Documentation
-------------

In order to create and test the documentation locally run:

.. code-block:: bash

    ./server docs

This will create an application container with a volume mount to the
local ``docs/build/html`` directory and update the documentation so
it is available in that local directory.

To view the documentation open ``file://docs/build/html/index.html``
with a web brower.


CSS / JS / Images
-----------------

The project depends on a number of external web assets. Those dependencies
are tracked via npm and bower in files under `docker/node`.

In order to install them, run:

.. code-block:: bash

    ./server css
    ./server js

This will install build tools and bower assets inside a docker container.
It will also copy, compile and minify files in various folders under
`ichnaea/content/static/`.

To check if the external assets are outdated run:

.. code-block:: bash

    ./server bower_list


Python Dependencies
-------------------

The project uses `requires.io <https://requires.io/github/mozilla/ichnaea/requirements/?branch=master>`_
to track whether or not the Python dependencies are outdated.

If they are, update the version pins in the various `requirements/*.txt`
files and rerun `./server test` and `./server docs`.
