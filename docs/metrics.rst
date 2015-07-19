.. _metrics:

=======
Metrics
=======

As discussed in :ref:`the deployment document <deploy>`, Ichnaea emits
metrics through the Statsd client library with the intent of
aggregating and viewing them on a compatible dashboard.

This document describes the metrics collected.


API Key Counters
----------------

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


Response Counters
-----------------

For each API endpoint, and for each type of location datum that can be
found in response to a query (``cell``, ``cell_lac``, ``wifi`` and
``geoip``) a set of counters is produced to track how often a query commits
to using ("hits") the given type of data on the given API.

Some of these counters are "mutually exclusive" with respect to one
another; which is to say that for every query *exactly one* of them will be
incremented.

For the ``geolocate`` API, the following counters are emitted:

``geolocate.cell_hit`` : counter

    Counts any geolocation query response that was based primarily on a
    cell record. This counter is mutually exclusive with
    ``geolocate.wifi_hit``, ``geolocate.cell_lac_hit``, and
    ``geolocate.geoip_hit``.

``geolocate.cell_lac_hit`` : counter

    Counts any geolocation query response that was based primarily on a
    cell LAC record. This counter is mutually exclusive with
    ``geolocate.wifi_hit``, ``geolocate.cell_hit``, and
    ``geolocate.geoip_hit``.

``geolocate.wifi_hit`` : counter

    Counts any geolocation query response that was based primarily on
    wifi records. This counter is mutually exclusive with
    ``geolocate.cell_hit``, ``geolocate.cell_lac_hit``, and
    ``geolocate.geoip_hit``.

``geolocate.geoip_city_found`` : counter

    Counts any geolocation query for which GeoIP lookup of the query
    source produced a city-level record, whether or not that city was
    used in the response. This counter is mutually exclusive with
    ``geolocate.geoip_country_found``.

``geolocate.geoip_country_found`` : counter

    Counts any geolocation query for which GeoIP lookup of the query source
    produced only a country-level record, whether or not that country was
    used in the response. This counter is mutually exclusive with
    ``geolocate.geoip_city_found``.

``geolocate.geoip_hit`` : counter

    Counts any geolocation query response that was based primarily on a
    GeoIP record. This counter is mutually exclusive with
    ``geolocate.cell_hit``, ``geolocate.cell_lac_hit``, and
    ``geolocate.wifi_hit``.

``geolocate.miss`` : counter

    Counts any geolocation query which did not find enough information
    in the database to make any sort of guess at a location, and thus
    returned an empty response.


In addition to ``geolocate`` response-type counters, equivalent counters
exist for the ``search`` API endpoint.


Per API Key Response Counters
-----------------------------

In addition to the above mentioned response counters, additional
extended stats are provided for some API keys. These counters track if
the best possible response was given for each query. Exactly one counter
is used per response. For example if WiFi information was provided in the
request and the service did not respond with a WiFi based result, a
"wifi_miss" metric is emitted, independent of whether a cell based or geoip
based response was provided instead.

``geolocate.api_log.<api_shortname>.wifi_hit``,
``geolocate.api_log.<api_shortname>.wifi_miss``, : counter

    Counts the number of requests that did contain WiFi data and were
    responded to with a WiFi based result (hit) and those that did not
    (miss).

``geolocate.api_log.<api_shortname>.cell_hit``,
``geolocate.api_log.<api_shortname>.cell_lac_hit``,
``geolocate.api_log.<api_shortname>.cell_miss``, : counter

    Counts the number of requests that did contain cell data and were
    responded to with a cell (hit) or a cell location area (lac_hit) result
    and those that were not answered with any cell based data (miss).

``geolocate.api_log.<api_shortname>.geoip_hit``,
``geolocate.api_log.<api_shortname>.geoip_miss``, : counter

    Counts the number of requests that did contain neither cell nor WiFi
    data and were successfully answered with a geoip result (hit) and
    those were no position estimate could be given (miss).


