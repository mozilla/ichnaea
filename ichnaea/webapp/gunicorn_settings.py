"""
Contains :ref:`Gunicorn configuration settings <gunicorn:settings>` and
hook functions.
"""

# Disable keep-alive
keepalive = 0


def post_worker_init(worker):
    worker.wsgi(None, None)


def worker_exit(server, worker):
    from ichnaea.webapp.app import worker_exit

    worker_exit(server, worker)
