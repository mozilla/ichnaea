.. _deploy:

==========
Deployment
==========

Mozilla deploys Ichnaea in an Amazon AWS environment, and there are some
optional dependencies on specific AWS services like Amazon S3. The
documentation assumes you are also using a AWS environment, but Ichnaea can be
run in non-AWS environments as well.

Mozilla's Production Deployment
===============================

Mozilla's deployment of Ichnaea looks something like this:

.. Source document:
.. https://docs.google.com/drawings/d/1v0Db941NtZQoaKYETHXNYMK9MvZx7FlIw5QzQiiI2fI/edit?usp=sharing

.. image:: deploy.png
   :height: 417px
   :width: 921px
   :scale: 75%
   :align: center
   :alt: Deployment Diagram

The required parts are:

* One or more **WebApp workers** running the user-facing web page and APIs.
  Mozilla uses 20 EC2 instances in an Auto Scaling Group (ASG), behind an
  Elastic Load Balancer (ELB).
* One or more **Async workers** that run Celery tasks that process
  observations, update the station database, create map tiles, export data, and
  other tasks.  Mozilla uses 5 EC2 instances in an ASG.
* A **Celery scheduler** to schedule periodic tasks. Mozilla uses an EC2 instance.
* A **MySQL or compatible database**, to store station data. Mozilla uses Amazon's
  Relational Database Service (RDS), MySQL 5.7, in Multi-AZ mode. The
  user-facing website does not write to a database, and reads from a read-only
  replica.
* A **Redis cache server**, for cached data, Celery tasks queues, and observation
  data pipelines. Mozilla uses Amazon's ElastiCache Redis, in Multi-AZ mode.

The optional parts are:

* An **S3 asset bucket** to store map tiles and public data like cell exports.
  Mozilla uses Cloudfront as a CDN in front of the asset bucket.
* An **S3 backup bucket** to store observation samples.
* An **Admin node**, to provide interactive access to the cluster and to run
  database migration. Mozilla uses an EC2 instance.
* **DNS entries** to publish on the Internet. Mozilla uses AWS's Route 53.

Optional parts not shown on the diagram:

* A **statsd-compatible metrics server**. Mozilla uses InfluxDB.
* A **log aggregator**. Mozilla uses Google Cloud Logging.
* **Sentry**, for aggregating captured exceptions.

MySQL / Amazon RDS
==================

The application is written and tested against MySQL 5.7.x or Amazon RDS
of the same versions. MariaDB 10.5 has also been tested in the development
environment.

The default configuration works for the most part, but ensure you are using
UTF-8 to store strings. For example in ``my.cnf``:

.. code-block:: ini

    [mysqld]
    character-set-server = utf8
    collation-server = utf8_general_ci
    init-connect='SET NAMES utf8'

The WebApp frontend role only needs access to a read-only version of the
database, for example a read-replica. The Async Worker backend role needs
access to the read-write primary database.

You need to create a database called ``location`` and a user with DDL
privileges for that database.

Mozilla's MLS deployment processes 500 million to 1,000 million observations
a day. We have had issues in the past with replica lag and transaction log
sizes (used disk space), and both should be monitored. We reduced replica lag
to 2 seconds or less by increasing ``innodb_log_file_size`` from 125 MB to
2 GB.  See :doc:`/rate_control` for more information.

Redis / Amazon ElastiCache
==========================

The application uses Redis:

* As the Celery backend and broker for the Async backend workers,
* As queues for observation data,
* As an API key cache
* As storage for API key rate limits and usage

You can install a standard Redis or use Amazon ElastiCache (Redis).
The application is tested against Redis 3.2.


Amazon S3
=========

The application uses Amazon S3 for various tasks, including backup of
:term:`observations`, export of the aggregated cell table and hosting of
the data map image tiles.

All of these are triggered by asynchronous jobs and you can disable them
if you are not hosted in an AWS environment.

If you use Amazon S3 you might want to configure a lifecycle policy to
delete old export files after a couple of days and :term:`observation`
data after one year.


Statsd / Sentry
===============

The application uses Statsd to aggregate metrics and Sentry to log
exception messages.

To use Statsd and Sentry, you need to configure them via environment
variables as detailed in :ref:`the config section <config>`.

Installation of Statsd and Sentry are outside the scope of this documentation.


Logging
=======
The application logs to ``stdout`` by default. The WebApp logs using the
`MozLog format <https://wiki.mozilla.org/Firefox/Services/Logging>`_,
while the Async workers have more traditional logs. If you want to view logs
across a deployment, a logging aggregation system is needed. This is outside
the scope of this documentation.


Image Tiles
===========

