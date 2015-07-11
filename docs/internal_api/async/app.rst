:mod:`ichnaea.async.app`
------------------------

.. automodule:: ichnaea.async.app

.. autodata:: celery_app
   :annotation: = Internal module global holding the celery app.

This is also the Celery app public endpoint, used on the command line via:

.. code-block:: bash

    bin/celery -A ichnaea.async.app:celery_app <worker, beat>

.. autofunction:: init_worker_process
.. autofunction:: shutdown_worker_process
