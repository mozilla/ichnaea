.. _internal:

=================
Internal Code API
=================

This section describes the internal Python API's used throughout the code base.
For documentation on the public HTTP API please look at :ref:`service_api`.


Overview
========

The code is structured around a couple of larger functional areas in
addition to top-level helper modules.

There are two sub-packages `async` and `webapp` related to runtime
configuration and settings of the two process classes. `async` deals
with Celery and `webapp` deals with `gunicorn`.

The `api` sub-package deals with the implementation of the public
HTTP API. The `content` sub-package includes the public website content.
The `data` sub-package includes the data pipeline code, in the form of
asynchronous Celery tasks. The `models` sub-package deals with database
models and schema validation. `scripts` has the implementation of
command line scripts.


Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`

.. toctree::
   :maxdepth: 2

   api/index
   async/index
   cache
   config
   constants
   content/index
   data/index
   db
   exceptions
   geocalc
   geocode
   geoip
   http
   log
   models/index
   queue
   scripts/index
   util
   webapp/index
