.. _config:

=============
Configuration
=============

The application takes a number of different settings and reads them
from environment variables. There are also a small number of settings
inside database tables.


Environment Variables
=====================

Required Variables
------------------

Database
~~~~~~~~

The MySQL compatible database is used for storing configuration and
application data.

The web role only requires a read-only connection, while the
worker role need a read-write connection.

Both of them can be restricted to only DML (data-manipulation) permissions,
as neither needs DDL (data-definition) rights.

DDL changes are only done via the alembic database migration system.

.. code-block:: ini

    DB_HOST = localhost

    DB_RO_USER = location_ro
    DB_RO_PWD = password
    DB_RW_USER = location_rw
    DB_RW_PWD = password
    DB_DDL_USER = location_admin
    DB_DDL_PWD = password

The database name is `location` and the port number is the default `3306`.


GeoIP
~~~~~

The web and worker roles need access to a maxmind GeoIP City database
in version 2 format. Both GeoLite and commercial databases will work.

.. code-block:: ini

    GEOIP_PATH = /path/to/GeoIP2-City.mmdb


Redis
~~~~~

The Redis cache is used as a classic cache by the web role, as a backend
to store rate-limiting counters, as a custom and a worker queuing backend.

.. code-block:: ini

    REDIS_HOST = localhost

The port number is the default `6379`.


Optional Variables
------------------

Sentry
~~~~~~

All roles and command line scripts use an optional Sentry server
to log application exception data.

.. code-block:: ini

    SENTRY_DSN = https://public_key:secret_key@localhost/project_id


StatsD
~~~~~~

All roles and command line scripts use an optional StatsD service
to log application specific metrics. The StatsD service needs to
support metric tags.

The project uses a lot of metrics as further detailed in
:ref:`the metrics documentation <metrics>`.

.. code-block:: ini

    STATSD_HOST = localhost

The port number is the default `8125`. All metrics are prefixed with
a `location` namespace.


Feature Specfic Variables
-------------------------

Assets
~~~~~~

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


Web
~~~

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


Database Configuration
======================

API Keys
--------

The project requires API keys to access the locate APIs. You need to add
API keys manually to the database by direct SQL inserts.

API keys can be any string of up to 40 characters, though random UUID4s
in hex representation are commonly used, for example
``329694ac-a337-4856-af30-66162bc8187a``.

But to start off, you can add a simple literal `test` API key:

.. code-block:: sql

    INSERT INTO api_key
    (`valid_key`, `allow_locate`) VALUES ("test", 1);


Export Configuration
--------------------

The project supports exporting all data that its gets via the submit-style
APIs to different backends. This configuration lives in the `export_config`
database table.

Currently three different kinds of backends are supported:

* Amazon S3 buckets
* The projects own internal data processing pipeline
* A HTTPS POST endpoint accepting the geosubmit v2 format

The type of the target is determined by the `schema` column of each entry.

All export targets can be configured with a ``batch`` setting that
determines how many reports have to be available before data is
submitted to the backend.

All exports have an additional ``skip_keys`` setting as a set of
API keys. Data submitted using one of these API keys will not be
exported to the target.

There can be multiple instances of the bucket and HTTP POST export
targets, but only one instance of the internal export.

In the simplest case, you insert one row to send data to the internal
data pipeline via:

.. code-block:: sql

    INSERT INTO export_config
    (`name`, `batch`, `schema`) VALUES ("internal", 1, "internal");

For a production setup you want to set the batch column to something
like `100` or `1000` to get more efficiency. For initial testing its
easier to set it to `1` so you immediately process any incoming data.


Bucket Export
~~~~~~~~~~~~~

The Amazon S3 bucket export combines reports into a gzipped JSON file
and uploads them to the specified bucket ``url``, for example:

``s3://amazon_s3_bucket_name/directory/{source}{api_key}/{year}/{month}/{day}``

The schema column must be set to `s3`.

The url can contain any level of additional static directories under
the bucket root. The ``{api_key}/{year}/{month}/{day}`` parts will
be dynamically replaced by the `api_key` used to upload the data,
the source of the report (e.g. gnss) and the date when the backup took place.
The files use a random UUID4 as the filename.

An example filename might be:

``/directory/test/2015/07/15/554d8d3c-5b28-48bb-9aa8-196543235cf2.json.gz``

Internal Export
~~~~~~~~~~~~~~~

The internal export forwards the incoming data into the internal
data pipeline.

The schema column must be set to `internal`.

HTTPS Export
~~~~~~~~~~~~

The HTTPS export buffers incoming data into batches of ``batch``
size and then submits them using the :ref:`api_geosubmit_latest`
API to the specified ``url`` endpoint, for example:

``https://localhost/some/api/url?key=export``

The schema column must be set to `geosubmit`.

If the project is taking in data from a partner in a data exchange,
the ``skip_keys`` setting can be used to prevent data being
round tripped and send back to the same partner that it came from.
