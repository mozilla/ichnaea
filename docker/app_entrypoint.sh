#!/bin/sh
set -e

cd $(dirname $0)
SERVICE=$1
shift

case "${SERVICE}" in
    map)
        echo "Creating datamaps image tiles."
        exec ./map.sh
        ;;
    scheduler)
        echo "Starting Celery Scheduler"
        exec ./scheduler.sh
        ;;
    web)
        echo "Starting Web Server"
        exec ./web.sh
        ;;
    worker)
        echo "Starting Celery Worker"
        exec ./worker.sh
        ;;
    alembic)
        echo "Running Alembic"
        cd ..
        /app/bin/alembic "$@"
        ;;
    local_map)
        echo "Creating datamaps image tiles."
        cd ..
        /app/bin/location_map --create \
            --output /app/ichnaea/content/static/tiles/
        ;;
    shell)
        echo "Opening shell"
        cd ..
        if [ -z "$*" ]; then
            exec /bin/bash
        else
            "$@"
        fi
        ;;
    docs)
        echo "Updating docs"
        cd ..
        make -f docker.make docs
        ;;
    *)
        echo "Usage: $0 {scheduler|web|worker|alembic|shell}"
        exit 1
esac
