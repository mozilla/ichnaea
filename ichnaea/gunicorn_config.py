# This file contains gunicorn configuration setttings, as described at
# http://docs.gunicorn.org/en/latest/settings.html
# The file is loaded via the -c ichnaea.gunicorn_config command line option

# Be explicit about the worker class
worker_class = "sync"

# Set timeout to the same value as the default one from Amazon ELB (60 secs).
# It should be 60 seconds, but gunicorn halves the configured value,
# see https://github.com/benoitc/gunicorn/issues/829
timeout = 120

# Recycle worker processes after 100k requests to prevent memory leaks
# from effecting us
max_requests = 100000

# Avoid too much output on the console
loglevel = "warning"
