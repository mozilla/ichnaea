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


Cache
-----

The cache section contains a ``cache_url`` pointing to a Redis server.

The cache is used as a classic cache by the webapp code, as a backend
to store rate-limiting counters and as a custom queuing backend.

.. code-block:: ini

    [cache]
    cache_url = redis://localhost:6379/0


Celery
------

The celery section contains connection settings for the Celery asynchronous
task system.

.. code-block:: ini

    [celery]
    broker_url = redis://localhost:6379/0
    result_url = redis://localhost:6379/0


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


Export
------

The project supports exporting all data that its gets via the submit-style
APIs to different backends.

Currently three different kinds of backends are supported:

* Amazon S3 buckets
* The projects own internal data processing pipeline
* A HTTPS POST endpoint accepting the geosubmit v2 format

The type of target is determined by the URL prefix of each section.
The section name must start with ``export:`` but the name postfix can
be anything.

All export targets can be configured with a ``batch`` setting that determines
how many reports have to be available before data is submitted to the
backend. Data is buffered in the Redis cache configured in the cache section.

All exports take an additional ``skip_keys`` setting as a whitespace
separated list of API keys. Data submitted using one of these API keys
will not be exported to the target.

There can be multiple instances of the bucket and HTTP POST export targets,
but only one instance of the internal export.

Bucket Export
+++++++++++++

The Amazon S3 bucket export combines reports into a gzipped JSON file
and uploads them to the specified bucket ``url``.

.. code-block:: ini

    [export:backup]
    url = s3://amazon_s3_bucket_name/directory/{api_key}/{year}/{month}/{day}
    skip_keys = test
    batch = 10000

The url can contain any level of additional static directories under the
bucket root. The ``{api_key}/{year}/{month}/{day}`` parts will be dynamically
replaced by the `api_key` used to upload the data, and the date when the
backup took place. The files use a random UUID4 as the filename.

An example filename might be::

    /directory/test/2015/07/15/554d8d3c-5b28-48bb-9aa8-196543235cf2.json.gz


Internal Export
+++++++++++++++

The internal export forwards the incoming data into the internal data
pipeline. The url must be the exact string ``internal://``.

.. code-block:: ini

    [export:internal]
    url = internal://
    batch = 1000


HTTPS Export
++++++++++++

The HTTPS export buffers incoming data into batches of ``batch`` size
and then submits them using the :ref:`api_geosubmit_latest` API to the
specified ``url`` endpoint.

.. code-block:: ini

    [export:test]
    url = https://localhost/some/api/url?key=export
    skip_keys = test
    batch = 1000

If the project is taking in data from a partner in a data exchange,
the ``skip_keys`` setting can be used to prevent data being roundtripped
and send back to the same partner that it came from.


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
