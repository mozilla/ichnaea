.. _architecture:

============
Architecture
============

Overview
========

The application consists of an HTTP web service implementing the APIs and
web site and a streaming data pipeline.


Web Service
===========

The web service uses the Python Pyramid web framework.

The web service serves several content views (home page, downloads page, maps
page, and so on), serves the locate and submit API endpoints, and serves
several monitoring endpoints.

The web service uses MySQL, but should function and respond to requests even if
MySQL is down or unavailable.

Redis is used to track API key usage and unique IP addresses making
service requests.

All API endpoints require a valid API key to use. The web service caches
keys to reduce MySQL lookups.

Requests to lookup API endpoints that only contain an IP address are
fulfilled just by looking at the Maxmind GeoIP database without
any MySQL lookups.

Requests to lookup API endpoints that contain additional network information
are fulfilled by using `location providers`.  These are responsible for
matching the data against the MySQL tables and generate possible result values
and corresponding data quality / trustworthiness scores.

Some API keys allow falling back to an external web service if the best
internal result does not match the expected accuracy/precision of the
incoming query. In those cases an additional HTTPS request is made to
an external service and that result is considered as a possible result
in addition to the internal ones.

The system only deals with probabilities, fuzzy matches, and has to consider
multiple plausible results for each incoming query. The data in the database
will always represent a view of the world which is outdated, compared to the
changes in the real world.

Should the service be able to generate a good enough answer, this is sent back
as a response. The incoming query and this answer are also added to a queue, to
be picked up by the data pipeline later. This query based data is used to
validate and invalidate the database contents and estimate the position of
previously unknown networks as to be near the already known networks.


Data pipeline
=============

The data pipeline uses the Python Celery framework, its Celery scheduler and
custom logic based on Redis.

The Celery scheduler schedules recurring tasks that transform and move data
through the pipeline. These tasks process data in batches stored in custom
Redis Queues implemented as Redis lists. Celery tasks themselves don't contain
any data payload, but instead act as triggers to process the seperate queues.

Things to note:

1. The pipeline makes no at-most or at-least once delivery guaruantees, but
   is based on a best-effort approach.

2. Most of the data is being sent to the service repeatedly and missing some
   small percentage of overall data doesn't negatively impact the data quality.

3. A small amount of duplicate data is processed which won't negatively impact
   the data qualtiy.


Data flows
----------

Locate API
~~~~~~~~~~

The data flow for a Locate API request looks like this:

FIXME


Submit API
~~~~~~~~~~

The data flow for a Submit API request looks like this:

1. The Web frontend stores data in Redis (`update_incoming`).

2. The Celery scheduler plans the execution of the `update_incoming` task.

3. The Celery Async worker executes the `update_incoming` task, this task
   acts as a multiplexer and depends on the `export_config` database table.
   Typically data is forwared into a backup job, storing data in S3, a
   internal processing job to update the database contents and an external
   data sharing job, to share the data with one or more external partners.

4. The `update_incoming` stores data in multiple Redis lists, for example
   `queue_export_internal` and one more `queue_export_*` for each export
   target. These targets all have different batch intervals, so data is
   duplicated at this point. The job checks the length and last processing
   time of each queue and schedules a `export_reports` job per target.

5. The task worker export reports job either assembles the data to store
   in S3, upload it to an external web service or prepares it for internal
   processing. The internal processing job splits the reports into its
   parts, creating one observation per network and queues them into
   multiple queues, one queue corresponding to one database table shard.
   This data ends up in Redis queues like `update_cell_gsm`,
   `update_cell_wcdma`, `update_wifi_0`, `update_wifi_1`, etc. The job
   also fills the `update_datamap` queue, to update the coverage data
   map on the web site.

6. The celery scheduler again plans a `station updater` job for each type
   of network, for example an `update_wifi` task. These jobs take in the
   new batch of observations and match them against the known database
   contents. As a result network positions can be modified, new networks
   be added or old networks be marked as blocklisted, noting that they've
   recently moved from their old position.



