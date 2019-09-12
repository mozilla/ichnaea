#!/bin/sh

# BBB: Celery 4
# celery -A ichnaea.taskapp.app:celery_app worker

celery -A ichnaea.taskapp.app:celery_app worker \
    -Ofair --without-mingle --without-gossip --no-execv
