.. _metrics:

===========================
Metrics and Structured Logs
===========================

Ichnaea provides two classes of runtime data:

* Statsd-style **Metrics**, for real-time monitoring and easy visual analysis of trends
* **Structured Logs**, for offline analysis of data and targeted custom reports

Structured logs were added in 2020, and the migration of data from metrics to
logs is not complete. For more information, see the Implementation_ section.

Metrics are emitted by the web / API application, the backend task application,
and the datamaps script:

================================ ======== ======= =======================================================
Metric Name                      App      Type    Tags
================================ ======== ======= =======================================================
`api.limit`_                     task     gauge   key, path
`data.batch.upload`_             web      counter key
`data.export.batch`_             task     counter key
`data.export.upload`_            task     counter key, status
`data.export.upload.timing`_     task     timer   key
`data.observation.drop`_         task     counter type, key
`data.observation.insert`_       task     counter type
`data.observation.upload`_       task     counter type, key
`data.report.drop`_              task     counter key
`data.report.upload`_            task     counter key
`data.station.blocklist`_        task     counter type
`data.station.confirm`_          task     counter type
`data.station.dberror`_          task     counter type, errno
`data.station.new`_              task     counter type
`datamaps.dberror`_              task     counter errno
`locate.fallback.cache`_         web      counter fallback_name, status
`locate.fallback.lookup`_        web      counter fallback_name, status
`locate.fallback.lookup.timing`_ web      timer   fallback_name, status
`locate.query`_                  web      counter key, geoip, blue, cell, wifi
`locate.request`_                web      counter key, path
`locate.result`_                 web      counter key, accuracy, status, source, fallback_allowed
`locate.source`_                 web      counter key, accuracy, status, source
`locate.user`_                   task     gauge   key, interval
`queue`_                         task     gauge   data_type, queue, queue_type
`rate_control.locate`_           task     gauge
`rate_control.locate.dterm`_     task     gauge
`rate_control.locate.iterm`_     task     gauge
`rate_control.locate.kd`_        task     gauge
`rate_control.locate.ki`_        task     gauge
`rate_control.locate.kp`_        task     gauge
`rate_control.locate.pterm`_     task     gauge
`region.query`_                  web      counter key, geoip, blue, cell, wifi
`region.request`_                web      counter key, path
`region.result`_                 web      counter key, accuracy, status, source, fallback_allowed
`region.user`_                   task     gauge   key, interval
`request`_                       web      counter path, method, status
`request.timing`_                web      timer   path, method
`submit.request`_                web      counter key, path
`submit.user`_                   task     gauge   key, interval
`task`_                          task     timer   task
================================ ======== ======= =======================================================

Web Application Metrics
=======================
The website handles HTTP requests, which may be page requests or API calls.

Request Metrics
---------------
Each HTTP request, including API calls, emits metrics and a structured log entry.

request
^^^^^^^
``request`` is a counter for almost all HTTP requests, including API calls. The
exceptions are static assets, like CSS, images, Javascript, and fonts, as well as
some static content like ``robots.txt``.

Additionally, invalid requests (HTTP status in the ``4xx`` range) do not omit this
metric, unless they are API endpoints.

The ``path`` tag is the request path, like ``/stats/regions``, but normalized
to tag-safe characters.  The initial slash is dropped, and remaining slashes
are replaced with periods, so ``/stats/regions`` becomes ``stats.regions``.
The homepage, ``/`` is normalized as ``.homepage``, to avoid an empty tag
value.

Tags:

* ``path``: The metrics-normalized HTTP path, like ``stats.regions``,
  ``v1.geolocate``, and ``.homepage``
* ``method``: The HTTP method in lowercase, like ``post``, ``get``, ``head``,
  and ``options``
* ``status``: The returned HTTP status, like ``200`` for success and ``400``
  for client errors

Related structured log data:

* `http_method`_: The non-normalized HTTP method
* `http_path`_: The non-normalized request path
* `http_status`_: The HTTP status code

request.timing
^^^^^^^^^^^^^^
``request.timing`` is a timer for how long the HTTP request took to complete in
milliseconds.

Tags:

The tags ``path`` and ``method`` are the same as `request`_. The tag ``status``
is omitted.

Related structured log data:

* `duration_s`_: The time the request took in seconds, rounded to the millisecond

API Metrics
-----------
These metrics are emitted when the API is called.

data.batch.upload
^^^^^^^^^^^^^^^^^
``data.batch.upload`` is a counter that is incremented when a submit API, like
:ref:`/v2/geosubmit <api_geosubmit2>`, is called with any valid data. A
submission batch could contain a single report or multiple reports, but both
would increment ``data.batch.upload`` by one. A batch with no (valid) reports
does not increment this metric.

