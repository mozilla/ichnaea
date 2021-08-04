.. _localdev:

*******************************
 Local development environment
*******************************

This chapter covers getting started with Ichnaea using Docker for a local
development environment.

.. contents::


.. _localdev-quickstart:

Setup Quickstart
================

1. Install required software: Docker, docker-compose (1.10+), make, and git.

   **Linux**:

      Use your package manager.

   **macOS**:

      Install `Docker for Mac <https://docs.docker.com/docker-for-mac/>`_ which
      will install Docker and docker-compose.

      Use `homebrew <https://brew.sh>`_ to install make and git::

         $ brew install make git

   **Other**:

      Install `Docker <https://docs.docker.com/engine/installation/>`_.

      Install `docker-compose <https://docs.docker.com/compose/install/>`_. You need
      1.10 or higher.

      Install `make <https://www.gnu.org/software/make/>`_.

      Install `git <https://git-scm.com/>`_.

2. Clone the repository so you have a copy on your host machine.

   Instructions for cloning are `on the Ichnaea page in GitHub
   <https://github.com/mozilla/ichnaea>`_.

3. Set environment options.

   To create the environment options file ``my.env`` ::

       $ make my.env

   If you're on **Linux**, you will need to set the UID/GID of the app user that
   runs in the Docker containers to match your UID/GID.  Run ``id`` to get your
   UID/GID. Edit ``my.env`` and set the ``ICHNAEA_UID`` and ``ICHNAEA_GID``
   variables. These will get used when creating the app user in the base image.

   If you are using **macOS** on a computer with Apple Silicon (such as M1 Macs
   released in 2020 or later), you'll need to select a different database engine,
   since Docker images are not available for the arm64 platform. Edit ``my.env``
   and set ``ICHNAEA_DOCKER_DB_ENGINE`` to ``mariadb_10_5``. This will be used
   when creating and running the database.

   If you ever want different values, change them in ``my.env`` and re-run
   the setup steps below (``make setup``, ``make runservices``, etc.).

4. Build Docker images for Ichnaea services.

   From the root of this repository, run::

       $ make build

   That will build the app Docker image required for development.

5. Initialize Redis and MySQL.

   Then you need to set up services. To do that, run::

       $ make runservices

   This starts service containers. Then run::

       # docker-compose ps

   If the state of the database container is ``Up (health: starting)``, wait a
   minute and try ``docker-compose ps``.  When the state is ``Up (healthy)``,
   then the database is initialized and ready for connections.

   If the state is just ``Up``, then the container doesn't provide health
   checks. Wait a couple of minutes before trying the next step.

   Then run::

       $ make setup

   This creates the MySQL database and sets up tables and things.

   You can run ``make setup`` any time you want to wipe any data and start
   fresh.


At this point, you should have a basic functional Ichnaea development
environment that has no geo data in it.

To see what else you can do, run::

        $ make

.. _localdev-updating:

Updating the Dev Environment
============================

Updating code
-------------

Any time you want to update the code in the repostory, run something like this from
the main branch::

    $ git pull

The actual command depends on what you're working on and the state of your copy of
the repository.

After you have the latest code, you'll need to update other things.

If there were changes to the requirements files or setup scripts, you'll need to
build new images::

    $ make build

If there were changes to the database tables, you'll need to wipe the MySQL
database and Redis::

    $ make setup


.. _localdev-configuration:

Specifying configuration
========================

Configuration is pulled from these sources:

1. The ``my.env`` file.
2. ENV files located in ``/app/docker/config/``. See ``docker-compose.yml`` for
   which ENV files are used in which containers, and their precedence.
3. Configuration defaults defined in the code.

The sources above are ordered by precedence, i.e. configuration values defined
in the ``my.env`` file will override values in the ENV files or defaults.

The following ENV files can be found in ``/app/docker/config/``:

``local_dev.env``
   This holds *secrets* and *environment-specific configuration* required
   to get services to work in a Docker-based local development environment.

   This should **NOT** be used for server environments, but you could base
   configuration for a server environment on this file.

``test.env``
   This holds configuration specific to running the tests. It has some
   configuration value overrides because the tests are "interesting".

``my.env``
   This file lets you override any environment variables set in other ENV files
   as well as set variables that are specific to your instance.

   It is your personal file for your specific development environment--it
   doesn't get checked into version control.

   The template for this is in ``docker/config/my.env.dist``.

In this way:

1. environmental configuration which covers secrets, hosts, ports, and
   infrastructure-specific things can be set up for every environment

