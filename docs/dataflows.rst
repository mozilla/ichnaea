.. _data-flows:

==========
Data flows
==========

API keys
========

API keys are stored in the ``api_key`` table.

API keys are created, updated, and deleted by an admin.


Export config
=============

Export configuration is stored in the ``export_config`` table.

Export configuration is created, updated, and deleted by an admin.


Stat data
=========

Stat data is stored in the ``stat`` and ``region_stat`` tables.

FIXME: data flow for stat data?


Datamap data
============

Datamap data is stored in the ``datamap_*`` tables.

FIXME: data flow for datamap data?


Position data
=============

Position data is stored in the database in shard tables:

* ``blue_shard_*``
* ``cell_*``
* ``wifi_shard_*``

This data is created and updated from incoming API requests.

Data flow:

1. User submits data to one of the submit API endpoints.

   If the user used an api key and the key is sampling submissions, then the
   submission might get dropped at this point.

   OR 

   User submits query to one of the locate API endpoints.

   If the query is handled by `InternalPositionSource`, then the web frontend
   adds a submission.

2. If the sumission is kept, then the web frontend adds an item to the
   `update_incoming` queue in Redis.

   The item looks like a::

       {"api_key": key, "report": report, "source": source}

   "source" can be one of "gnss", "fused", "query".

3. The Celery scheduler schedules the `update_incoming` task every 
   X seconds--see task definition in ``ichnaea/data/tasks.py``.

4. A Celery worker executes the `update_incoming` task.

   This task acts as a multiplexer and its behavior depends on the
   `export_config` database table table.

   The `update_incoming` task will store data in multiple Redis lists depending
   on the `export_config` table. For example, it could store it in
   `queue_export_internal` and one more `queue_export_*` for each export
   target. These targets all have different batch intervals, so data is
   duplicated at this point.

   The task checks the length and last processing time of each queue and
   schedules an `export_reports` task if the queue is ready for processing.

5. A Celery worker executes `export_reports` tasks:

   * ``dummy``:

     The dummy export does nothing--it's a no-op.

   * ``geosubmit``:

     The geosubmit export sends the data as JSON to some HTTP endpoint. This
     can be used to submit data to other systems.

   * ``s3``:

     The s3 export generates a gzipped JSON file of the exports and uploads
     to a configured AWS S3 bucket.

   * ``internal``:

     The internal processing job splits the reports into its parts, creating one
     observation per network and queues them into multiple queues, one queue
     corresponding to one database table shard.
     
     This data ends up in Redis queues like `update_cell_gsm`,
     `update_cell_wcdma`, `update_wifi_0`, `update_wifi_1`, etc to be
     processed by `station updater` tasks.
     
     The internal processing job also fills the `update_datamap` queue, to
     update the coverage data map on the web site.

6. The Celery worker executes `station updater` tasks.

   These tasks take in the new batch of observations and match them against the
   known database contents. As a result network positions can be modified, new
   networks be added or old networks be marked as blocklisted, noting that
   they've recently moved from their old position.
