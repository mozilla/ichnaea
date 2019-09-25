#!/bin/sh
celery -A ichnaea.taskapp.app:celery_app beat \
    -s "/var/run/location/celerybeat-schedule" \
    --pidfile="/var/run/location/celerybeat.pid" \
    --loglevel=INFO
