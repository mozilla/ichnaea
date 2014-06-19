.. _metrics:

=======
Metrics
=======

As discussed in `the deployment document <deploy.html>`_, Ichnaea emits
metrics through the Heka client library with the intent of aggregating and
viewing them on a Graphite server.

This document describes the metrics collected.

Counter aggregation
-------------------

In the following sections, any counter described will typically result in
*two* sub-metrics emitted from Heka. This is because Heka performs a level
of time-based aggregation before reporting to Graphite. In other words,
Heka typically accumulates counter messages for a given reporting period (5
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

Several families of counter exist based on API keys. These have the prefixes:

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
``geoip``) a set of counters is produced to track how often a query finds,
fails to find, or commits to using ("hits") the given type of data on the
given API.

Some of these counters are "mutually exclusive" with respect to one
another; which is to say that for every query *exactly one* of them will be
incremented.

For the ``geolocate`` API, the following counters are emitted:

``geolocate.cell_found`` : counter

    Counts any geolocation query that included a cell that the database has
    information about, whether or not that information was used in the
    response. This counter is mutually exclusive with
    ``geolocate.no_cell_found``.

``geolocate.no_cell_found`` : counter

    Counts any geolocation query that *did not* include any cell that the
    database has information about. This counter is mutually exclusive with
    ``geolocate.cell_found``.

``geolocate.cell_hit`` : counter

    Counts any geolocation query response that was based primarily on a
    cell record. This counter is mutually exclusive with
    ``geolocate.wifi_hit``, ``geolocate.cell_lac_hit``, and
    ``geolocate.geoip_hit``.

``geolocate.cell_lac_found`` : counter

    Counts any geolocation query that included a cell that the database has
    information about the corresponding LAC of, whether or not that
    information was used in the response. This counter is mutually
    exclusive with ``geolocate.no_cell_lac_found``.

``geolocate.no_cell_lac_found`` : counter

    Counts any geolocation query that *did not* include any cell that the
    database has information about the corresponding LAC of. This counter
    is mutually exclusive with ``geolocate.cell_lac_found``.

``geolocate.cell_lac_hit`` : counter

    Counts any geolocation query response that was based primarily on a
    cell LAC record. This counter is mutually exclusive with
    ``geolocate.wifi_hit``, ``geolocate.cell_hit``, and
    ``geolocate.geoip_hit``.

``geolocate.wifi_found`` : counter

    Counts any geolocation query that included at least two physically
    adjacent wifi networks that the database has information about, whether
    or not that information was used in the response. This counter is
    mutually exclusive with ``geolocate.no_wifi_found``.

``geolocate.no_wifi_found`` : counter

    Counts any geolocation query that included too few adjacent wifis, or
    no wifis at all, that the database has information about. This counter
    is mutually exclusive with ``geolocate.wifi_found``.

``geolocate.wifi_hit`` : counter

    Counts any geolocation query response that was based primarily on
    wifi records. This counter is mutually exclusive with
    ``geolocate.cell_hit``, ``geolocate.cell_lac_hit``, and
    ``geolocate.geoip_hit``.

``geolocate.geoip_city_found`` : counter

    Counts any geolocation query for which GeoIP lookup of the query
    source produced a city-level record, whether or not that city was
    used in the response. This counter is mutually exclusive with
    ``geolocate.geoip_country_found`` and ``geolocate.no_geoip_found``.

``geolocate.geoip_country_found`` : counter

    Counts any geolocation query for which GeoIP lookup of the query source
    produced only a country-level record, whether or not that country was
    used in the response. This counter is mutually exclusive with
    ``geolocate.geoip_city_found`` and ``geolocate.no_geoip_found``.

``geolocate.no_geoip_found`` : counter

    Counts any geolocation query for which GeoIP lookup returned no
    information. This counter is mutually exclusive with
    ``geolocate.geoip_city_found`` and ``geolocate.geoip_country_found``.

