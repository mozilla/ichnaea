.. _architecture:

============
Architecture
============

Overview
========

The application consists of a streaming data pipeline, a HTTP web service
and a normal web site.


Hardware Stack
==============

In terms of physical resources it's helpful to look at a diagram of a
typical full deployment in an AWS environment:

.. image:: deploy.png
   :height: 1860px
   :width: 1440px
   :scale: 50%
   :alt: Deployment Diagram

Major components are MySQL and Redis in addition to load balancers,
web servers and Amazon S3.


Software Stack
==============

On the software side, the application is complex and based on many different
libraries and frameworks. The streaming data pipeline is a combination
of the Python Celery framework, its Celery scheduler and custom logic
based on Redis. The web service and web site are based on the
Python Pyramid web framework.

In addition to those larger frameworks many other Python libraries are used
including Cython, gevent, numpy/scipy, maxminddb, pytest, Rtree, Shapely
and SQLAlchemy.

There are also a good number of C/C++ libraries and command line programs
involved, like libgeos, libspatialindex, libmaxminddb, pngquant and a
tool called datamaps for generating the coverage data map tiles.


Data Pipeline
=============

The data pipeline is based on recurring tasks scheduled via the Celery
scheduler. These process data in batches, stored in custom Redis Queues
(implemented as Redis lists). Celery tasks themselves don't contain any
data payload, but merely act as triggers to process the seperate queues.

The pipeline itself makes no at-most or at-least once delivery
guaruantees, but is based on a best-effort approach. The assumption is
that most of the data is being sent to the service repeatedly and missing
some small percentage doesn't negatively impact the data quality. At
the same time since redundant data is being processed by the system
in any case, a small number of additional cases of duplicated data
processing caused by the pipeline itself doesn't hurt much either.

In more technical concrete terms, the typical data flow of an incoming
request looks like this:

Submit API
----------

- The Web frontend stores data in Redis (`update_incoming`)
- The Celery scheduler plans the execution of the `update_incoming` task.
- The Celery Async worker executes the `update_incoming` task, this task
  acts as a multiplexer and depends on the `export_config` database table.
  Typically data is forwared into a backup job, storing data in S3, a
  internal processing job to update the database contents and an external
  data sharing job, to share the data with one or more external partners.
- The `update_incoming` stores data in multiple Redis lists, for example
  `queue_export_internal` and one more `queue_export_*` for each export
  target. These targets all have different batch intervals, so data is
  duplicated at this point. The job checks the length and last processing
  time of each queue and schedules a `export_reports` job per target.
- The async worker export reports job either assembles the data to store
  in S3, upload it to an external web service or prepares it for internal
  processing. The internal processing job splits the reports into its
  parts, creating one observation per network and queues them into
  multiple queues, one queue corresponding to one database table shard.
  This data ends up in Redis queues like `update_cell_gsm`,
  `update_cell_wcdma`, `update_wifi_0`, `update_wifi_1`, etc. The job
  also fills the `update_datamap` queue, to update the coverage data
  map on the web site.
- The celery scheduler again plans a `station updater` job for each type
  of network, for example an `update_wifi` task. These jobs take in the
  new batch of observations and match them against the known database
  contents. As a result network positions can be modified, new networks
  be added or old networks be marked as blocklisted, noting that they've
  recently moved from their old position.


Web Service
===========

The web service offers a couple of different HTTP APIs. As a first step
the service needs to validate the API key in the request. In order to avoid
doing a database backend lookup on each request, the web service frontend
uses an in-memory API key cache with a livetime of 5 minutes with some
additional jitter.

As a second step some requests contain only the orginating IP address
of the request without any additional information about Bluetooth, Cell
or WiFi networks. These requests are answered based on the locally
available Maxmind GeoIP database, again avoiding any backend database
lookup. A backend request to Redis is still made to track API key usage
and maintain a Redis HyperLogLog counting the number of unique IP
addresses making service requests.

Should the request contain additional network information, this
information is matched against a list of `location providers`. These
are responsible for matching the data against the internal database
structures and generate possible result values and corresponding
data quality / trustworthiness scores.

Some API keys allow falling back on an external web service if the best
internal result does not match the expected accuracy/precision of the
incoming query. In those cases an additional HTTPS request is made to
an external service and their result is considered as a possible result
in addition to the internal ones.

Generally speaking the system only deals with probabilities, fuzzy matches
and has to consider multiple plausible results for each incoming query.
The database contents will always represent a view of the world which is
outdated, compared to the changes in the real world.

Should the service be able to generate a plausible and good enough
answer, this is send back as a response. The incoming query and this
answer is also stored in another queue, to be picked up by the data
pipeline later. This query based data is used to in/validate the database
contents and estimate the position of previously unknown networks as
to be near the already known networks.