Tags:

* ``key``: The API key, often a UUID, or omitted if the API key is not valid.

Related structured log data:

* `api_key`_: The same value as tag ``key`` for valid keys

locate.query
^^^^^^^^^^^^
``locate.query`` is a counter, incremented each time the
:ref:`Geolocate API <api_geolocate_latest>` is used with a valid API key that
is not rate limited. It is used to segment queries by the station data
contained in the request body.

Tags:

* ``key``: The API key, often a UUID
* ``geoip``: ``false`` if there was no GeoIOP data, and omitted when there is
  GeoIP data for the client IP (the common case)
* ``blue``: Count of valid Bluetooth :term:`stations` in the request, ``none``, ``one``
  or ``many``
* ``cell``: Count of valid cell :term:`stations` in the request, ``none``, ``one``, or
  ``many``
* ``wifi``: Count of valid WiFi :term:`stations` in the request, ``none``, ``one``, or
  ``many``

.. versionchanged:: 2020.04.16
   Removed the ``region`` tag

Related structured log data:

* `api_key`_: The same value as tag ``key``
* `has_geoip`_: Always set, ``False`` when ``geoip`` is ``false``
* `blue`_: Count of Bluetooth stations, as a number instead of text like ``many``
* `cell`_: Count of Cell stations
* `wifi`_: Count of WiFi stations

locate.request
^^^^^^^^^^^^^^
``locate.request`` is a counter, incremented for each call to the
:ref:`Geolocate API <api_geolocate_latest>`.

Tags:

* ``key``: The API key, often a UUID, or ``invalid`` for a known key that can
  not call the API, or ``none`` for an omitted key.
* ``path``: ``v1.geolocate``, the standardized API path

Related structured log data:

* `api_key`_: The same value as tag ``key``, except that instead of ``invalid``,
  the request key is used, and ``api_key_allowed=False``
* `api_key_allowed`_: ``False`` when the key is not allowed to use the API
* `api_path`_: The same value as tag ``path``
* `api_type`_: The value ``locate``

locate.result
^^^^^^^^^^^^^
``locate.result`` is a counter, incremented for each call to the
:ref:`Geolocate API <api_geolocate_latest>` with a valid API key that is not
rate limited.

If there are no Bluetooth, Cell, or WiFi networks provided, and GeoIP data is
not available (for example, the IP fallback is explicitly disabled), then this
metric is not emitted.

Tags:

* ``key``: The API key, often a UUID
* ``accuracy``: The expected accuracy, based on the sources provided:

  - ``high``: At least two Bluetooth or WiFi networks
  - ``medium``: No Bluetooth or WiFi networks, at least one cell network
  - ``low``: No networks, only GeoIP data

* ``status``: Could we provide a location estimate?

  - ``hit`` if we can provide a location with the expected accuracy,
  - ``miss`` if we can not provide a location with the expected accuracy.
    For cell networks (``accuracy=medium``), a ``hit`` includes the case
    where there is not an exact cell match, but the cell area (the area
    covered by related cells) is small enough (smaller than tens of
    kilometers across) for an estimate.

* ``source``: The source that provided the hit:

  - ``internal``: Our crowd-sourced network data
  - ``geoip``: The MaxMind GeoIP database
  - ``fallback``: An optional external fallback provider
  - Omitted when ``status=miss``

* ``fallback_allowed``:

  - ``true`` if the external fallback provider was allowed
  - Omitted if the external fallback provider was not allowed

.. versionchanged:: 2020.04.16
   Removed the ``region`` tag

Related structured log data:

* :ref:`accuracy <accuracy_metric>`: The accuracy level of the result, ``high``,
  ``medium``, or ``low``
* `accuracy_min`_: The same value as tag ``accuracy``
* `api_key`_: The same value as tag ``key``
* `result_status`_: The same value as tag ``status``

locate.source
^^^^^^^^^^^^^
``locate.source`` is a counter, incremented for each processed source in
a location query. If :term:`station` data (Bluetooth, WiFi, and Cell data)
is provided, this usually two metrics for one request, one for the
``internal`` source and one for the ``geoip`` source.

The required accuracy for a ``hit`` is set by the kind of station data in the
request. For example, a request with no station data requires a ``low``
accuracy, while one with multiple WiFi networks requires a ``high`` accuracy.
The ``high`` accuracy is at least 500 meters, and the minimum current MaxMind
accuracy is 1000 meters, so the ``geoip`` source is expected to have a ``miss``
status when accuracy is ``high``.

Tags (similar to `locate.result`_) :

