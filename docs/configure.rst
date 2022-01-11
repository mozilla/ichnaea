.. _config:

=============
Configuration
=============

The application takes a number of different settings and reads them
from environment variables. There are also a small number of settings
inside database tables.

.. contents::
   :local:


.. _environment-variables:

Environment variables
=====================

.. autocomponent:: ichnaea.conf.AppComponent
   :hide-classname:
   :case: upper


Alembic requires an additional item in the environment:

.. code-block:: bash

   # URI for user with ddl access
   SQLALCHEMY_URL=mysql+pymysql://USER:PASSWORD@HOST:PORT/DBNAME


The webapp uses gunicorn which also has configuration.

.. literalinclude:: ../docker/run_web.sh
   :start-after: START GUNICORN CONFIGURATION
   :end-before: END GUNICORN CONFIGURATION
   :language: bash


Database
--------

The MySQL compatible database is used for storing configuration and application
data.

The webapp service requires a read-only connection.

The celery worker service requires a read-write connection.

Both of them can be restricted to only DML (data-manipulation) permissions as
neither need DDL (data-definition) rights.

DDL changes are done using the alembic database migration system.


GeoIP
-----

The web and worker roles need access to a maxmind GeoIP City database
in version 2 format. Both GeoLite and commercial databases will work.


Redis
-----

The Redis cache is used as a:

* classic cache by the web role
* backend to store rate-limiting counters
* custom and a worker queuing backend


Sentry
------

All roles and command line scripts use an optional Sentry server to log
application exception data. Set this to a Sentry DSN to enable Sentry or ``''``
to disable it.


StatsD
------

All roles and command line scripts use an optional StatsD service to log
application specific metrics. The StatsD service needs to support metric tags.

The project uses a lot of metrics as further detailed in :ref:`the metrics
documentation <metrics>`.

All metrics are prefixed with a `location` namespace.

.. _map_tile_and_download_assets:

Map tile and download assets
----------------------------

The application can optionally generate image tiles for a data map and public
export files available via the downloads section of the website.

These assets are stored in a static file repository (Amazon S3) and made
available via a HTTPS frontend (Amazon CloudFront).

Set ``ASSET_BUCKET`` and ``ASSET_URL`` accordingly.

To access the ``ASSET_BUCKET``, authorized AWS credentials are needed inside
the Docker image. See the `Boto3 credentials documentation`_ for details.

.. _`Boto3 credentials documentation`: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html

The development environment defaults to serving map tiles from the web server,
and not serving public export files for download.

.. _mapbox:

Mapbox
------

The web site content uses Mapbox to display a world map. In order to do this,
it requires a Mapbox API token. Without a token, the map is not displayed.

You can create an account on their site: https://www.mapbox.com

After you have an account, you can create an API token at:
https://account.mapbox.com

Set the ``MAP_TOKEN`` configuration value to your API token.


Configuration in the database
=============================

API Keys
--------

The project requires API keys to access the locate APIs.

API keys can be any string of up to 40 characters, though random UUID4s
in hex representation are commonly used, for example
``329694ac-a337-4856-af30-66162bc8187a``.


Fallback
~~~~~~~~

You can also enable a fallback location provider on a per API key basis.  This
allows you to send queries from this API key to an external service if Ichnaea
can't provide a good-enough result.

In order to configure this fallback mode, you need to set the ``fallback_*``
columns. For example:

.. code-block:: ini

    fallback_name: mozilla
    fallback_schema: ichnaea/v1
    fallback_url: https://location.services.mozilla.com/v1/geolocate?key=some_key
    fallback_ratelimit: 10
    fallback_ratelimit_interval: 60
    fallback_cache_expire: 86400

The name can be shared between multiple API keys and acts as a partition
key for the cache and rate limit tracking.

The schema can be one of  ``NULL``, ``ichnaea/v1``, ``combain/v1``,
``googlemaps/v1`` or ``unwiredlabs/v1``.

``NULL`` and ``ichnaea/v1`` are currently synonymous. Setting the schema to one
of those means the external service uses the same API as the geolocate v1 API
used in Ichnaea.

If you set the url to one of the unwiredlabs endpoints, add your API
token as an anchor fragment to the end of it, so instead of::

    https://us1.unwiredlabs.com/v2/process.php

you would instead use::

    https://us1.unwiredlabs.com/v2/process.php#my_secret_token
    
The code will read the token from here and put it into the request body.

Note that external services will have different terms regarding caching, data
collection, and rate limiting.

If the external service allows caching their responses on an intermediate
service, the ``cache_expire`` setting can be used to specify the number of
seconds the responses should be cached. This can avoid repeated calls to the
external service for the same queries.

The rate limit settings are a combination of how many requests are allowed to
be send to the external service. It's a "number" per "time interval"
combination. In the above example, 10 requests per 60 seconds.


Export Configuration
--------------------

Ichnaea supports exporting position data that it gets via the APIs to different
export targets. This configuration lives in the ``export_config`` database
table.

Currently three different kinds of backends are supported:

* ``s3``: Amazon S3 buckets
* ``internal``: Ichnaea's internal data processing pipeline which creates/
  updates position data using new position information
* ``geosubmit``: submitting position information to an HTTP POST endpoint in
  geosubmit v2 format

The type of the target is determined by the ``schema`` column of each entry.

All export targets can be configured with a ``batch`` setting that determines
how many reports have to be available before data is submitted to the backend.

All exports have an additional ``skip_keys`` setting as a set of API keys. Data
submitted using one of these API keys will not be exported to the target.

There can be multiple instances of the bucket and HTTP POST export
targets in ``export_config``, but only one instance of the internal export.

Here's the SQL for setting up an "internal" export target:

.. code-block:: sql

    INSERT INTO export_config
    (`name`, `batch`, `schema`) VALUES ("internal test", 1, "internal");

For a production setup you want to set the batch column to something
like ``100`` or ``1000`` to get more efficiency. For initial testing its
easier to set it to ``1`` so you immediately process any incoming data.


S3 Bucket Export (s3)
~~~~~~~~~~~~~~~~~~~~~

The schema column must be set to ``s3``.

The S3 bucket export target combines reports into a gzipped JSON file and
uploads them to the specified bucket ``url``, for example::

    s3://amazon_s3_bucket_name/directory/{source}{api_key}/{year}/{month}/{day}

The url can contain any level of additional static directories under
the bucket root. The ``{api_key}/{year}/{month}/{day}`` parts will
be dynamically replaced by the `api_key` used to upload the data,
the source of the report (e.g. gnss) and the date when the backup took place.
The files use a random UUID4 as the filename.

An example filename might be::

    /directory/test/2015/07/15/554d8d3c-5b28-48bb-9aa8-196543235cf2.json.gz


Internal Export (internal)
~~~~~~~~~~~~~~~~~~~~~~~~~~

The schema column must be set to ``internal``.

The internal export target forwards the incoming data into the internal data
pipeline.


HTTP Export (geosubmit)
~~~~~~~~~~~~~~~~~~~~~~~

The schema column must be set to ``geosubmit``.

The HTTP export target buffers incoming data into batches of ``batch`` size and
then submits them using the :ref:`api_geosubmit_latest` API to the specified
``url`` endpoint.

If the project is taking in data from a partner in a data exchange, the
``skip_keys`` setting can be used to prevent data being round tripped and sent
back to the same partner that it came from.
