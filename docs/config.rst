.. _config:

=========================
Application Configuration
=========================

As part of deploying the application, you need to create an application
configuration file, commonly called ``location.ini``.

As explained in the :ref:`the deployment documentation <deploy>` the
processes find this configuration file via the ``ICHNAEA_CFG``
environment variable. The variable should contain an absolute path,
for example ``/etc/location.ini``.

The configuration file is an ini-style file and contains a number of
different sections.

Required Sections
=================

Cache
-----

The cache section contains a ``cache_url`` pointing to a Redis server.

The cache is used as a classic cache by the webapp code, as a backend
to store rate-limiting counters, as a custom and a celery queuing backend.

.. code-block:: ini

    [cache]
    cache_url = redis://localhost:6379/0


Database
--------

The database section contains settings for accessing the MySQL database.

The web application only requires and uses the read-only connection,
while the asynchronous celery workers only use the read-write connection.

Both of them can be restricted to only DML (data-manipulation) permissions,
as neither needs DDL (data-definition) rights.

DDL changes are only done via the alembic database migration system,
which has a separate ``alembic.ini`` configuration file.

.. code-block:: ini

    [database]
    rw_url = mysql+pymysql://rw_user:password@localhost/location
    ro_url = mysql+pymysql://ro_user:password@localhost/location


GeoIP
-----

The geoip section contains settings related to the maxmind GeoIP database.

The ``db_path`` setting needs to point to a maxmind GeoIP city database
in version 2 format. Both GeoLite and commercial databases will work.

.. code-block:: ini

    [geoip]
    db_path = /path/to/GeoIP2-City.mmdb


Sentry
------

The sentry section contains settings related to a Sentry server.

The ``dsn`` setting needs to contain a valid DSN project entry.

.. code-block:: ini

    [sentry]
    dsn = https://public_key:secret_key@localhost/project_id


StatsD
------

The statsd section contains settings related to a StatsD service. The
project uses a lot of metrics as further detailed in
:ref:`the metrics documentation <metrics>`.

The ``host`` and ``port`` settings determine how to connect to the service
via UDP.

Since a single StatsD service usually supports multiple different projects,
the ``metric_prefix`` setting can be used to prefix all metrics emitted
by this project with a unique name.

The ``tag_support`` setting can either be ``false`` or ``true`` and declares
whether or not the StatsD service supports metric tags.
`Datadog <https://www.datadoghq.com/>`_ is an example of a service that
supports tags. If ``tag_support`` is false, the tags will be emitted as
part of the standard metric name.

.. code-block:: ini

    [statsd]
    host = localhost
    port = 8125
    metric_prefix = location
    tag_support = true


Optional Sections
=================

Assets
------

The assets section contains settings for a static file repository
(Amazon S3) and a public DNS to access those files via HTTPS
(Amazon CloudFront).

These are used to store and serve both the image tiles generated for
the data map and the public export files available via the downloads
section of the website.

.. code-block:: ini

    [assets]
    bucket = amazon_s3_bucket_name
    url = https://some_distribution_id.cloudfront.net


Import
------

The project supports importing cell data on a regular basis from the
:term:`OpenCellID` (OCID) project, using the
:ref:`cell import/export <import_export>` data format.

.. code-block:: ini

    [import:ocid]
    url = https://localhost:7001/downloads/
    apikey = some_key

The section name must be the exact string ``import:ocid``. Both a ``url``
and an ``apikey`` need to be configured for accessing an HTML overview
page listing the available download files using a specific file name pattern
for daily full and hourly differential files.

For the :term:`OpenCellID` service, the URL must end with a slash.


Web
---

The web section contains settings related to the non-API website content.

The web functionality by default is limited to the public HTTP API.
If the ``enabled`` setting is set to ``true`` the website content pages
are also made available.

The ``map_id_base`` and ``map_id_labels`` settings specify Mapbox map
ids for a base map and a map containing only labels. The ``map_token``
specifies a Mapbox access token.

.. code-block:: ini

    [web]
    enabled = true
    map_id_base = example_base.map-123
    map_id_labels = example_labels.map-234
    map_token = pk.example_public_access_token
