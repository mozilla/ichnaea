#!/bin/sh

exec /app/bin/celery -A ichnaea.async.app:celery_app worker