* ``key``: The API key, often a UUID
* ``accuracy``: The expected accuracy, based on the sources provided:

  - ``high``: At least two Bluetooth or WiFi networks
  - ``medium``: No Bluetooth or WiFi networks, at least one cell network
  - ``low``: No networks, only GeoIP data

* ``status``: Could we provide a location estimate?

  - ``hit``: We can provide a location with the expected accuracy,
  - ``miss``: We can not provide a location with the expected accuracy

* ``source``: The source that was processed:

  - ``internal``: Our crowd-sourced network data
  - ``geoip``: The MaxMind GeoIP database
  - ``fallback``: An optional external fallback provider

* ``fallback_allowed``:

  - ``true`` if the external fallback provider was allowed
  - Omitted if the external fallback provider was not allowed

.. versionchanged:: 2020.04.16
   Removed the ``region`` tag

Related structured log data:

* `api_key`_: The same value as tag ``key``
* `source_internal_accuracy`_: The accuracy level of the internal source
* `source_internal_accuracy_min`_: The required accuracy level of the internal
  source, same value as tag ``accuracy`` when ``source=internal``
* `source_internal_status`_: The same value as tag ``status`` when ``source=internal``
* `source_geoip_accuracy`_: The accuracy level of the GeoIP source
* `source_geoip_accuracy_min`_: The required accuracy level of the GeoIP source,
  same value as tag ``accuracy`` when ``source=geoip``
* `source_geoip_status`_: The same value as tag ``status`` when ``source=geoip``
* `source_fallback_accuracy`_: The accuracy level of the external fallback source
* `source_fallback_accuracy_min`_: The required accuracy level of the fallback source,
  same value as tag ``accuracy`` when ``source=fallback``
* `source_fallback_status`_: The same value as tag ``status`` when ``source=fallback``

region.query
^^^^^^^^^^^^
``region.query`` is a counter, incremented each time the
:ref:`Region API <api_region_latest>` is used with a valid API key. It is used
to segment queries by the station data contained in the request body.

It has the same tags (``key``, ``geoip``, ``blue``, ``cell``, and ``wifi``) as
`locate.query`_.

region.request
^^^^^^^^^^^^^^
``region.request`` is a counter, incremented for each call to the
:ref:`Region API <api_region_latest>`.

It has the same tags (``key`` and ``path``) as `locate.request`_, except the
``path`` tag is ``v1.country``, the standardized API path.

region.result
^^^^^^^^^^^^^
``region.result`` is a counter, incremented for each call to the
:ref:`Region API <api_region_latest>` with a valid API key that is not
rate limited.

If there are no Bluetooth, Cell, or WiFi networks provided, and GeoIP data is
not available (for example, the IP fallback is explicitly disabled), then this
metric is not emitted.

It has the same tags (``key``, ``accuracy``, ``status``, ``source``, and
``fallback_allowed``) as `locate.result`_.

region.source
^^^^^^^^^^^^^
``region.source`` is a counter, incremented for each processed source in
a region query. If :term:`station` data (Bluetooth, WiFi, and Cell data)
is provided, this usually two metrics for one request, one for the
``internal`` source and one for the ``geoip`` source. In practice, most
users provide no station data, and only the ``geoip`` source is emitted.

It has the same tags (``key``, ``accuracy``, ``status``, ``source``, and
``fallback_allowed``) as `locate.source`_.

submit.request
^^^^^^^^^^^^^^
``submit.request`` is a counter, incremented for each call to a Submit API:

* :ref:`api_geosubmit_latest`
* :ref:`api_submit`
* :ref:`api_geosubmit`

This counter can be used to determine when the deprecated APIs can be removed.

It has the same tags (``key`` and ``path``) as `locate.request`_, except the
``path`` tag is ``v2.geosubmit``, ``v1.submit``, or ``v1.geosubmit``, the
standardized API path.

API Fallback Metrics
--------------------
These metrics were emitted when the fallback location provider was called.  MLS
stopped using this feature in 2019, so these metrics are not emitted, but the
code remains as of 2020.

These metrics have not been converted to structured logs.

locate.fallback.cache
^^^^^^^^^^^^^^^^^^^^^
``locate.fallback.cache`` is a counter for the performance of the fallback cache.

Tags:

* ``fallback_name``: The name of the external fallback provider, from the API
  key table
* ``status``: The status of the fallback cache:

  - ``hit``: The cache had a previous result for the query
  - ``miss``: The cache did not have a previous result for the query
  - ``bypassed``: The cache was not used, due to mixed :term:`stations` in
    the query, or the high number of individual stations
  - ``inconsistent``: The cached results were for multiple inconsistent
    locations
  - ``failure``: The cache was unreachable