``geolocate.geoip_hit`` : counter

    Counts any geolocation query response that was based primarily on a
    GeoIP record. This counter is mutually exclusive with
    ``geolocate.cell_hit``, ``geolocate.cell_lac_hit``, and
    ``geolocate.wifi_hit``.

``geolocate.country_from_geoip`` : counter

    Counts any geolocation query from which the "source country" of the
    query was inferred from GeoIP information. This counter is mutually
    exclusive with ``geolocate.country_from_mcc``. Source countries are
    used in consistency checking; see counters below such as
    ``geolocate.anomaly.wifi_country_mismatch``.

``geolocate.country_from_mcc`` : counter

    Counts any geolocation query from which the "source country" of the
    query was inferred from the query's cell MCC number(s). This counter is
    mutually exclusive with ``geolocate.country_from_geoip``. Source
    countries are used in consistency checking; see counters below such as
    ``geolocate.anomaly.wifi_country_mismatch``.

``geolocate.miss`` : counter

    Counts any geolocation query which did not find enough information
    in the database to make any sort of guess at a location, and thus
    returned an empty response.


In addition to ``geolocate`` response-type counters, equivalent counters
exist for the ``search`` and ``geosubmit`` API endpoints. These are named:


  - ``search.cell_found``
  - ``search.no_cell_found``
  - ``search.cell_hit``
  - ``search.cell_lac_found``
  - ``search.no_cell_lac_found``
  - ``search.cell_lac_hit``
  - ``search.wifi_found``
  - ``search.no_wifi_found``
  - ``search.wifi_hit``
  - ``search.geoip_city_found``
  - ``search.geoip_country_found``
  - ``search.no_geoip_found``
  - ``search.geoip_hit``
  - ``search.country_from_geoip``
  - ``search.country_from_mcc``
  - ``search.miss``
  - ``geosubmit.cell_found``
  - ``geosubmit.no_cell_found``
  - ``geosubmit.cell_hit``
  - ``geosubmit.cell_lac_found``
  - ``geosubmit.no_cell_lac_found``
  - ``geosubmit.cell_lac_hit``
  - ``geosubmit.wifi_found``
  - ``geosubmit.no_wifi_found``
  - ``geosubmit.wifi_hit``
  - ``geosubmit.geoip_city_found``
  - ``geosubmit.geoip_country_found``
  - ``geosubmit.no_geoip_found``
  - ``geosubmit.geoip_hit``
  - ``geosubmit.country_from_geoip``
  - ``geosubmit.country_from_mcc``
  - ``geosubmit.miss``


Their meanings are identical to those specified above for the ``geolocate``
API.


Query anomaly counters
----------------------

These count semantic data inconsistencies detected either in a query or in
the data retrieved in response to a query. In some cases they will cause
the query to be rejected outright, in other cases simply degrade the
quality of the query.

These inconsistencies are generally not automatically correctable as it's
not clear which data is correct or incorrect, merely that two data points
disagree on some fact that they "should" agree on. The corrective measure
taken is usually to reduce the estimated accuracy of the result, or discard
the data that suggests higher accuracy in favour of that which suggests
lower.

``geolocate.anomaly.cell_lac_country_mismatch`` : counter

    Counts any cell-based geolocation query where the cell LAC stored in
    the database was located outside the country inferred from the query's
    GeoIP and/or cell MCC.

``geolocate.anomaly.geoip_mcc_mismatch`` : counter

    Counts any cell-based geolocation query where the country inferred from
    an observed cell's MCC did not match the country code inferred from the
    query GeoIP.

``geolocate.anomaly.wifi_cell_lac_mismatch`` : counter

    Counts any cell-and-wifi geolocation query where the wifi stored in the
    database was located outside the cell's LAC bounding box, also as
    stored in the database.

``geolocate.anomaly.wifi_country_mismatch`` : counter

    Counts any wifi-based geolocation query where the wifi stored in the
    database was located outside the country inferred from GeoIP and/or
    cell MCC.

``geolocate.anomaly.multiple_mccs`` : counter

    Counts any cell-based geolocation query where multiple cells were
    measured and the cells appear in more than a single MCC. This may
    happen somewhat frequently in border areas.

