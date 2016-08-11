#!/bin/sh

exec /app/bin/celery -A ichnaea.async.app:celery_app worker -Ofair --maxtasksperchild=100000 --without-mingle --without-gossip --no-execv