locate.fallback.lookup
^^^^^^^^^^^^^^^^^^^^^^
``locate.fallback.lookup`` is a counter for the HTTP response codes returned
from the fallback server.

Tags:

* ``fallback_name``: The name of the external fallback provider, from the API
  key table
* ``status``: The HTTP status code, such as ``200``

locate.fallback.lookup.timing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
``locate.fallback.lookup.timing`` is a timer for the call to the fallback
location server.

Tags:

* ``fallback_name``: The name of the external fallback provider, from the API
  key table
* ``status``: The HTTP status code, such as ``200``

Web Application Structured Logs
===============================
There is one structured log emitted for each request, which may be an API
request. The structured log data includes data that was emitted as one or more
metrics.

.. _duration_s:
.. _http_method:
.. _http_path:
.. _http_status:

Request Metrics
---------------
All requests, with the exception of static assets and static views (see `request`_),
include this data:

* ``duration_s``: The time in seconds, rounded to the millisecond, to serve the request.
* ``http_method``: The HTTP method, like ``POST`` or ``GET``.
* ``http_path``: The request path, like ``/`` for the homepage, or
  ``/v1/geolocate`` for the API.
* ``http_status``: The response status, like ``200`` or ``400``.

This data is duplicated in metrics:

* `request`_
* `request.timing`_

.. _accuracy_metric:
.. _accuracy_min:
.. _api_key:
.. _api_key_allowed:
.. _api_key_db_fail:
.. _api_path:
.. _api_response_sig:
.. _api_type:
.. _blue:
.. _blue_valid:
.. _cell:
.. _cell_valid:
.. _fallback_allowed:
.. _has_geoip:
.. _has_ip:
.. _invalid_api_key:
.. _rate_allowed:
.. _rate_quota:
.. _rate_remaining:
.. _region:
.. _result_status:
.. _source_fallback_accuracy:
.. _source_fallback_accuracy_min:
.. _source_fallback_status:
.. _source_geoip_accuracy:
.. _source_geoip_accuracy_min:
.. _source_geoip_status:
.. _source_internal_accuracy:
.. _source_internal_accuracy_min:
.. _source_internal_status:
.. _wifi:
.. _wifi_valid:

API Metrics
-----------
If a request is an API call, additional data can be added to the log:

* ``accuracy``: The accuracy of the result, ``high``, ``medium``, or ``low``.
* ``accuracy_min``: The minimum required accuracy of the result for a hit, ``high``,
  ``medium``, or ``low``.
* ``api_key``: An API key that has an entry in the API key table, often a UUID,
  or ``none`` if omitted. Same as statsd tag ``key``, except that known but
  disallowed API keys are the key value, rather than ``invalid``.
* ``api_key_allowed``: ``False`` if a known API key is not allowed to call the
  API, omitted otherwise.
* ``api_key_db_fail``: ``True`` when a database error prevented checking the
  API key. Omitted when the check is successful.
* ``api_path``: The normalized API path, like ``v1.geolocate`` and
  ``v2.geosubmit``. Same as statsd tag ``path`` when an API is called.
* ``api_response_sig``: A hash to identify repeated geolocate requests getting
  the same response without identifying the client.
* ``api_type``: The API type, ``locate``, ``submit``, or ``region``.
* ``blue``: The count of Bluetooth radios in the request.
* ``blue_valid``: The count of valid Bluetooth radios in the request.
* ``cell``: The count of cell tower radios in the request.
* ``cell_valid``: The count of valid cell tower radios in the request.
* ``fallback_allowed``: ``True`` if the optional fallback location provider can
  be used by this API key, ``False`` if not.
* ``has_geoip``: ``True`` if there is GeoIP data for the client IP, otherwise
  ``False``.
* ``has_ip``: ``True`` if the client IP was available, otherwise ``False``.
* ``invalid_api_key``: The invalid API key not found in API table, omitted if known or empty.
* ``rate_allowed``: ``True`` if allowed, ``False`` if not allowed due to rate
  limit, or omitted if the API is not rate-limited.
* ``rate_quota``: The daily rate limit, or omitted if API is not rate-limited.
* ``rate_remaining``: The remaining API calls to hit limit, 0 if none remaining, or
  omitted if the API is not rate-limited.
* ``region``: The ISO region code for the IP address, ``null`` if none.
* ``result_status``: ``hit`` if an accurate estimate could be made, ``miss`` if
  it could not.
* ``source_fallback_accuracy``: The accuracy level of the external fallback
  source, ``high``, ``medium``, or ``low``.
* ``source_fallback_accuracy_min``: The required accuracy level of the fallback source.
* ``source_fallback_status``: ``hit`` if the fallback source provided an accurate
  estimate, ``miss`` if it did not.
