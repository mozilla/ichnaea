.. _data-flows:

==========
Data flows
==========

.. contents::
   :local:


.. _position-data-flow:

Position data
=============

Position data is stored in the database in shard tables:

* ``blue_shard_*``: hex 0 through f
* ``cell_*``: ``area``, ``gsm``, ``lte``, and ``wcdma``
* ``wifi_shard_*``: hex 0 through f

This data is created and updated from incoming API requests.

Data flow:

1. User submits data to one of the submit API endpoints.

   If the user used an api key and the key is sampling submissions, then the
   submission might get dropped at this point.

   *OR*

   User submits query to one of the locate API endpoints.

   If the query is handled by ``InternalPositionSource``, then the web frontend
   adds a submission.

2. If the submission is kept, then the web frontend adds an item to the
   ``update_incoming`` queue in Redis.

   The item looks like a::

       {"api_key": key, "report": report, "source": source}

   "source" can be one of:

   * ``gnss``: Global Navigation Satellite System based data
   * ``fused``: position data obtained from a combination of other sensors or
     outside service queries
   * ``fixed``: outside knowledge about the true position of the station
   * ``query``: position estimate based on query data

3. The Celery scheduler schedules the ``update_incoming`` task every 
   X seconds--see task definition in `ichnaea/data/tasks.py
   <https://github.com/mozilla/ichnaea/blob/main/ichnaea/data/tasks.py>`_.

4. A Celery worker executes the ``update_incoming`` task.

   This task acts as a multiplexer and its behavior depends on the
   ``export_config`` database table table.

   The ``update_incoming`` task will store data in multiple Redis lists depending
   on the ``export_config`` table. For example, it could store it in
   ``queue_export_internal`` and one more ``queue_export_*`` for each export
   target. These targets all have different batch intervals, so data is
   duplicated at this point.

   The task checks the length and last processing time of each queue and
   schedules an ``export_reports`` task if the queue is ready for processing.

5. A Celery worker executes ``export_reports`` tasks:

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

     This data ends up in Redis queues like ``update_cell_gsm``,
     ``update_cell_wcdma``, ``update_wifi_0``, ``update_wifi_1``, etc to be
     processed by ``station updater`` tasks.

     The internal processing job also fills the ``update_datamap`` queue, to
     update the coverage data map on the web site.

6. The Celery worker executes ``station updater`` tasks.

   These tasks take in the new batch of observations and match them against
   known data. As a result, network positions can be modified, new networks can
   be added, and old networks be marked as blocked noting that they've
   recently moved from their old position.  See :ref:`observations` for
   details.


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

Datamap data is stored in the ``datamap_*`` (``ne``, ``nw``, ``se``, ``sw``)
tables. The north / south split is at 36˚N latitude, and the east / west split
at 5˚ longitude, to attempt to split the data into four equal shards. The rows
divide the world into boxes that are one-thousandth of a degree on each side
(about 112 meters at the equator), and record the first and latest time that
an observation was seen in that box. Other details, including the exact
position of the observation, are not recorded. These tables are updated during
the ``internal`` processing job.

A periodic task runs the script ``ichnaea/scripts/datamap.py`` to convert this
data into transparent tile images for the contribution map. Thread pools are
used to distribute the work across available processors. The process is:

1. Export the datamap tables as CSV files.

   The latitude, longitude, and days since last observation are fed into a
   randomizer that creates 0 to 13 nearby points, more for the recently
   observed grid positions. This emulates the multiple observations that go
   into each grid position, and hides details of observations for increased
   privacy.

2. Convert the CSV files to a quadtree_ structure.

   The binary quadtree structure efficiently stores points when there are
   large areas with no points, and is faster for determining points within
   the bounding box of a tile.

3. Merge the per-table quadtrees to a single quadtree file.

   This includes removing duplicates at the boundaries of tables.

4. Generate and minimize tiles for the different zoom levels.

   Each zoom level potentially has four times the tiles of the previous zoom
   level, with 1 at zoom level 0, 4 at zoom level 1, 16 at zoom level 2, up
   to over 4 million at maximum zoom level 11. However, tiles with no
   observations are not rendered, so the actual number of generated tiles is
   less. The tiles are stored in a folder structure by zoom level, x position,
   and files at the y position, to match Mapbox tile standards and to avoid
   having too many files in a folder.

   Tiles are further optimized for disk space by reducing the colorspace,
   without reducing quality below a target.

   A double-resolution tile at zoom level 0 is created for the map overview
   on the front page on high-resolution displays.

5. Upload the tiles to an S3 bucket.

   There may be existing tiles in the S3 bucket from previous uploads. The
   script collects the size and MD5 hash of existing S3 tiles, and compares
   them to the newly generated tiles, to determine which are new, which are
   updated, which are the same an can be ignored, and which S3 tiles should
   be deleted.

   New and updated tiles are uploaded. Uploading is I/O bound, so the
   concurrency of uploads is doubled. The deleted tiles are deleted in
   batches, for speed.

   A file ``tiles/data.json`` is written to record when the upload completed
   and details of the tile generation process.


Quadtree and tile generation tools are provided by `ericfischer/datamaps`_, and
PNG size optimization by pngquant_.

.. _quadtree: https://en.wikipedia.org/wiki/Quadtree
.. _ericfischer/datamaps: https://github.com/ericfischer/datamaps
.. _pngquant: https://pngquant.org