The code includes functionality to render out image tiles for a data map
of places where observations have been made. These can be stored in an S3
bucket, allowing them to be viewed on the website.

You can trigger this functionality periodically via a cron job, by
calling the application container with the ``map`` argument.


Docker Config
=============

The :ref:`development section <localdev>` describes how to set up an
environment used for working on and developing Ichnaea itself. For a
production install, you should use pre-packaged docker images, instead
of installing and setting up the code from Git.

Docker images are published to https://hub.docker.com/r/mozilla/location.
When the ``main`` branch is updated (such as when a pull request is merged),
an image is uploaded with a label matching the commit hash, as well as the
``latest`` tag. This is deployed to the
`stage deployment <https://location.stage.mozaws.net/>`_, and the deployed
commit can be viewed at
`/__version__ on stage <https://location.stage.mozaws.net/__version__>`_.
When it is ready for production, it is tagged with the date, such as
``2021.08.16``, and is deployed to
`production <https://location.services.mozilla.com/>`_. The deployed tag and
commit can be viewed at
`/__version__ on prod <https://location.services.mozilla.com/__version__>`_,
and the available tags at
https://github.com/mozilla/ichnaea/tags.

Pull the desired docker image:

.. code-block:: bash

    docker pull mozilla/location:2021.11.23

To test if the image was downloaded successfully, you can create a
container and open a shell inside of it:

.. code-block:: bash

    docker run -it --rm mozilla/location:2021.11.23 shell

Close the container again, either via ``exit`` or ``Ctrl-D``.

Next create the application config as a docker environment file,
for example called `env.txt`:

.. code-block:: ini

    DB_READONLY_URI=mysql+pymysql://USER:PASSWORD@HOSTNAME:3306/location
    DB_READWRITE_URI=mysql+pymysql://USER:PASSWORD@HOSTNAME:3306/location
    SQLALCHEMY_URL=mysql+pymysql://USER:PASSWORD@HOSTNAME:3306/location
    GEOIP_PATH=/mnt/geoip/GeoLite2-City.mmdb
    REDIS_URI=redis://HOST:PORT/0
    SECRET_KEY=change_this_value_or_it_will_not_be_secret

You can use either a single database user with DDL/DML privileges, or
separate users for DDL (``SQLALCHEMY_URL``), read-write (``DB_READWRITE_URI``),
and read-only (``DB_READONLY_URI``) privileges.

See :ref:`environment-variables` for additional options.


.. _database-setup:

Database Setup
==============

The user with DDL privileges and a database called ``location`` need to
be created manually. If multiple users are used, the initial database
setup will create the read-only / read-write users. Something like this
should work in a ``mysql`` shell:

.. code-block:: sql

    CREATE DATABASE location;

    CREATE USER 'read'@'%' IDENTIFIED BY 'read-password';
    GRANT SELECT ON location.* TO 'read'@'%';

    CREATE USER 'write'@'%' IDENTIFIED BY 'write-password';
    GRANT SELECT, INSERT, UPDATE, DELETE ON location.* TO 'write'@'%';

    CREATE USER 'admin'@'%' IDENTIFIED BY 'admin-password';
    GRANT ALL PRIVILEGES ON * TO 'admin'@'%';

    quit

These usernames and passwords need to match the database connection URLs in the
``env.txt`` file.  Next up, run the initial database setup:

.. code-block:: bash

    docker run -it --rm --env-file env.txt \
        mozilla/location:2021.11.23 shell alembic stamp base

And update the database schema to the latest version:

.. code-block:: bash

    docker run -it --rm --env-file env.txt \
        mozilla/location:2021.11.23 shell alembic upgrade head

The last command needs to be run whenever you upgrade to a new version
of Ichnaea. You can inspect available database schema changes via
alembic with the ``history`` and ``current`` sub-commands.

An API key will be needed to use the service, and a testing one can
be created now that the database is available. This can be used to
create one called ``test``:

.. code-block:: bash

    docker run -it --rm --env-file env.txt \
        mozilla/location:2021.11.23 shell /app/ichnaea/scripts/apikey.py create test


GeoIP
=====

The application uses a Maxmind GeoIP City database for various tasks.
It works both with the commerically available and Open-Source GeoLite
databases in binary format.

You can download the
`GeoLite database <https://dev.maxmind.com/geoip/geoip2/geolite2/>`_ 
for free from MaxMind after
`signing up for a GeoLite2 account <https://www.maxmind.com/en/geolite2/signup>`_.

Download and untar the downloaded file. Put the ``GeoLite2-City.mmdb``
into a directory accessible to docker (for example ``/opt/geoip``).
The directory or file can be
`mounted <https://docs.docker.com/storage/bind-mounts/>`_
into the running docker containers.