* ``source_internal_accuracy``: The accuracy level of the internal source (Bluetooth,
  WiFi, and cell data compared against the database), ``high``, ``medium``, or ``low``.
* ``source_internal_accuracy_min``: The required accuracy level of the internal source.
* ``source_internal_status``: ``hit`` if the internal check provided an accurate
  estimate, ``miss`` if it did not.
* ``source_geoip_accuracy``: The accuracy level of the GeoIP source, ``high``,
  ``medium``, or ``low``.
* ``source_geoip_accuracy_min``: The required accuracy level of the GeoIP source.
* ``source_geoip_status``: ``hit`` if the GeoIP database provided an accurate
  estimate, ``miss`` if it did not.
* ``wifi``: The count of WiFi radios in the request.
* ``wifi_valid``: The count of valid WiFi radios in the request.

Some of this data is duplicated in metrics:

* `api.limit`_
* `locate.query`_
* `locate.request`_
* `locate.result`_
* `locate.source`_
* `region.query`_
* `region.request`_
* `region.result`_
* `region.source`_
* `submit.request`_

Task Application Metrics
========================
The task application, running on celery in the backend, implements the data
pipeline and other periodic tasks. These emit metrics, but have not been
converted to structured logging.

API Monitoring Metrics
----------------------
These metrics are emitted periodically to monitor API usage. A Redis key is
incremented or updated during API requests, and the current value is reported
via these metrics:

api.limit
^^^^^^^^^
``api.limit`` is a gauge of the API requests, segmented by API key and API
path, for keys with daily limits. It is updated every 10 minutes.

Tags:

* ``key``: The API key, often a UUID
* ``path``: The normalized API path, such as ``v1.geolocate`` or ``v2.geosubmit``

Related structured log data is added during the request when an API key has
rate limits:

* `rate_allowed`_: ``True`` if the request was allowed, ``False`` if not allowed
  due to the rate limit
* `rate_quota`_: The daily rate limit
* `rate_remaining`_: The remaining API calls to hit limit, 0 if none remaining

locate.user
^^^^^^^^^^^
``locate.user`` is a gauge of the estimated number of daily and weekly users of
the :ref:`Geolocate API <api_geolocate_latest>` by API key. It is updated
every 10 minutes.

The estimate is based on the client's IP address. At request time, the IP is
added via PFADD_ to a HyperLogLog structure. This structure can be used to
estimate the cardinality (number of unique IP addresses) to within about 1%.
See PFCOUNT_ for details on the HyperLogLog implementation.

.. _PFADD: https://redis.io/commands/pfadd
.. _PFCOUNT: https://redis.io/commands/pfcount

Tags:

* ``key``: The API key, often a UUID
* ``interval``: ``1d`` for the daily estimate, ``7d`` for the weekly estimate.

region.user
^^^^^^^^^^^
``region.user`` is a gauge of the estimated number of daily and weekly users of
the :ref:`Region API <api_region_latest>` by API key. It is updated every 10
minutes.

It has the same tags (``key`` and ``interval``) as `locate.user`_.

submit.user
^^^^^^^^^^^
``submit.user`` is a gauge of the estimated number of daily and weekly users of
the submit APIs (:ref:`/v2/geosubmit <api_geosubmit2>` and the
deprecated submit APIs) by API key. It is updated every 10 minutes.

It has the same tags (``key`` and ``interval``) as `locate.user`_.

Data Pipeline Metrics - Gather and Export
-----------------------------------------
The data pipeline processes data from two sources:

* **Submission reports**, from the submission APIs, which include a position from
  an external source like GPS, along with the Wifi, Cell, and Bluetooth
  :term:`stations` that were seen.
* **Location queries**, from the geolocate and region APIs, which include an
  estimated position, along with the stations.

Multiple reports can be submitted in one call to the submission APIs. Each batch
of reports increment the `data.batch.upload`_ metric when the API is called. A
single report is created for each location query, and there is no corresponding
metric.

The APIs feed these :term:`reports` into a Redis queue ``update_incoming``,
processed by the backend task of the same name. This task copies reports to
"export" queues. Four types are supported:

* ``dummy``: Does nothing, for pipeline testing
* ``geosubmit``: POST reports to a service supporting the
  :ref:`Geosubmit API <api_geosubmit_latest>`.
* ``internal``: Divide :term:`reports` into :term:`observations`,
  for further processing to update the internal database.
* ``s3``: Store report JSON in S3.

Ichnaea supports multiple export targets for a type. In production,
there are three export targets, identified by an export key:

* ``backup``: An ``s3`` export, to a Mozilla-private S3 bucket
* ``tostage``: A ``geosubmit`` export, to send a sample of reports to
  stage for integration testing.
