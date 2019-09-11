"""
Contains :ref:`Gunicorn configuration settings <gunicorn:settings>`.

This needs to be specified on the command line via the `-c` argument:

.. code-block:: bash

    bin/gunicorn -c python:ichnaea.webapp.gunicorn_settings \
        ichnaea.webapp.app:wsgi_app

"""
import multiprocessing

# Use our own Gevent worker
worker_class = "ichnaea.webapp.worker.LocationGeventWorker"

# Create one worker process per CPU.
workers = multiprocessing.cpu_count()

# Maximum number of simultaneous greenlets,
# limited by number of DB and Redis connections
worker_connections = 20

# Set timeout to the same value as the default one from Amazon ELB (60 secs).
timeout = 60

# Disable keep-alive
keepalive = 0

# Log errors to stderr
errorlog = "-"

# Avoid too much output on the console
loglevel = "warning"


def post_worker_init(worker):
    worker.wsgi(None, None)


def worker_exit(server, worker):
    from ichnaea.webapp.app import worker_exit

    worker_exit(server, worker)


del multiprocessing
