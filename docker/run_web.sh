#!/bin/bash

set -e

# Runs the webapp in gunicorn.

# START GUNICORN CONFIGURATION

# Port for gunicorn to listen on
GUNICORN_PORT=${GUNICORN_PORT:-"8000"}

# Number of gunicorn workers to spin off--should be one per cpu
GUNICORN_WORKERS=${GUNICORN_WORKERS:-"1"}

# Gunicorn worker class--use our gevent worker
GUNICORN_WORKER_CLASS=${GUNICORN_WORKER_CLASS:-"ichnaea.webapp.worker.LocationGeventWorker"}

# Number of simultaneous greenlets per worker
GUNICORN_WORKER_CONNECTIONS=${GUNICORN_WORKER_CONNECTIONS:-"4"}

# Number of requests to handle before retiring worker
GUNICORN_MAX_REQUESTS=${GUNICORN_MAX_REQUESTS:-"10000"}

# Jitter to add/subtract from number of requests to prevent stampede
# of retiring
GUNICORN_MAX_REQUESTS_JITTER=${GUNICORN_MAX_REQUESTS_JITTER:-"1000"}

# Timeout for handling a request
GUNICORN_TIMEOUT=${GUNICORN_TIMEOUT:-"60"}

# Python log level for gunicorn logging output: debug, info, warning,
# error, critical
GUNICORN_LOGLEVEL=${GUNICORN_LOGLEVEL:-"info"}

# END GUNICORN CONFIGURATION

LOCAL_DEV_ENV=${LOCAL_DEV_ENV:-"False"}

# Make sure the app can load; this will route out some of the possible "can't
# start" scenarios
python /app/ichnaea/webapp/app.py --check

if [ "${LOCAL_DEV_ENV}" == "True" ]; then
    echo "*****************************************************************************"
    echo "Running webapp in local dev environment."
    echo "Connect at http://localhost:8000"
    echo "*****************************************************************************"
    cd /app/ && python ichnaea/webapp/app.py

else
    set -x
    gunicorn \
        --pythonpath /app \
        --workers="${GUNICORN_WORKERS}" \
        --worker-class="${GUNICORN_WORKER_CLASS}" \
        --worker-connections="${GUNICORN_WORKER_CONNECTIONS}" \
        --max-requests="${GUNICORN_MAX_REQUESTS}" \
        --max-requests-jitter="${GUNICORN_MAX_REQUESTS_JITTER}" \
        --capture-output \
        --error-logfile=- \
        --access-logfile=- \
        --log-file=- \
        --timeout="${GUNICORN_TIMEOUT}" \
        --config=python:ichnaea.webapp.gunicorn_settings \
        --bind 0.0.0.0:"${GUNICORN_PORT}" \
        ichnaea.webapp.app:wsgi_app
fi