* ``internal``: An ``internal`` export, to update the database

The data pipeline has not been converted to structured logging. As data
moves through this part of the data pipeline, these metrics are emitted:

data.export.batch
^^^^^^^^^^^^^^^^^
``data.export.batch`` is a counter of the report batches exported to external
and internal targets.

Tags:

* ``key``: The export key, from the export table. Keys used in Mozilla
  production:

  - ``backup``: Reports archived in S3
  - ``tostage``: Reports sent from production to stage, as a form of integration testing
  - ``internal``: Reports queued for processing to update the internal station database

data.export.upload
^^^^^^^^^^^^^^^^^^
``data.export.upload`` is a counter that tracks the status of export jobs.

Tags:

* ``key``: The export key, from the export table. Keys used in Mozilla
  production are ``backup`` and ``tostage``, with the same meaning as
  data.export.batch_. Unlike that metric, ``internal`` is not used.
* ``status``: The status of the export, which varies by type of export:

  - ``backup``: ``success`` or ``failure`` storing the report to S3
  - ``tostage``: HTTP code returned by the submission API, usually ``200`` for
    success or ``400`` for failure.

data.export.upload.timing
^^^^^^^^^^^^^^^^^^^^^^^^^
``data.export.upload.timing`` is a timer for the report batch export process.

Tags:

* ``key``: The export key, from the export table. See data.export.batch_ for
  the values used in Mozilla production.

data.observation.drop
^^^^^^^^^^^^^^^^^^^^^
``data.observation.drop`` is a counter of the Bluetooth, cell, or WiFi
:term:`observations` that were discarded before integration due to some
internal consistency, range or validity-condition error encountered while
attempting to normalize the observation.

Tags:

* ``key``: The API key, often a UUID. Omitted if unknown or not available
* ``type``: The :term:`station` type, one of ``blue``, ``cell``, or ``wifi``

data.observation.upload
^^^^^^^^^^^^^^^^^^^^^^^
``data.observation.upload`` is a counter of the number of Bluetooth, cell or
WiFi :term:`observations` entering the data processing pipeline, before
normalization and blocked station processing. This count is taken after a batch
of :term:`reports` are decomposed into observations.

The tags (``key`` and ``type``) are the same as `data.observation.drop`_.

data.report.drop
^^^^^^^^^^^^^^^^
``data.report.drop`` is a counter of the :term:`reports` discarded due to
some internal consistency, range, or validity-condition error.

Tags:

* ``key``: The API key, often a UUID. Omitted if unknown or not available

data.report.upload
^^^^^^^^^^^^^^^^^^
``data.report.upload`` is a counter of the :term:`reports` accepted into the data
processing pipeline.

It has the same tag (``key``) as `data.report.drop`_.

Data Pipeline Metrics - Update Internal Database
------------------------------------------------
The internal export process decomposes :term:`reports` into
:term:`observations`, pairing one position with one :term:`station`. Each
observation works its way through a process of normalization,
consistency-checking, and (possibly) integration into the database, to improve
future location estimates.

The data pipeline has not been converted to structured logging. As data moves
through the pipeline, these metrics are emitted:

.. _data.observation.insert-metric:

data.observation.insert
^^^^^^^^^^^^^^^^^^^^^^^
``data.observation.insert`` is a counter of the Bluetooth, cell, or WiFi
:term:`observations` that were successfully validated, normalized, integrated.

Tags:

* ``type``: The :term:`station` type, one of ``blue``, ``cell``, or ``wifi``

data.station.blocklist
^^^^^^^^^^^^^^^^^^^^^^
``data.station.blocklist`` is a counter of the Bluetooth, cell, or WiFi
:term:`stations` that are blocked from being used to estimate positions.
These are added because there are multiple valid :term:`observations` at
sufficiently different locations, supporting the theory that it is a
mobile station (such as a picocell or a mobile hotspot on public transit),
or was recently moved (such as a WiFi base station that moved with the
owner to a new home).

Tags:

* ``type``: The :term:`station` type, one of ``blue``, ``cell``, or ``wifi``

data.station.confirm
^^^^^^^^^^^^^^^^^^^^
``data.station.confirm`` is a counter of the Bluetooth, cell or WiFi
:term:`stations` that were confirmed to still be active. An :term:`observation`
from a location query can be used to confirm a station with a position based
on submission reports.

It has the same tag (``type``) as data.station.blocklist_

data.station.dberror
^^^^^^^^^^^^^^^^^^^^
``data.station.dberror`` is a counter of retryable database errors, which are
encountered as multiple task threads attempt to update the internal database.

