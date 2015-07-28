.. _metrics:

=======
Metrics
=======

As discussed in :ref:`the deployment document <deploy>`, Ichnaea emits
metrics through the Statsd client library with the intent of
aggregating and viewing them on a compatible dashboard.

This document describes the metrics collected.

The code emits most metrics using the statsd tags extension. A metric
name of ``task#name:function,version:old`` therefor means a statsd metric
called `task` will be emitted with two tags `name:function` and
`version:old`. If the statsd backend does not support tags, the
statsd client can be configured with a `tag_support = false` option.
In this case the above metric would be emitted as:
``task.name_function.version_old``.


API Query Metrics
-----------------

For each incoming API query we log metrics about the data contained in
the query under the following two prefixes:

``<api_type>.query.<api_shortname>.all.``,
``<api_type>.query.<api_shortname>.<country_code>.``

`api_type` describes the type of API being used, independent of the
version number of the API. So `v1/country` gets logged as `country`
and both `v1/search` and `v1/geolocate` get logged as `locate`.

`country_code` is either a two-letter ISO3166 code like `de` or the
special value `none` if the country origin of the incoming request
could not be determined. The value for `all` will be always be logged,
even for the `none` case.

Under these two prefixes, there are a number of metrics:

``geoip.only`` : counter

    If the query contained only GeoIP data and nothing else, only log
    this metric and none of the following.

``cell.none``, ``cell.one``, ``cell.many``,
``wifi.none``, ``wifi.one``, ``wifi.many`` : counter

    If the query contained any cell or wifi networks, one cell and one
    wifi metric gets logged. The metrics depend on the number of valid
    stations for each of the two.


API Source Metrics
------------------

TODO - describe metrics collected about each individual source of
location data, like our internal database or OpenCellIDs data.


API Result Metrics
------------------

Similar to the API query metrics we also collect metrics about each
result of an API query. This follows the same per API type and per
country rules under the prefixes:

``<api_type>.result.<api_shortname>.all.``,
``<api_type>.result.<api_shortname>.<country_code>.``

Under these two prefixes we collect metrics that measure if we satisfied
the incoming API query in the best possible fashion. Incoming queries
can generally contain WiFi networks, cell networks, an IP address or any
mixture thereof. If the query contained only cell networks, we do not
expect to get a high accuracy result, as there is too little data in the
query to do so.

We express this by classifying each incoming query into one of four
categories:

High Accuracy (``high``)
    A query containing at least two WiFi networks.

Medium Accuracy (``medium``)
    A query containing no WiFi networks but at least one cell network.

Low Accuracy (``low``)
    A query containing no networks but only the IP address of the client.

No Accuracy (``none``)
    A query containing no usable information, for example an IP-only
    query that explicitly disables the IP fallback.

A query containing multiple data types gets put into the best possible
category, so for example any query containing cell data will at least
be of medium accuracy.

One we have determined the expected accuracy category for the query, we
compare it to the accuracy category of the result we determined. If we
can deliver an equal or better category we consider the status to be
a `hit`. If we don't satisfy the expected category we consider the
result to be a `miss`.

For each result we then log exactly one of the following result metrics:

``high.hit``, ``high.miss``,
``medium.hit``, ``medium.miss``,
``low.hit``, ``low.miss`` : counter

We don't log metrics for the uncommon case of ``none`` or no expected
accuracy.

One special case exists for cell networks. If we cannot find an exact
cell match, we might fall back to a cell area based estimate. If the
range of the cell area is fairly small we consider this to be a
``medium.hit``. But if the size of the cell area is extremely large, in
the order of tens of kilometers to hundreds of kilometers, we consider
it to be a ``medium.miss``.

In the past we only collected stats based on whether or not cell based
data was used to answer a cell based query and counted it as a
cell-based success, even if the provided accuracy was really bad.


Fallback Source Metrics
-----------------------

The external fallback source has a couple extra metrics to observe the
performance of outbound network calls and the effectiveness of its cache.

