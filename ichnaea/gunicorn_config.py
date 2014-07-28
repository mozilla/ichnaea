# This file contains gunicorn configuration setttings, as described at
# http://docs.gunicorn.org/en/latest/settings.html
# The file is loaded via the -c ichnaea.gunicorn_config command line option

# Be explicit about the worker class
worker_class = "sync"

# Set timeout to the same value as the default one from Amazon ELB (60 secs).
timeout = 60

# Recycle worker processes after 100k requests to prevent memory leaks
# from effecting us
max_requests = 100000

# Avoid too much output on the console
loglevel = "warning"


def post_worker_init(worker):
    from random import randint

    # Use 10% jitter, to prevent all workers from restarting at once,
    # as they get an almost equal number of requests
    jitter = randint(0, max_requests // 10)
    worker.max_requests += jitter

    # Actually initialize the application
    worker.wsgi(None, None)