Retryable database errors, like a lock timeout (``1205``) or deadlock
(``1213``) cause the station updating task to sleep and start over.  Other
database errors are not counted, but instead halt the task and are recorded in
Sentry.

Tags:

* ``errno``: The error number, which can be found in the 
  `MySQL Server Error Reference`_
* ``type``: The :term:`station`, one of ``blue``, ``cell``, or ``wifi``,
  or the aggregate station type ``cellarea``

.. _`MySQL Server Error Reference`: https://dev.mysql.com/doc/refman/5.7/en/server-error-reference.html

data.station.new
^^^^^^^^^^^^^^^^
``data.station.new`` is a counter of the Bluetooth, cell or WiFi
:term:`stations` that were discovered for the first time.

Tags:

* ``type``: The :term:`station` type, one of ``blue``, ``cell``, or ``wifi``

datamaps.dberror
^^^^^^^^^^^^^^^^
``datamaps.dberror`` is a counter of the number of retryable database errors
when updating the ``datamaps`` tables.

Tags:

* ``errno``: The error number, same as `data.station.dberror`_

Backend Monitoring Metrics
--------------------------

.. _queue-metric:

queue
^^^^^
``queue`` is a gauge that reports the current size of task and data queues.
Queues are implemented as Redis lists, with a length returned by LLEN_.

.. _LLEN: https://redis.io/commands/llen

Task queues hold the backlog of celery async tasks. The names of the task
queues are:

* ``celery_blue``, ``celery_cell``, ``celery_wifi`` - A task to process a chunk
  of :term:`observation` data
* ``celery_content`` - Tasks that update website content, like the datamaps and
  statistics
* ``celery_default`` - A generic task queue
* ``celery_export`` - Tasks exporting data, either public cell data or the
  `Data Pipeline <Data Pipeline Metrics - Gather and Export>`_
* ``celery_monitor`` - Tasks updating metrics gauges for this metric and
  `API Monitoring Metrics`_
* ``celery_reports`` - Tasks handling batches of submission reports or location
  queries

Data queues are the backlog of :term:`observations` and other data items to be
processed.  Data queues have names that mirror the shared database tables:

* ``update_blue_0`` through ``update_blue_f`` (16 total) - Observations of
  Bluetooth stations
* ``update_cell_gsm``, ``update_cell_lte``, and ``update_cell_wcdma`` -
  Observations of cell stations
* ``update_cell_area`` - Aggregated observations of cell towers
  ``data_type: cellarea``
* ``update_datamap_ne``, ``update_datamap_nw``, ``update_datamap_se``, and
  ``update_datamap_sw`` - Approximate locations for the contribution map
* ``update_incoming`` - Incoming reports from geolocate and submission APIs
* ``update_wifi_0`` through ``update_wifi_f`` (16 total) - Observations of
  WiFi stations

Tags:

* ``queue``: The name of the task or data queue
* ``queue_type``: ``task`` or ``data``
* ``data_type``: For data queues, ``bluetooth``, ``cell``, ``cellarea``,
  ``datamap``, ``report`` (queue ``update_incoming``), or ``wifi``. Omitted for
  task queues.

task
^^^^
``task`` is a timer that measures how long each Celery task takes. Celery tasks
are used to implement the data pipeline and monitoring tasks.

Tags:

* ``task``: The task name, such as ``data.export_reports`` or
  ``data.update_statcounter``

.. _rate-control-metrics:

Rate Control Metrics
--------------------

The optional :ref:`rate controller <auto-rate-controller>` can be used to
dynamically set the global locate sample rate and prevent the data queues from
growing without bounds. There are several metrics emitted to monitor the rate
controller.

rate_control.locate
^^^^^^^^^^^^^^^^^^^
``rate_control.locate`` is a gauge that reports the current setting of the
:ref:`global locate sample rate <global-rate-control>`, which may be unset
(100.0), manually set, or set by the rate controller.

rate_control.locate.target
^^^^^^^^^^^^^^^^^^^^^^^^^^
``rate_control.locate.target`` is a gauge that reports the current target queue
size of the rate controller. It is emitted when the rate controller is enabled.

rate_control.locate.kp
^^^^^^^^^^^^^^^^^^^^^^
``rate_control.locate.kp`` is a gauge that reports the current value of
K\ :sub:`p`, the proportional gain. It is emitted when the rate controller is enabled.

rate_control.locate.ki
^^^^^^^^^^^^^^^^^^^^^^
``rate_control.locate.ki`` is a gauge that reports the current value of
K\ :sub:`i`, the integral gain. It is emitted when the rate controller is enabled.