``locate.fallback.cache.hit``,
``locate.fallback.cache.miss``,
``locate.fallback.cache.bypassed`` : counter

    Counts the number of hits and misses for the fallback cache. Since
    the cache only works for single cell based queries, there is also a
    third metric for all requests bypassing the cache.

``locate.fallback.lookup`` : timer

    Measures the time it takes to do each outbound network request.

``locate.fallback.lookup_status.<code>`` : counter

    Counts the HTTP response codes for all outbound requests. There is
    one counter per HTTP response code, for example `200`.


API Key Metrics
---------------

TODO: Redo these to better fit with the new API query/source/result metrics.

Several families of counters exist based on API keys. These have the prefixes:

  - ``geolocate.api_key.*``
  - ``search.api_key.*``
  - ``geosubmit.api_key.*``
  - ``geosubmit2.api_key.*``
  - ``submit.api_key.*``

Each immediate sub-component of the metric name after the prefix is the name
of an API key, which is a counter of the number of times a request to each
named API endpoint (``geolocate``, ``geosubmit``, etc.) came in using the
named API key.

In addition, each API endpoint has two counters measuring requests that
fail to provide an API key, or provide an unknown API key. These counters
are named:

  - ``<api_endpoint>.no_api_key``
  - ``<api_endpoint>.unknown_api_key``


Data Pipeline Metrics
---------------------

When a batch of reports is accepted at one of the submission API
endpoints, it is decomposed into a number of "items" -- wifi or cell
observations -- each of which then works its way through a process of
normalization, consistency-checking and eventually (possibly) integration
into aggregate station estimates held in the main database tables.
Along the way several counters measure the steps involved:

``items.uploaded.batches`` : counter

    Counts the number of "batches" of reports accepted to the data
    processing pipeline by an API endpoint. A batch generally
    corresponds to the set of items uploaded in a single HTTP POST to the
    ``submit`` or ``geosubmit`` APIs. In other words this metric counts
    "submissions that make it past coarse-grained checks" such as API-key
    and JSON schema validity checking.

``items.uploaded.batch_size`` : timer

    Pseudo-timer counting the number of reports per uploaded batch.
    Typically client software uploads 50 reports per batch.

``items.uploaded.reports`` : counter

    Counts the number of reports accepted into the data processing pipeline.

``items.uploaded.cell_observations``, ``items.uploaded.wifi_observations`` : counters

    Count the number of cell or wifi observations entering the data
    processing pipeline; before normalization and blacklist processing
    have been applied. In other words this metric counts "total cell or
    wifi observations inside each submitted batch", as each batch is
    decomposed into individual observations.

``items.dropped.cell_ingress_malformed``, ``items.dropped.wifi_ingress_malformed`` : counters

    Count incoming cell or wifi observations that were discarded before
    integration due to some internal consistency, range or
    validity-condition error encountered while attempting to normalize the
    observation.

``items.dropped.cell_ingress_blacklisted``, ``items.dropped.wifi_ingress_blacklisted`` : counters

    Count incoming cell or wifi observations that were discarded before
    integration due to the presence of a blacklist record for the station
    (see next metric).

``items.blacklisted.cell_moving``, ``items.blacklisted.wifi_moving`` : counters

    Count any cell or wifi that is blacklisted due to the acceptance of
    multiple observations at sufficiently different locations. In these
    cases, Ichnaea decides that the station is "moving" (such as a picocell
    or mobile hotspot on a public transit vehicle) and blacklists it, to
    avoid estimating query positions using the station.

``items.inserted.cell_observations``, ``items.inserted.wifi_observations`` : counters

    Count cell or wifi observations that are successfully normalized,
    integrated and not discarded due to consistency errors.

In addition to these global stats on the data processing pipeline,
we also have a number of per API key stats for uploaded data.

``items.api_log.<api_shortname>.uploaded.batches``,
``items.api_log.<api_shortname>.uploaded.reports`` : counters

    Count the number of batches and reports for this API key.