In addition to ``geolocate`` response counters, equivalent counters
exist for the ``search`` API endpoint.


API Query Counters
------------------

For each incoming API query we log stats about the data contained in
the query under the following two prefixes:

``<api_type>.query.<api_shortname>.all.``,
``<api_type>.query.<api_shortname>.<country_code>.``

`api_type` describes the type of API being used, independent of the
version number of the API. So `v1/country` gets logged as `country`
and both `v1/search` and `v1/geolocate` get logged as `locate`.

`country_code` is either a two-letter ISO3166 code like `de` or the
special value `none` if the country of the incoming request could not
be determined. The value for `all` will be always be logged, even for
the `none` case.

Under these two prefixes, there are a number of metrics:

``geoip.only`` : counter

If the query contained only GeoIP data and nothing else, only log this
metrics and none of the following.

``cell.none``, ``cell.one``, ``cell.many``,
``wifi.none``, ``wifi.one``, ``wifi.many``, : counter

If the query contained any cell or wifi data, one cell and one wifi
metric gets logged. The metrics depend on the number of valid stations
for each of the two.


Data Pipeline Stats
-------------------

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

Export Stats
------------

Incoming reports can also be sent to a number of different export targets.
We keep stats on how those individual export targets perform.

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

``queue.celery_default``,
``queue.celery_incoming``,
``queue.celery_insert``,
``queue.celery_monitor``, : gauges

    These gauges measure the number of tasks in each of the Redis queues.
    They are sampled at an approximate per-minute interval.

``queue.update_cell``,
``queue.update_cell_lac``,
``queue.update_wifi``, : gauges

    These gauges measure the number of items in the Redis update queues.
    These queues are used to keep track of which observations still need to
    be acted upon and integrated into the aggregate station data.

``table.ocid_cell_age`` : gauges

    This gauge measures when the last entry was added to the table. It
    represents this as `now() - max(created)` and converts it to a
    millisecond value. This metric is useful to see if the ocid_import
    jobs are run on a regular basis.


HTTP Counters
-------------

Every legitimate, routed request to Ichnaea, whether to an API endpoint or
to static content, also increments a ``request.*`` counter. The path
of the counter is the based on the path of the HTTP request, with slashes
replaced with periods, followed by a final component named by the response
code produced by the request.

For example, a GET of ``/stats/regions`` that results in an HTTP 200
status code, will increment the counter ``request.stats.regions.200``.

Response codes in the 400 range (eg. 404) are only generated for HTTP paths
referring to API endpoints. Logging them for unknown and invalid paths would
overwhelm the system with all the random paths the friendly Internet bots
army sends along.


HTTP Timers
-----------

In addition to the HTTP counters, every legitimate, routed request to
Ichnaea emits an ``request.*`` *timer*. These timers have the same
name structure as the HTTP counters, except they do not have a final
component based on the response code. Rather, they aggregate over all
response codes for a given HTTP path.


Task timers
-----------

Ichnaea's ingress and data-maintenance actions are managed by a Celery
queue of *tasks*. These tasks are executed asynchronously, and each task
emits a timer indicating its execution time.

For example:

  - ``task.data.update_statcounter``
  - ``task.data.upload_reports``


Datamaps Timers
---------------

Ichnaea includes a script to generate a data map from the gathered map
statistics. This script includes a number of timers and pseudo-timers
to monitor its operation.

This includes timers to track the individual steps of the generation process:

  - ``datamaps.export_to_csv``
  - ``datamaps.encode``
  - ``datamaps.render``
  - ``datamaps.upload_to_s3``

A gauge to plot the number of rows in the mapstat table:

  - ``datamaps.csv_rows``

And pseudo-timers to track the number of image tiles and S3 operations:

  - ``datamaps.s3_list``
  - ``datamaps.s3_put``
  - ``datamaps.tile_new``
  - ``datamaps.tile_changed``
  - ``datamaps.tile_unchanged``