2. behavioral configuration which covers how the code behaves and which classes
   it uses is versioned alongside the code making it easy to deploy and revert
   behavioral changes with the code depending on them

3. ``my.env`` lets you set configuration specific to your development
   environment as well as override any configuration and is not checked into
   version control


.. seealso::

   See :ref:`config` for configuration settings.


Setting configuration specific to your local dev environment
------------------------------------------------------------

There are some variables you need to set that are specific to your local dev
environment. Put them in ``my.env``.


Overriding configuration
------------------------

If you want to override configuration temporarily for your local development
environment, put it in ``my.env``.


.. _localdev-alembic:

Alembic and Database Migrations
===============================

Ichnaea uses Alembic.

To create a new database migration, do this::

    $ make shell
    app@blahblahblah:/app$ alembic revision -m "SHORT DESCRIPTION"

Then you can edit the file.


.. _localdev-staticassets:

Building Static Assets (CSS/JS)
===============================

To build changed assets::

    $ make assets

To rebuild asset files from scratch::

    $ make clean-assets assets

To recreate the node container, applying changes in ``package.json``::

    $ make build clean-assets assets

.. _localdev-testing:

Running Tests
=============

You can run the test suite like this::

    $ make test


If you want to pass different arguments to pytest or specify specific
tests to run, open up a test shell first::

    $ make testshell
    app@blahblahblah:/app$ pytest [ARGS]


.. _localdev-docs:

Building Docs
=============

You can build the docs like this::

    $ make docs

This will create an application container with a volume mount to the
local ``docs/build/html`` directory and update the documentation so
it is available in that local directory.

To view the documentation open ``file://docs/build/html/index.html``
with a web brower.

Updating Test GeoIP Data and Libraries
======================================
The development environment uses a test MaxMind GeoIP database, and the Ichnaea
test suite will fail if this is more than 1000 days old. To update this
database and confirm tests pass, run::

    $ make update-vendored test

Commit the refreshed files.

This command can also be used to updated ``libmaxmindb`` and the ``datamaps``
source. Update ``docker.make`` for the desired versions, and run::

    $ make update-vendored build test

Commit the updated source tarballs.

Building Datamap Tiles
======================

To build datamap tiles for the local development environment, run::

    $ make local-map

If you have data in the ``datamap`` tables, this will create many files
under ``ichnaea/content/static/datamap``. This uses
``ichnaea/scripts/datamap.py``, which can also be run directly.

To see the map locally, you will need to configure :ref:`mapbox`. A free
developer account should be sufficient.

To use an S3 bucket for tiles, you'll need to set ``ASSET_BUCKET`` and
``ASSET_URL`` (see :ref:`map_tile_and_download_assets`).
To upload tiles to an S3 bucket, you'll also need AWS credentials that
can read, write, and delete objects in the ``ASSET_BUCKET``. Here are
two ways, neither of which is ideal since it adds your AWS credentials
in plain text:

1. Add credentials as environment variables ``AWS_ACCESS_KEY_ID`` and
   ``AWS_SECRET_ACCESS_KEY`` in ``my.env``.
2. Add credentials to a file ``my.awscreds`` in the project folder,
   and add ``AWS_SHARED_CREDENTIALS_FILE=/app/my.awscreds`` to ``my.env``.

You can then generate and upload tiles with::

    $ docker-compose run --rm app map

This will generate a fresh set of tiles in a temporary directory and
sync the S3 bucket with the changes.

Running Tasks
=============

To run worker tasks in the development environment, run::

    $ make runcelery

This will run the ``scheduler``, which will schedule periodic tasks, as well as the
``worker``, which runs the tasks. If you see this error::

    scheduler_1  | ERROR: Pidfile (/var/run/location/celerybeat.pid) already exists.

then stop the ``make runcelery`` process (Ctrl-C) and re-create the ``scheduler``::

    $ docker rm -f scheduler
    $ make runcelery

To manually run a task, call it from a shell::

    $ make shell
    $ celery -A ichnaea.taskapp.app:celery_app call ichnaea.data.tasks.update_statregion

This will add the task ``update_statregion`` to the Redis queue. The ``worker`` task
will read the queue and execute it.

The commands will also run if you start a shell with ``make testshell``, but the task
will not execute. A different Redis URI is setup for the test environment, and
the worker running with ``make runcelery`` will not read that Redis queue, and will
not see the request.

There are other commands available, such as this one to display registered tasks::

    $ celery -A ichnaea.taskapp.app:celery_app inspect registered
