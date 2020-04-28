.. _metrics:

=======
Metrics
=======

.. Note:: 2019-09-24: This needs to be updated.

Ichnaea emits statsd-compatible metrics using markus_, if the ``STATSD_HOST``
is configured (see :ref:`the config section <config>`).

.. _markus: https://markus.readthedocs.io/en/latest/

Most metrics use the the statsd tags extension. A metric
name of ``task#name:function,version:old`` means a statsd metric
called ``task`` will be emitted with two tags ``name:function`` and
``version:old``.

Here's a summary of the metrics emitted by Ichnaea:

================================ ======= =======================================================
Metric Name                      Type    Tags
================================ ======= =======================================================
`api.limit`_                     gauge   key, path
`data.batch.upload`_             counter key
`data.export.batch`_             counter key
`data.export.upload`_            counter key, status
`data.export.upload.timing`_     timer   key
`data.observation.drop`_         counter type, key
`data.observation.insert`_       counter type
`data.observation.upload`_       counter type, key
`data.report.drop`_              counter key
`data.report.upload`_            counter key
`data.station.blocklist`_        counter type
`data.station.confirm`_          counter type
`data.station.dberror`_          counter type, errno
`data.station.new`_              counter type
`datamaps`_                      timer   func, count
`datamaps.dberror`_              counter errno
`locate.fallback.cache`_         counter fallback_name, status
`locate.fallback.lookup`_        counter fallback_name, status
`locate.fallback.lookup.timing`_ timer   fallback_name, status
`locate.query`_                  counter key, geoip, blue, cell, wifi
`locate.request`_                counter key, path
`locate.result`_                 counter key, accuracy, status, source, fallback_allowed
`locate.source`_                 counter key, accuracy, status, source
`locate.user`_                   gauge   key, interval
`queue`_                         gauge   queue
`region.request`_                counter key, path
`region.result`_                 counter key, accuracy, status, source, fallback_allowed
`region.user`_                   gauge   key, interval
`request`_                       counter path, method, status
`request.timing`_                timer   path, method
`submit.request`_                counter key, path
`submit.user`_                   gauge   key, interval
`task`_                          timer   task
================================ ======= =======================================================

.. _locate.request:
.. _region.request:
.. _submit.request:

API Request Metrics
-------------------

These are metrics that track how many times each specific public API
is used and which clients identified by their API keys do so. They are
grouped by the type of the API, where type is one of `locate`, `region`
and `submit`, independent of the specific version of that API.

These metrics can help in deciding when to remove a deprecated API.

``locate.request#path:v1.search,key:<apikey>``,
``locate.request#path:v1.geolocate,key:<apikey>``,
``region.request#path:v1.country,key:<apikey>``,
``submit.request#path:v1.submit,key:<apikey>``,
``submit.request#path:v1.geosubmit,key:<apikey>``,
``submit.request#path:v2.geosubmit,key:<apikey>`` : counters

    These metrics count how many times a specific API was called by a
    specific API key expressed via the API keys short name. The API key
    is the actual API key, often a UUID.

    Two special short names exist for tracking invalid (``invalid``)
    and no (``none``) provided API keys.

.. _locate.user:
.. _region.user:
.. _submit.user:

API User Metrics
----------------

For all API requests including the submit-type APIs we gather metrics
about the number of unique users based on the users IP addresses.

These metrics are gathered under the metric prefix:

``<api_type>.user#key<apikey>`` : gauge

They have an additional tag to determine the time interval for which
the unique users are aggregated for:

``#interval:1d``, ``interval:7d`` : tags

    Unique users per day or last 7 days.

Technically these metrics are based on HyperLogLog cardinality numbers
maintained in a Redis service. They should be accurate to about 1% of
the actual number.

.. _locate.query:

API Query Metrics
-----------------

For each incoming API query we log metrics about the data contained in
the query with the metric name and tag:

``<api_type>.query#key<apikey>`` : counter

`api_type` describes the type of API being used, independent of the
version number of the API. So `v1/country` gets logged as `region`
and both `v1/search` and `v1/geolocate` get logged as `locate`.

We extend the metric with additional tags based on the data contained
in it:

``#geoip:false`` : tag

    This tag only gets added if there was no valid client IP address
    for this query. Since almost all queries contain a client IP address
    we usually skip this tag.

