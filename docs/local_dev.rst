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

   **OSX**:

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

   Ichnaea publishes documentation at `<https://mozilla.github.io/ichnaea>`_
   which is a git submodule in the repository.

   After you clone the repository, you need to do this in the repository
   directory::

       $ git submodule update --init --recursive

3. (*Optional/Advanced*) Set UID and GID for Docker container user.

   If you're on Linux or you want to set the UID/GID of the app user that
   runs in the Docker containers, run::

       $ make my.env

   Then edit the file and set the ``ICHNAEA_UID`` and ``ICHNAEA_GID``
   variables. These will get used when creating the app user in the base
   image.

   If you ever want different values, change them in ``my.env`` and re-run
   ``make build``.

4. Build Docker images for Ichnaea services.

   From the root of this repository, run::

       $ make build

   That will build the app Docker image required for development.

5. Initialize Redis and MySQL.

   Then you need to set up services. To do that, run::

       $ make runservices

   This starts service containers. Then run::

       $ make setup

   This creates the MySQL database and sets up tables and things.

   You can run ``make setup`` any time you want to wipe any data and start
   fresh.


At this point, you should have a basic functional Ichnaea development
environment that has no geo data in it.


.. _localdev-updating:

Updating the Dev Environment
============================

Updating code
-------------

Any time you want to update the code in the repostory, run something like this from
the master branch::

    $ git pull


It depends on what you're working on and the state of things.

After you do that, you'll need to update other things.

If there were changes to the requirements files or setup scripts, you'll need to
build new images::

    $ make build


If there were changes to the database tables, you'll need to wipe the MySQL
database and Redis::

    $ make setup


.. _localdev-configuration:

Configuration
=============

Configuration is pulled from these sources:

1. The ``my.env`` file.
2. ENV files located in ``/app/docker/config/``. See ``docker-compose.yml`` for
   which ENV files are used in which containers, and their precedence.
3. Configuration defaults defined in the code.

The sources above are ordered by precedence, i.e. configuration values defined
in the ``my.env`` file will override values in the ENV files or defaults.

The following ENV files can be found in ``/app/docker/config/``:

``app.env``
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

To build CSS files::

    $ make buildcss


To build JS files::

    $ make buildjs


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