``items.api_log.<api_shortname>.uploaded.batch_size`` : timer

    Count the batch size for submissions for this API key.

``items.api_log.<api_shortname>.uploaded.cell_observations``,
``items.api_log.<api_shortname>.uploaded.wifi_observations`` : counters

    Count the number of uploaded cell and wifi observations for this API key.


Export Metrics
--------------

Incoming reports can also be sent to a number of different export targets.
We keep metrics about how those individual export targets perform.

``items.export.<export_key>.batches`` : counter

    Count the number of batches sent to the export target.

``items.export.<export_key>.upload`` : timer

    Track how long the upload operation took per export target.

``items.export.<export_key>.upload_status.<status>`` : counter

    Track the upload status of the current job. One counter per status.
    A status can either be a simple `success` and `failure` or a HTTP
    response code like 200, 400, etc.


Internal Monitoring
-------------------

``api.limit#key:<apikey_shortname>`` : gauge

    One gauge is created per API key that has rate limiting enabled on it.
    This gauge measures how many requests have been done for each such
    API key for the current day.

``queue#name:celery_default``,
``queue#name:celery_export``,
``queue#name:celery_incoming``,
``queue#name:celery_insert``,
``queue#name:celery_monitor``,
``queue#name:celery_reports``,
``queue#name:celery_upload`` : gauges

    These gauges measure the number of tasks in each of the Redis queues.
    They are sampled at an approximate per-minute interval.

``queue#name:update_cell``,
``queue#name:update_cell_area``,
``queue#name:update_mapstat``,
``queue#name:update_score``,
``queue#name:update_wifi`` : gauges

    These gauges measure the number of items in the Redis update queues.
    These queues are used to keep track of which observations still need to
    be acted upon and integrated into the aggregate station data.

``table#name:ocid_cell_age`` : gauge

    This gauge measures when the last entry was added to the table. It
    represents this as `now() - max(created)` and converts it to a
    millisecond value. This metric is useful to see if the ocid_import
    jobs are run on a regular basis.


HTTP Counters
-------------

Every legitimate, routed request, whether to an API endpoint or
to static content, increments a
``request#path:<path>,method:<method>,status:<code>`` counter.

The path of the counter is the based on the path of the HTTP
request, with slashes replaced with periods. The method tag contains
the lowercased HTTP method of the request. The status tag contains
the response code produced by the request.

For example, a GET of ``/stats/regions`` that results in an HTTP 200
status code, will increment the counter
``request#path:stats.regions,method:get,status:200``.

Response codes in the 400 range (eg. 404) are only generated for HTTP
paths referring to API endpoints. Logging them for unknown and invalid
paths would overwhelm the system with all the random paths the friendly
Internet bot army sends along.


HTTP Timers
-----------

In addition to the HTTP counters, every legitimate, routed request
emits a ``request#path:<path>,method:<method>`` timer.

These timers have the same structure as the HTTP counters, except they
do not have the response code tag.


Task Timers
-----------

Our data ingress and data maintenance actions are managed by a Celery
queue of tasks. These tasks are executed asynchronously, and each task
emits a timer indicating its execution time.

For example:

  - ``task#name:data.update_statcounter``
  - ``task#name:data.upload_reports``


Datamaps Timers
---------------

We include a script to generate a data map from the gathered map
statistics. This script includes a number of timers and pseudo-timers
to monitor its operation.

``datamaps#func:export_to_csv``,
``datamaps#func:encode``,
``datamaps#func:main``,
``datamaps#func:render``,
``datamaps#func:upload_to_s3`` : timers

    These timers track the individual functions of the generation process.

``datamaps#count:csv_rows``,
``datamaps#count:s3_list``,
``datamaps#count:s3_put``,
``datamaps#count:tile_new``,
``datamaps#count:tile_changed``,
``datamaps#count:tile_unchanged`` : timers

    Pseudo-timers to track the number of CSV rows, image tiles and
    S3 operations.
