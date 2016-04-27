"""
Contains :ref:`Gunicorn configuration settings <gunicorn:settings>`.

This needs to be specified on the command line via the `-c` argument:

.. code-block:: bash

    bin/gunicorn -c python:ichnaea.webapp.settings \
        ichnaea.webapp.app:wsgi_app

"""

# Use our own Gevent worker
worker_class = 'ichnaea.webapp.worker.LocationGeventWorker'

# Maximum number of simultaneous greenlets,
# limited by number of DB and Redis connections
worker_connections = 20

# Set timeout to the same value as the default one from Amazon ELB (60 secs).
timeout = 60

# Disable keep-alive
keepalive = 0

# Recycle worker processes after 1 million requests to prevent memory leaks.
max_requests = 1000000
# Use some jitter to prevent all workers from restarting at once.
max_requests_jitter = max_requests // 10

# Log errors to stderr
errorlog = '-'

# Avoid too much output on the console
loglevel = 'warning'


def post_worker_init(worker):  # pragma: no cover
    # Actually initialize the application
    worker.load_wsgi()
    worker.wsgi(None, None)


def worker_exit(server, worker):  # pragma: no cover
    from ichnaea.webapp.app import worker_exit
    worker_exit(server, worker)
