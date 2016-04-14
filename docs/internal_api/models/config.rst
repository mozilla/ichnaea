:mod:`ichnaea.models.config`
----------------------------

.. automodule:: ichnaea.models.config
    :members:
    :member-order: bysource

Export Configuration
++++++++++++++++++++

The project supports exporting all data that its gets via the
submit-style APIs to different backends.

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