In addition to geolocate anomaly counters, equivalent counters exist for
the ``search`` and ``geosubmit`` API endpoints. These are named:

  - ``search.anomaly.cell_lac_country_mismatch``
  - ``search.anomaly.geoip_mcc_mismatch``
  - ``search.anomaly.wifi_cell_lac_mismatch``
  - ``search.anomaly.wifi_cell_lac_mismatch``
  - ``search.anomaly.multiple_mccs``
  - ``geosubmit.anomaly.cell_lac_country_mismatch``
  - ``geosubmit.anomaly.geoip_mcc_mismatch``
  - ``geosubmit.anomaly.wifi_cell_lac_mismatch``
  - ``geosubmit.anomaly.wifi_cell_lac_mismatch``
  - ``geosubmit.anomaly.multiple_mccs``

Their meanings are identical to those specified above for the ``geolocate``
API.


Accuracy pseudo-timers
----------------------

Each query sent to a location-search API endpoint -- ``search``,
``geolocate`` or ``geosubmit`` -- results in a location and an estimated
*accuracy*, measuring an approximate radius (in meters) around the location
in which Ichnaea thinks the user is located.

These accuracy values are emitted as *timer metrics*, despite not actually
representing an elapsed time value. This overloading of the concept of
"timer" to convey some other scalar quantity like "meters" is a common
idiom in metric reporting pipelines, in order to measure the min, max, mean
and 90th-percentile aggregate functions.

Therefore the following "pseudo-timers" exist, reporting the accuracy of
cell, cell LAC, GeoIP and wifi-based responses:

  - ``geolocate.accuracy.cell``
  - ``geolocate.accuracy.cell_lac``
  - ``geolocate.accuracy.geoip``
  - ``geolocate.accuracy.wifi``
  - ``geosubmit.accuracy.cell``
  - ``geosubmit.accuracy.cell_lac``
  - ``geosubmit.accuracy.geoip``
  - ``geosubmit.accuracy.wifi``
  - ``search.accuracy.cell``
  - ``search.accuracy.cell_lac``
  - ``search.accuracy.geoip``
  - ``search.accuracy.wifi``


Submit counters
---------------

The ``submit`` and ``geosubmit`` APIs have an additional counter each,
``submit.geoip_mismatch`` and ``geosubmit.geoip_mismatch``.  This metric
counts submissions that are discarded on arrival due to a mismatch between
the submission's claimed location (a ``lat``/``lon`` pair) and the country
the submission was sent from, as determined by GeoIP lookup.


Fine-grained ingress counters
-----------------------------

When a set of measurements is accepted at one of the submission API
endpoints, it is decomposed into a number of "items" -- wifi or cell
measurements -- each of which then works its way through a process of
normalization, consistency-checking, rate limiting and eventually
(possibly) integration into aggregate station estimates held in the main
database tables. Along the way several counters measure the steps involved:

``items.uploaded.batches`` : counter

    Counts the number of "batches" of measures accepted to the
    item-processing pipeline by an API endpoint. A batch generally
    corresponds to the set of items uploaded in a single HTTP POST to the
    ``submit`` or ``geosubmit`` APIs, but if an exceptionally large POST is
    made it may be broken into multiple batches to make further processing
    more granular. In other words this metric counts "submissions that make
    it past coarse-grained checks" such as API-key, JSON schema validity
    and GeoIP checking.

``items.uploaded.cell_measures``, ``items.uploaded.wifi_measures`` : counters

    Count the number of cell or wifi measures entering the item-processing
    pipeline; before normalization, blacklist processing and rate limiting
    have been applied. In other words this metric counts "total cell or wifi
    measurements inside each submitted batch", as each batch is decomposed
    into individual measurements.


``items.dropped.cell_ingress_malformed``, ``items.dropped.wifi_ingress_malformed`` : counters

    Count incoming cell or wifi measurements that were discarded before
    integration due to some internal consistency, range or
    validity-condition error encountered while attempting to normalize the
    measurement.