``#blue:none``, ``#blue:one``, ``#blue:many``,
``#cell:none``, ``#cell:one``, ``#cell:many``,
``#wifi:none``, ``#wifi:one``, ``#wifi:many`` : tags

    If the query contained any Bluetooth, cell or WiFi networks,
    one blue, cell and wifi tag get added. The tags depend on the
    number of valid :term:`stations` for each of the three.

.. versionchanged:: 2020.04.unreleased
   Removed the ``region`` tag

.. _locate.result:
.. _region.result:

API Result Metrics
------------------

Similar to the API query metrics we also collect metrics about each
result of an API query. This follows the same per API type and per
region rules under the prefix / tag combination:

``<api_type>.result#key:<apikey>``

The result metrics measure if we satisfied the incoming API query in
the best possible fashion. Incoming queries can generally contain
an IP address, Bluetooth, cell, WiFi networks or any combination thereof.
If the query contained only cell networks, we do not expect to get a
high accuracy result, as there is too little data in the query to do so.

We express this by classifying each incoming query into one of four
categories:

High Accuracy (``#accuracy:high``)
    A query containing at least two Bluetooth or WiFi networks.

Medium Accuracy (``#accuracy:medium``)
    A query containing neither Bluetooth nor WiFi networks but at
    least one cell network.

Low Accuracy (``#accuracy:low``)
    A query containing no networks but only the IP address of the client.

No Accuracy (``#accuracy:none``)
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

For each result we then log exactly one of the following tag combinations:

``#accuracy:high,status:hit``, ``#accuracy:high,status:miss``,
``#accuracy:medium,status:hit``, ``#accuracy:medium,status:miss``,
``#accuracy:low,status:hit``, ``#accuracy:low,status:miss`` : tags

We don't log metrics for the uncommon case of ``none`` or no expected
accuracy.

One special case exists for cell networks. If we cannot find an exact
cell match, we might fall back to a cell area based estimate. If the
range of the cell area is fairly small we consider this to be a
``#accuracy:medium,status:hit``. But if the size of the cell area is
extremely large, in the order of tens of kilometers to hundreds of
kilometers, we consider it to be a ``#accuracy:medium,status:miss``.

In the past we only collected stats based on whether or not cell based
data was used to answer a cell based query and counted it as a
cell-based success, even if the provided accuracy was really bad.

In addition to the accuracy of the result, we also tag the result
metric with the data source that got used to provide the result,
but only for results that met the expected accuracy.

``#source:<source_name>`` : tag

Data sources can be one of:

``internal``
    Data from our own crowd-sourcing effort.

``fallback``
    Data from the optional external fallback provider.

``geoip``
    Data from a GeoIP database.

And finally we add a tag to state whether or not the query was allowed
to use the fallback source.

``#fallback_allowed:<value>`` : tag

    The value is either `true` or `false`.

.. versionchanged:: 2020.04.unreleased
   Removed the ``region`` tag

.. _locate.source:

API Source Metrics
------------------

In addition to the final API result, we also collect metrics about each
individual data source we use to answer queries under the
``<api_type>.source#key:<apikey>`` metric.

Each request may use one or multiple of these sources to deliver a result.
We log the same metrics as mentioned above for the result.

All of this combined might lead to a tagged metric like:

``locate.source#key:test,source:geoip,accuracy:low,status:hit``

.. versionchanged:: 2020.04.unreleased
   Removed the ``region`` tag

.. _locate.fallback.cache:
.. _locate.fallback.lookup:
.. _locate.fallback.lookup.timing:

API Fallback Source Metrics
---------------------------

The external fallback source has a couple extra metrics to observe the
performance of outbound network calls and the effectiveness of its cache.

The fallback name tag specifies which fallback service is used.

``locate.fallback.cache#fallback_name:<fallback_name>,status:hit``,
``locate.fallback.cache#fallback_name:<fallback_name>,status:miss``,
``locate.fallback.cache#fallback_name:<fallback_name>,status:bypassed``,
``locate.fallback.cache#fallback_name:<fallback_name>,status:inconsistent``,
``locate.fallback.cache#fallback_name:<fallback_name>,status:failure`` : counter

    Counts the number of hits and misses for the fallback cache. If
    the query should not be cached, a `bypassed` status is used.
    If the cached values couldn't be read, a `failure` status is used.
    If the cached values didn't agree on a consistent position,
    a `inconsistent` status is used.

``locate.fallback.lookup.timing#fallback_name:<fallback_name>`` : timer

    Measures the time it takes to do each outbound network request.

``locate.fallback.lookup#fallback_name:<fallback_name>,status:<code>`` : counter

    Counts the HTTP response codes for all outbound requests. There
    is one counter per HTTP response code, for example `200`.

.. _data.batch.upload:
.. _data.report.upload:
.. _data.report.drop:
.. _data.observation.upload:
.. _data.observation.drop:
.. _data.observation.insert:
.. _data.station.confirm:
.. _data.station.blocklist:
.. _data.station.new:
.. _data.station.dberror:

Data Pipeline Metrics
---------------------

When a batch of reports is accepted at one of the submission API
endpoints, it is decomposed into a number of "items" -- wifi or cell
:term:`observations` -- each of which then works its way through a process of
normalization, consistency-checking and eventually (possibly) integration
into aggregate :term:`station` estimates held in the main database tables.
Along the way several counters measure the steps involved:

``data.batch.upload``,
``data.batch.upload#key:<apikey>`` : counters

    Counts the number of "batches" of :term:`reports` accepted to the data
    processing pipeline by an API endpoint. A batch generally
    corresponds to the set of :term:`reports` uploaded in a single HTTP POST
    to one of the submit APIs. In other words this metric counts
    "submissions that make it past coarse-grained checks" such as API-key
    and JSON schema validity checking.

    The metric is either emitted per tracked API key, or for everything
    else without a key tag.

``data.report.upload``,
``data.report.upload#key:<apikey>`` : counters

    Counts the number of :term:`reports` accepted into the data processing
    pipeline. The metric is either emitted per tracked API key, or for
    everything else without a key tag.

``data.report.drop``,
``data.report.drop#key:<apikey>`` : counter

    Count incoming :term:`reports` that were discarded due to some internal
    consistency, range or validity-condition error.

``data.observation.upload#type:blue``,
``data.observation.upload#type:blue,key:<apikey>``,
``data.observation.upload#type:cell``,
``data.observation.upload#type:cell,key:<apikey>``,
``data.observation.upload#type:wifi``,
``data.observation.upload#type:wifi,key:<apikey>`` : counters

    Count the number of Bluetooth, cell or WiFi :term:`observations` entering
    the data processing pipeline; before normalization and blocklist processing
    have been applied. In other words this metric counts "total Bluetooth,
    cell or WiFi :term:`observations` inside each submitted batch", as each
    batch is composed of individual :term:`observations`.

    The metrics are either emitted per tracked API key, or for everything
    else without a key tag.

``data.observation.drop#type:blue``,
``data.observation.drop#type:blue,key:<apikey>``,
``data.observation.drop#type:cell``,
``data.observation.drop#type:cell,key:<apikey>``,
``data.observation.drop#type:wifi``
``data.observation.drop#type:wifi,key:<apikey>`` : counters

    Count incoming Bluetooth, cell or WiFi :term:`observations` that were
    discarded before integration due to some internal consistency, range or
    validity-condition error encountered while attempting to normalize the
    :term:`observation`.

``data.observation.insert#type:blue``,
``data.observation.insert#type:cell``,
``data.observation.insert#type:wifi`` : counters

    Count Bluetooth, cell or WiFi :term:`observations` that are successfully
    normalized, integrated and not discarded due to consistency errors.

``data.station.blocklist#type:blue``,
``data.station.blocklist#type:cell``,
``data.station.blocklist#type:wifi`` : counters

    Count any Bluetooth, cell or WiFi network that is blocklisted due to
    the acceptance of multiple :term:`observations` at sufficiently different
    locations. In these cases, we decide that the :term:`station` is "moving"
    (such as a picocell or mobile hotspot on a public transit vehicle) and
    blocklist it, to avoid estimating query positions using the
    :term:`station`.

``data.station.confirm#type:blue``,
``data.station.confirm#type:cell``,
``data.station.confirm#type:wifi`` : counters

    Count the number of Bluetooth, cell or WiFi :term:`station` that were
    successfully confirmed by any type of :term:`observations`.

``data.station.new#type:blue``,
``data.station.new#type:cell``,
``data.station.new#type:wifi`` : counters

    Count the number of Bluetooth, cell or WiFi :term:`station` that were
    discovered for the first time.

``data.station.dberror#type:<type>,errno:<errno>``: counters

    Count the number of retryable database errors.  ``type`` is ``blue``,
    ``cell``, ``cellarea``, or ``wifi``, and ``errno`` is the error number,
    which can be found on the `MySQL Server Error Reference`_.

    Retryable database errors, like a lock timeout (``1205``) or deadlock
    (``1213``) cause the station updating task to sleep and start over.  Other
    database errors are not counted, but instead halt the task and are recorded
    in Sentry.

.. _data.export.batch:
.. _data.export.upload:
.. _data.export.upload.timing:

Data Pipeline Export Metrics
----------------------------

Incoming :term:`reports` can also be sent to a number of different export
targets. We keep metrics about how those individual export targets perform.

``data.export.batch#key:<export_key>`` : counter

    Count the number of batches sent to the export target.

``data.export.upload.timing#key:<export_key>`` : timer

    Track how long the upload operation took per export target.

``data.export.upload#key:<export_key>,status:<status>`` : counter

    Track the upload status of the current job. One counter per status.
    A status can either be a simple `success` and `failure` or a HTTP
    response code like 200, 400, etc.

.. _api.limit:
.. _queue:

Internal Monitoring
-------------------

``api.limit#key:<apikey>,#path:<path>`` : gauge

    One gauge is created per API key and API path which has rate limiting
    enabled on it. This gauge measures how many requests have been done
    for each such API key and path combination for the current day.

``queue#queue:celery_blue``,
``queue#queue:celery_cell``,
``queue#queue:celery_default``,
``queue#queue:celery_export``,
``queue#queue:celery_incoming``,
``queue#queue:celery_monitor``,
``queue#queue:celery_reports``,
``queue#queue:celery_wifi`` : gauges

    These gauges measure the number of tasks in each of the Redis queues.
    They are sampled at an approximate per-minute interval.

``queue#queue:update_blue_0``,
``queue#queue:update_blue_f``,
``queue#queue:update_cell_gsm``,
``queue#queue:update_cell_wcdma``,
``queue#queue:update_cell_lte``,
``queue#queue:update_cellarea``,
``queue#queue:update_datamap_ne``,
``queue#queue:update_datamap_nw``,
``queue#queue:update_datamap_se``,
``queue#queue:update_datamap_sw``,
``queue#queue:update_wifi_0``,
``queue#queue:update_wifi_f`` : gauges

    These gauges measure the number of items in the Redis update queues.

.. _request:

HTTP Counters
-------------

Every legitimate, routed request to an API endpoint or to a content
view increments a ``request#path:<path>,method:<method>,status:<code>``
counter.

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

.. _request.timing:

HTTP Timers
-----------

In addition to the HTTP counters, every legitimate, routed request
emits a ``request.timing#path:<path>,method:<method>`` timer.

These timers have the same structure as the HTTP counters, except they
do not have the response code tag.

.. _task:

Task Timers
-----------

Our data ingress and data maintenance actions are managed by a Celery
queue of tasks. These tasks are executed asynchronously, and each task
emits a timer indicating its execution time.

For example:

  - ``task#task:data.export_reports``
  - ``task#task:data.update_statcounter``

.. _datamaps:
.. _datamaps.dberror:

Datamaps Timers
---------------

We include a script to generate a data map from the gathered map
statistics. This script includes a number of timers and pseudo-timers
to monitor its operation.

``datamaps#func:export``,
``datamaps#func:encode``,
``datamaps#func:merge``,
``datamaps#func:main``,
``datamaps#func:render``,
``datamaps#func:upload`` : timers

    These timers track the individual functions of the generation process.

``datamaps#count:csv_rows``,
``datamaps#count:quadtrees``,
``datamaps#count:tile_new``,
``datamaps#count:tile_changed``,
``datamaps#count:tile_deleted``,
``datamaps#count:tile_unchanged`` : timers

    Pseudo-timers to track the number of CSV rows, Quadtree files and
    image tiles.


``datamaps.dberror#errno:<errno>``: counter

    Count the number of retryable database errors.  ``errno`` is the error
    number, which can be found on the `MySQL Server Error Reference`_.

    Retryable database errors, like a lock timeout (``1205``) or deadlock
    (``1213``) cause the station updating task to sleep and start over.  Other
    database errors are not counted, but instead halt the task and are recorded
    in Sentry.

.. _`MySQL Server Error Reference`: https://dev.mysql.com/doc/refman/5.7/en/server-error-reference.html
