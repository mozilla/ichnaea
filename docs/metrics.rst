.. _metrics:

=======
Metrics
=======

As discussed in :ref:`the deployment document <deploy>`, Ichnaea emits
metrics through the Heka and Statsd client libraries with the intent of
aggregating and viewing them on a Graphite server.

This document describes the metrics collected.

Counter aggregation
-------------------

In the following sections, any counter described will typically result in
*two* sub-metrics emitted from Heka. This is because Heka performs a level
of time-based aggregation before reporting to Graphite. In other words,
Heka typically accumulates counter messages for a given reporting period (60
seconds by default) and passes along to Graphite a single aggregate
function applied to the messages in each reporting period.

``count``

    The net counter-increment over the reporting period.

``rate``

    The average number of increments *per second* over the reporting
    period.

For example, the counter ``geolocate.cell_found`` below will cause two
metrics -- ``geolocate.cell_found.count`` and ``geolocate.cell_found.rate``
to be visible in Graphite.

Typically Graphite will further aggregate these into display-appropriate
time-based buckets when graphing them.


Timer aggregation
-----------------

As with counters, Heka will accumulate timer messages over a reporting
period, and emit periodic sub-metrics of aggregate functions over the
messages accumulated during the reporting period. The aggregates emitted
for timers are different than for counters, however:

``count``

    The number of timer events over the reporting period.

``count_ps``

    The average number of timer events *per second* over the reporting
    period.

``lower``

    The minimum value of any timer event over the reporting period.

``upper``

    The maximum value of any timer event over the reporting period.

``upper_90``

    The maximum of the lower 90th percentile of the values of all timer
    events over the reporting period.

``sum``

    The sum of the values of all timer events over the reporting period.

``mean``

    The mean of the values of all timer events over the reporting period.

``mean_90``

    The mean of the lower 90th percentile of the values of all timer
    events over the reporting period.


API-key counters
----------------

Several families of counters exist based on API keys. These have the prefixes:

  - ``geolocate.api_key.*``
  - ``search.api_key.*``
  - ``geosubmit.api_key.*``
  - ``submit.api_key.*``

Each immediate sub-component of the metric name after the prefix is the name
of an API key, which is a counter of the number of times a request to each
named API endpoint (``geolocate``, ``search``, ``submit`` or ``geosubmit``)
came in using the named API key.

In addition, each API endpoint has two counters measuring requests that
fail to provide an API key, or provide an unknown API key. These counters
are named:

  - ``geolocate.no_api_key``
  - ``search.no_api_key``
  - ``geosubmit.no_api_key``
  - ``submit.no_api_key``

and

  - ``geolocate.unknown_api_key``
  - ``search.unknown_api_key``
  - ``geosubmit.unknown_api_key``
  - ``submit.unknown_api_key``

respectively.


Response-type counters
----------------------

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
exist for the ``search`` and ``geosubmit`` API endpoints.


Response type API key specific counters
---------------------------------------

In addition to the above mentioned response type counters, additional
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


In addition to ``geolocate`` response-type counters, equivalent counters
exist for the ``search`` and ``geosubmit`` API endpoints.


WiFi query characteristics
--------------------------

Specifically for WiFi based queries, we collect a number of additional
metrics.

``geolocate.wifi.provided_too_few`` : counter

    Counts the number of times we get requests with exactly one WiFi
    network in them.

``geolocate.wifi.provided`` : timer

    Provides a pseudo-timer counting the number of WiFi networks in
    request. Only applies to requests with at least two WiFi networks.

``geolocate.wifi.partial_match`` : counter

    Counts the number of requests where we have WiFi records for some
    but not all of the provided networks.

``geolocate.wifi.provided_not_known`` : timer

    Provides a pseudo-timer counting the number of additional WiFi
    networks in a request, for which we did not have a record.

``geolocate.wifi.provided_too_similar`` : timer

    Provides a pseudo-timer counting the number of WiFi networks, which
    where too similar to each other. Only applies to requests where at
    least one WiFi network was detected as being too similar.

``geolocate.wifi.found_too_few`` : counter

    Counts the number of requests where we found less than two WiFi
    records after filtering them for similarity.

``geolocate.wifi.found_no_cluster`` : counter

    Counts the number of requests where we found no cluster of nearby
    WiFi networks which included at least two networks.


These counters and timers also exist for the ``search``
and ``geosubmit`` API endpoints.


Fine-grained ingress stats
--------------------------