``items.dropped.cell_ingress_overflow``, ``items.dropped.wifi_ingress_overflow`` : counters

    Count incoming cell or wifi measurements that were discarded before
    integration due to the rate of arrival of new records exceeding a
    threshold of new records per period of time. The rate limiting is done
    per-station, in other words only those measurements pertaining to a
    cell or wifi that already has "too many" recent measurements are
    discarded, and only the newest measurements are discarded.

``items.blacklisted.cell_moving``, ``items.blacklisted.wifi_moving`` : counters

    Count any cell or wifi that is blacklisted due to the acceptance of
    multiple measurements at sufficiently different locations. In these
    cases, Ichnaea decides that the station is "moving" (such as a picocell
    or mobile hotspot on a public transit vehicle) and blacklists it, to
    avoid estimating query positions using the station.

``items.inserted.cell_measures``, ``items.inserted.wifi_measures`` : counters

    Count cell or wifi measurements that are successfully normalized and
    integrated, not discarded due to rate limits or consistency errors.

``items.dropped.cell_trim_excessive``, ``items.dropped.wifi_trim_excessive`` : counters

    Count *old* cell or wifi measurements that were discarded from the
    database due to a periodic trimming task. Measurements are counted and
    discarded per-station, in other words only those measurements
    pertaining to a cell or wifi that already has "too many" measurements
    are discarded, and only the oldest measurements are discarded.


S3 backup counters
------------------

Ichnaea contains logic for backing up and optionally trimming large
measurement tables to S3 or similar bulk storage systems. When such backup
events occur, some associated counters are emitted:

``s3.backup.cell``, ``s3.backup.wifi`` : counters

    Counts the number of cell or wifi measures that have been backed up.


HTTP counters
-------------

Every legitimate, routed request to Ichnaea, whether to an API endpoint or
to static content, also increments an ``http.request.*`` counter. The path
of the counter is the based on the path of the HTTP request, with slashes
replaced with periods, followed by a final component named by the response
code produced by the request.

For example, a GET of ``/leaders/weekly`` that results in an HTTP 200
status code, will increment the counter
``http.request.leaders.weekly.200``.

Response codes in the 400 range (eg. 404) are only generated for HTTP paths
referring to API endpoints; for static content, no counter is incremented on
404 (since such requests do not refer to legitimate paths).


HTTP timers
-----------

In addition to the HTTP counters, every legitimate, routed request to
Ichnaea emits an ``http.request.*`` *timer*. These timers have the same
name structure as the HTTP counters, except they do not have a final
component based on the response code. Rather, they aggregate over all
response codes for a given HTTP path.


Task timers
-----------

Ichnaea's ingress and data-maintenance actions are managed by a Celery
queue of *tasks*. These tasks are executed asynchronously, and each task
emits a timer indicating its execution time.

The following timers exist for tasks, but in general they are of less
interest than user-facing timers or counters; they merely indicate the
internal pauses and work-granularity of asynchronous processing within the
system:

  - ``task.backup.delete_cellmeasure_records``
  - ``task.backup.delete_wifimeasure_records``
  - ``task.backup.dispatch_delete``
  - ``task.backup.schedule_cellmeasure_archival``
  - ``task.backup.schedule_wifimeasure_archival``
  - ``task.backup.write_block_to_s3``
  - ``task.backup.write_cellmeasure_s3_backups``
  - ``task.backup.write_wifimeasure_s3_backups``
  - ``task.cell_location_update``
  - ``task.cell_trim_excessive_data``
  - ``task.content.cell_histogram``
  - ``task.content.unique_cell_histogram``
  - ``task.content.unique_wifi_histogram``
  - ``task.content.wifi_histogram``
  - ``task.remove_cell``
  - ``task.remove_wifi``
  - ``task.scan_lacs``
  - ``task.service.submit.insert_cell_measures``
  - ``task.service.submit.insert_measures``
  - ``task.service.submit.insert_wifi_measures``
  - ``task.update_lac``
  - ``task.wifi_location_update``
  - ``task.wifi_trim_excessive_data``