rate_control.locate.kd
^^^^^^^^^^^^^^^^^^^^^^
``rate_control.locate.kd`` is a gauge that reports the current value of K\
:sub:`d`, the derivative gain. It is emitted when the rate controller is
enabled.

rate_control.locate.pterm
^^^^^^^^^^^^^^^^^^^^^^^^^
``rate_control.locate.pterm`` is a gauge that reports the current value of of
the proportional term of the rate controller. It is emitted when the rate
controller is enabled.

rate_control.locate.iterm
^^^^^^^^^^^^^^^^^^^^^^^^^
``rate_control.locate.pterm`` is a gauge that reports the current value of of
the integral term of the rate controller. It is emitted when the rate
controller is enabled.

rate_control.locate.dterm
^^^^^^^^^^^^^^^^^^^^^^^^^
``rate_control.locate.dterm`` is a gauge that reports the current value of of
the derivative term of the rate controller. It is emitted when the rate
controller is enabled.

Datamaps Structured Log
=======================
The datamap script generates a data map from the gathered observations. It does
not emit metrics.

The final ``canonical-log-line`` log entry has this data:

* ``bucket_name``: The name of the S3 bucket
* ``concurrency``: The number of concurrent threads used
* ``create``: True if ``--create`` was set to generate tiles
* ``duration_s``: How long in seconds to run the script
* ``export_duration_s``: How long in seconds to export from tables to CSV
* ``merge_duration_s``: How long in seconds to merge the per-table quadtrees
* ``quadtree_count``: How many per-table quadtrees were generated
* ``quadtree_duration_s``: How long in seconds to convert CSV to quadtrees
* ``render_duration_s``: How long in seconds to render the merged quadtree to tiles
* ``row_count``: The number of rows across datamap tables
* ``script_name``: The name of the script (``ichnaea.scripts.datamap``)
* ``success``: True if the script completed without errors
* ``sync_duration_s``: How long in seconds it took to upload tiles to S3
* ``tile_changed``: How many existing S3 tiles were updated
* ``tile_count``: The total number of tiles generated
* ``tile_deleted``: How many existing S3 tiles were deleted
* ``tile_new``: How many new tiles were uploaded to S3
* ``tile_unchanged``: How many tiles were the same as the S3 tiles
* ``upload``: True if ``--upload`` was set to upload / sync tiles

Much of this data is also found in the file ``tiles/data.json`` in the S3
bucket for the most recent run.

Implementation
==============

Ichnaea emits statsd-compatible metrics using markus_, if the ``STATSD_HOST``
is configured (see :ref:`the config section <config>`). Metrics use the the
tags extension, which add queryable dimensions to the metrics. In development,
the metrics are displayed with the logs. In production, the metrics are stored
in an InfluxDB_ database, and can be displayed as graphs with Grafana_.

.. _markus: https://markus.readthedocs.io/en/latest/
.. _InfluxDB: https://docs.influxdata.com/influxdb/v1.8/
.. _Grafana: https://grafana.com/docs/grafana/latest

Ichnaea also emits structured logs using structlog_.  In development, these are
displayed in a human-friendly format. In production, they use the MozLog_ JSON
format, and the data is stored in BigQuery_.

.. _structlog: https://www.structlog.org/en/stable/
.. _MozLog: https://wiki.mozilla.org/Firefox/Services/Logging
.. _BigQuery: https://cloud.google.com/bigquery/docs/

In the past, metrics were the main source of runtime data, and tags were used
to segment the metrics and provide insights. However, metric tags and their
values were limited to avoid performance issues. InfluxDB and other time-series
databases store metrics by the indexed series of tag values. This performs well
when tags have a small number of unique values, and the combinations of tags
are limited.  When tags have many unique values and are combined, the number of
possible series can explode and cause storage and performance issues (the
"high cardinality" problem).

Metric tag values are limited to avoid high cardinality issues. For example,
rather than storing the number of WiFi stations, the ``wifi`` tag of the
`locate.query`_ metric has the values ``none``, ``one``, and ``many``. The
region, such as ``US`` or ``DE``, was once stored as a tag, but this can have
almost 250 values, causing MLS to have the highest processing load across
Mozilla projects.

BigQuery easily handles high-cardinality data, so structured logs can contain
precise values, such as the actual number of WiFi stations provided, and more
items, such as the region and unexpected keys. On the other hand, there isn't a
friendly tool like Grafana to quickly explore the data.

As of 2020, we are in the process of duplicating data from metrics into
structured logging, expanding the data collected, and creating
dashboards. We'll also remove data from metrics, first to reduce the current
issues around high-cardinality, then to focus metrics on operational data.
Structured data will be used for service analysis and monitoring of long-term
trends, and dashboards created for reference.