When a batch of reports is accepted at one of the submission API
endpoints, it is decomposed into a number of "items" -- wifi or cell
observations -- each of which then works its way through a process of
normalization, consistency-checking, rate limiting and eventually
(possibly) integration into aggregate station estimates held in the main
database tables. Along the way several counters measure the steps involved:

``items.uploaded.batches`` : counter

    Counts the number of "batches" of reports accepted to the data
    processing pipeline by an API endpoint. A batch generally
    corresponds to the set of items uploaded in a single HTTP POST to the
    ``submit`` or ``geosubmit`` APIs. In other words this metric counts
    "submissions that make it past coarse-grained checks" such as API-key
    and JSON schema validity checking.

``items.uploaded.batch_size`` : timer

    Pseudo-timer counting the number of reports per uploaded batch.
    Typically client software like Mozilla Stumbler uploads 50 reports
    per batch.

``items.uploaded.reports`` : counter

    Counts the number of reports accepted to the data processing pipeline.

``items.uploaded.cell_observations``, ``items.uploaded.wifi_observations`` : counters

    Count the number of cell or wifi observations entering the data processing
    pipeline; before normalization, blacklist processing and rate limiting
    have been applied. In other words this metric counts "total cell or wifi
    observations inside each submitted batch", as each batch is decomposed
    into individual observations.

``items.dropped.cell_ingress_malformed``, ``items.dropped.wifi_ingress_malformed`` : counters

    Count incoming cell or wifi observations that were discarded before
    integration due to some internal consistency, range or
    validity-condition error encountered while attempting to normalize the
    observation.

``items.dropped.cell_ingress_overflow``, ``items.dropped.wifi_ingress_overflow`` : counters

    Count incoming cell or wifi observations that were discarded before
    integration due to the rate of arrival of new records exceeding a
    threshold of new records per period of time. The rate limiting is done
    per-station, in other words only those observations pertaining to a
    cell or wifi that already has "too many" recent observations are
    discarded, and only the newest observations are discarded.

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

    Count cell or wifi observations that are successfully normalized and
    integrated, not discarded due to rate limits or consistency errors.

``items.cell_unthrottled``, ``items.wifi_unthrottled`` : counters

    Count space made for new observations in the wifi and cell observation
    tables due to periodic backup and trimming of old records. Specifically:
    for cell or wifi stations that were previously rate-limited, count the
    amount of new space for observations of those stations freed up after each
    backup and trim task runs. This is not the same as the number of
    observations backed up; it's *only* a count of the cumulative space freed
    for previously rate-limited stations.

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

Gauges
------

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

``task.data.location_update_cell.new_measures_<min>_<max>``,
``task.data.location_update_wifi.new_measures_<min>_<max>``, : gauges

    These gauges measure the number of stations which have a new observation
    count within a certain range. These gauges should remain relatively
    constant if Ichnaea is "keeping up with" using new observations to
    update the position estimates of these stations.

``table.cell_measure``, ``table.wifi_measure`` : gauges

    These gauges measure the number of database rows in each of the observation
    tables at a regular interval. For performance reasons the gauges are
    based on `max(id) - min(id)`, which might be higher than the actual
    number of rows if not all auto-increment numbers are taken.

``table.ocid_cell_age`` : gauges

    This gauge measures when the last entry was added to the table. It
    represents this as `now() - max(created)` and converts it to a
    millisecond value. This metric is useful to see if the ocid_import
    jobs are run on a regular basis.


S3 backup counters
------------------

Ichnaea contains logic for backing up and optionally trimming large
observation tables to S3 or similar bulk storage systems. When such backup
events occur, some associated counters are emitted:

``s3.backup.cell``, ``s3.backup.wifi`` : counters

    Counts the number of cell or wifi observations that have been backed up.


HTTP counters
-------------

Every legitimate, routed request to Ichnaea, whether to an API endpoint or
to static content, also increments an ``request.*`` counter. The path
of the counter is the based on the path of the HTTP request, with slashes
replaced with periods, followed by a final component named by the response
code produced by the request.

For example, a GET of ``/stats/countries`` that results in an HTTP 200
status code, will increment the counter ``request.stats.countries.200``.

Response codes in the 400 range (eg. 404) are only generated for HTTP paths
referring to API endpoints. Logging them for unknown and invalid paths would
overwhelm the graphite backend with all the random paths the friendly
Internet bots army sends along.


HTTP timers
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

  - ``task.content.cell_histogram``
  - ``task.data.insert_measures``


Datamaps timers
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
