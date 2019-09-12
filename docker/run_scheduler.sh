#!/bin/sh

# BBB: Celery 4
# exec /app/bin/celery -A ichnaea.taskapp.app:celery_app beat --loglevel='WARNING'

celery -A ichnaea.taskapp.app:celery_app beat \
    -s "/var/run/location/celerybeat-schedule" \
    --pidfile="/var/run/location/celerybeat.pid"
