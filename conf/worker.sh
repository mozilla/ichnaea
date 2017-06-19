#!/bin/sh

# BBB: Celery 4
# exec /app/bin/celery -A ichnaea.async.app:celery_app worker

exec /app/bin/celery -A ichnaea.async.app:celery_app worker \
    -Ofair --without-mingle --without-gossip --no-execv
