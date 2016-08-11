#!/bin/sh

exec /app/bin/celery -A ichnaea.async.app:celery_app beat -s "/var/run/location/celerybeat-schedule" --pidfile="/var/run/location/celerybeat.pid"
