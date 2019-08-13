#!/bin/sh

# BBB: Celery 4
# celery -A ichnaea.async.app:celery_app worker

celery -A ichnaea.async.app:celery_app worker \
    -Ofair --without-mingle --without-gossip --no-execv
