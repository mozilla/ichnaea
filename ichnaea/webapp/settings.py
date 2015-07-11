"""
Contains :ref:`Gunicorn configuration settings <gunicorn:settings>`.

This needs to be specified on the command line via the `-c` argument:

.. code-block:: bash

    bin/gunicorn -c ichnaea.webapp.settings ichnaea.webapp.app:wsgi_app

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

# Recycle worker processes after 10m requests to prevent memory leaks
# from effecting us, at 100 req/s this means recycle every 2.8 hours
max_requests = 1000000
# Use some jitter to prevent all workers from restarting at once.
max_requests_jitter = max_requests // 10

# Log errors to stderr
errorlog = '-'

# Avoid too much output on the console
loglevel = 'warning'


def _statsd_host():
    from ichnaea.config import read_config

    conf = read_config()
    if conf.has_section('ichnaea'):
        section = conf.get_map('ichnaea')
    else:  # pragma: no cover
        # happens while building docs locally and on rtfd.org
        return

    return section.get('statsd_host', None)

# Set host and prefix for gunicorn's own statsd messages
statsd_host = _statsd_host()
statsd_prefix = 'location'
del _statsd_host


def post_worker_init(worker):
    # Actually initialize the application
    worker.wsgi(None, None)
