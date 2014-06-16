=======
Metrics
=======

As discussed in `the deployment document <deploy.html>`_, Ichnaea emits
metrics through the Heka client library with the intent of aggregating and
viewing them on a Graphite server.

This document describes the metrics collected.


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

    Counts any geolocation query that included a cell that the database
    does *not* have information about. This counter is mutually exclusive
    with ``geolocate.cell_found``.

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

    Counts any geolocation query that included a cell that the database
    does *not* have information about the corresponding LAC of. This
    counter is mutually exclusive with ``geolocate.cell_lac_found``.

``geolocate.cell_lac_hit`` : counter

    Counts any geolocation query response that was based primarily on a
    cell LAC record. This counter is mutually exclusive with
    ``geolocate.wifi_hit``, ``geolocate.cell_hit``, and
    ``geolocate.geoip_hit``.

``geolocate.wifi_found`` : counter

    Counts any geolocation query that included a wifi that the database has
    information about, whether or not that information was used in the
    response. This counter is mutually exclusive with
    ``geolocate.no_wifi_found``.

``geolocate.no_wifi_found`` : counter

    Counts any geolocation query that included a wifi that the database
    does *not* have information about. This counter is mutually exclusive
    with ``geolocate.wifi_found``.

``geolocate.wifi_hit`` : counter

    Counts any geolocation query response that was based primarily on a
    wifi record. This counter is mutually exclusive with
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
not clear which data is correct or incorrect, merely that two data disagree
on some fact that they "should" agree on. The corrective measure taken is
usually to reduce the estimated accuracy of the result, or discard the data
that suggests higher accuracy in favour of that which suggests lower.

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


Submit counters
---------------

The ``submit`` API has one additional counter, ``submit.geoip_mismatch``.
This metric counts submissions that are discarded on arrival due to a
mismatch between the submission's claimed location (a ``lat``/``lon`` pair)
and the country the submission was sent from, as determined by GeoIP
lookup.


Fine-grained ingress counters
-----------------------------

When a set of measurements is accepted at the ``submit`` API endpoint, it
is decomposed into a number of "items" -- wifi or cell measurements -- each
of which then works its way through a process of normalization,
consistency-checking, rate limiting and eventually (possibly) integration
into aggregate antenna estimates held in the main database tables. Along
the way several counters measure the steps involved:

``items.uploaded.batches`` : counter

    Counts the number of "batches" of measures accepted to the
    item-processing pipeline by an API endpoint. A batch generally
    corresponds to the set of items uploaded in a single HTTP POST to the
    ``submit`` or ``geosubmit`` APIs, but if an exceptionally large POST is
    made it may be broken into multiple batches to make further processing
    more granular. In other words this metric counts "submissions that make
    it past coarse-grained checks" such as API-key, JSON schema validity
    and GeoIP checking.

``items.uploaded.cell_measures`` : counter

    Counts the number of cell measures entering the item-processing
    pipeline; before normalization, blacklist processing and rate limiting
    have been applied. In other words this metric counts "total cell
    measurements inside each submitted batch", as each batch is decomposed
    into individual measurements.

``items.uploaded.wifi_measures`` : counter

    Counts the number of wifi measures entering the item-processing
    pipeline; before normalization, blacklist processing and rate limiting
    have been applied. In other words this metric counts "total wifi
    measurements inside each submitted batch", as each batch is decomposed
    into individual measurements.

``items.dropped.cell_ingress_malformed`` : counter

    Counts incoming cell measurements that were discarded before
    integration due to some internal consistency, range or
    validity-condition error encountered while attempting to normalize the
    measurement.

``items.dropped.wifi_ingress_malformed`` : counter

    Counts incoming wifi measurements that were discarded before
    integration due to some internal consistency, range or
    validity-condition error encountered while attempting to normalize the
    measurement.

``items.dropped.cell_ingress_overflow`` : counter

    Counts incoming cell measurements that were discarded before
    integration due to the rate of arrival of new records exceeding a
    threshold of new records per period of time. The rate limiting is done
    per-cell, in other words only those measurements pertaining to a cell
    that already has "too many" recent measurements are discarded, and only
    the newest measurements are discarded.

``items.dropped.wifi_ingress_overflow`` : counter

    Counts incoming wifi measurements that were discarded before
    integration due to the rate of arrival of new records exceeding a
    threshold of new records per period of time. The rate limiting is done
    per-wifi, in other words only those measurements pertaining to a wifi
    that already has "too many" recent measurements are discarded, and only
    the newest measurements are discarded.

``items.blacklisted.cell_moving`` : counter

    Counts any cell that is blacklisted due to the acceptance of multiple
    measurements at sufficiently different locations. In these cases,
    Ichnaea decides that the cell is "moving" (such as a picocell on a
    public transit vehicle) and blacklists it, to avoid estimating
    query positions using the cell.

``items.blacklisted.wifi_moving`` : counter

    Counts any wifi that is blacklisted due to the acceptance of multiple
    measurements at sufficiently different locations. In these cases,
    Ichnaea decides that the wifi is "moving" (such as a wifi hotspot on a
    public transit vehicle) and blacklists it, to avoid estimating query
    positions using the wifi.

``items.inserted.cell_measures`` : counter

    Counts cell measurements that are successfully normalized and
    integrated, not discarded due to rate limits or consistency errors.

``items.inserted.wifi_measures`` : counter

    Counts wifi measurements that are successfully normalized and
    integrated, not discarded due to rate limits or consistency errors.

``items.dropped.cell_trim_excessive`` : counter

    Counts *old* cell measurements that were discarded from the database
    due to a periodic trimming task. Measurements are discarded per-cell,
    in other words only those measurements pertaining to a cell that
    already has "too many" measurements are discarded, and only the oldest
    measurements are discarded.   

``items.dropped.wifi_trim_excessive`` : counter

    Counts *old* wifi measurements that were discarded from the database
    due to a periodic trimming task. Measurements are discarded per-wifi,
    in other words only those measurements pertaining to a wifi that
    already has "too many" measurements are discarded, and only the oldest
    measurements are discarded.   


S3 backup counters
------------------

Ichnaea contains logic for backing up and optionally trimming large
measurement tables to S3 or similar bulk storage systems. When such backup
events occur, some associated counters are emitted:

``s3.backup.wifi`` : counter

    Counts the number of wifi measures that have been backed up.

``s3.backup.cell`` : counter

    Counts the number of cell measures that have been backed up.


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