You can update this file on a regular basis. Typically once a month
is enough for the GeoLite database. Make sure to stop any containers
accessing the file before updating it and start them again afterwards.
The application code doesn't tolerate having the file being changed
underneath it.

Docker Runtime
==============

Finally you are ready to start containers for the three different
application roles.

There is a web frontend, a task worker and a task scheduler role.
The scheduler role is limited to a single running container. You need
to make sure to never have two containers for the scheduler running at
the same time. If you use multiple physical machines, the scheduler
must only run on one of them.

The web app and task worker roles both scale out and you can run
as many of them as you want. You can tune the web instance with the variables
``GUNICORN_WORKERS`` and similar variables - see
`docker/run_web.sh <https://github.com/mozilla/ichnaea/blob/main/docker/run_web.sh>`_
for details. You can run a single docker container per physical/virtual
machine, or multiple with a system like Kubernetes.

All roles communicate via the database and Redis only, so can be run
on different virtual or physical machines. The task workers load
balance their work internally via data structures in Redis.

If you run multiple web frontend roles, you need to put a load balancer
in front of them. The application does not use any sessions or cookies,
so the load balancer can simply route traffic via round-robin.

You can configure the load balancer to use the ``/__lbheartbeat__`` HTTP
endpoint to check for application health.

If you want to use docker as your daemon manager run:

.. code-block:: bash

    docker run -d --env-file env.txt \
        --volume /opt/geoip:/mnt/geoip
        mozilla/location:2021.11.23 scheduler

The ``/opt/geoip`` directory is the directory on the docker host, with
the ``GeoLite2-City.mmdb`` file inside it. The ``/mnt/geoip/`` directory
corresponds to the ``GEOIP_PATH`` config section in the ``env.txt`` file.

The two other roles are started in the same way:

.. code-block:: bash

    docker run -d --env-file env.txt \
        --volume /opt/geoip:/mnt/geoip
        mozilla/location:2021.11.23 worker

    docker run -d --env-file env.txt \
        --volume /opt/geoip:/mnt/geoip
        -p 8000:8000/tcp
        mozilla/location:2021.11.23 web

The web role can take an additional argument to map the port 8000 from
inside the container to port 8000 of the docker host machine.

You can put a web server (e.g. Nginx) in front of the web role and
proxy pass traffic to the docker container running the web frontend.


Runtime Checks
==============

To check whether or not the application is running, you can check the
web role, via:

.. code-block:: bash

    curl -i http://localhost:8000/__heartbeat__

This should produce output like::

    HTTP/1.1 200 OK
    Content-Length: 196
    Content-Type: application/json
    Date: Mon, 10 Jan 2022 22:15:05 GMT
    Server: waitress
    Strict-Transport-Security: max-age=31536000; includeSubDomains
    X-Content-Type-Options: nosniff

    {"database": {"up": true, "time": 15, "alembic_version": "3be4004781bc"},
     "geoip": {"up": true, "time": 0, "age_in_days": 553, "version": "2020-07-06T20:03:26Z"},
     "redis": {"up": true, "time": 0}}⏎ 

The ``__lbheartbeat__`` endpoint has simpler output and doesn't check
the database / Redis backend connections. The application is designed
to degrade gracefully and continue to work with limited capabilities
without working database and Redis backends.

The ``__version__`` endpoint shows what version of the software is
currently running.

To test one of the HTTP API endpoints, you can use:

.. code-block:: bash

    curl -H "X-Forwarded-For: 81.2.69.192" \
        http://localhost:8000/v1/geolocate?key=test

Change the command if you used a name other that ``test`` for a first
API key in the :ref:`database-setup`.

This should produce output like::

    {"location": {"lat": 51.5142, "lng": -0.0931}

Test this with different IP addresses like ``8.8.8.8`` to make sure
the database file was picked up correctly.


Upgrade
=======

In order to upgrade a running installation of Ichnaea to a new version,
first check and get the docker image for the new version, for example:

.. code-block:: bash

    docker pull mozilla/location:2021-11-23

Next up stop all containers running the scheduler and task worker roles.
If you use docker's own daemon support, the ``ps``, ``stop`` and ``rm``
commands can be used to accomplish this.

Now run the database migrations found in the new image:

.. code-block:: bash

    docker run -it --rm --env-file env.txt \
        mozilla/location:2.2.0 alembic upgrade head

The web app role can work with both the old database and new database
schemas. The worker role might require the new database schema right
away.

Start containers for the scheduler, worker and web roles based on the
new image.

Depending on how you run your web tier, swich over the traffic from
the old web containers to the new ones. Once all traffic is going to
the new web containers, stop the old web containers.
