#!/bin/sh
set -e

cd "$(dirname "$0")"
SERVICE=$1
shift

case "${SERVICE}" in
    map)
        echo "Creating datamaps image tiles."
        exec ./run_map.sh
        ;;
    scheduler)
        echo "Starting Celery Scheduler"
        exec ./run_scheduler.sh
        ;;
    web)
        echo "Starting Web Server"
        exec ./run_web.sh
        ;;
    worker)
        echo "Starting Celery Worker"
        exec ./run_worker.sh
        ;;
    local_map)
        echo "Creating datamaps image tiles."
        cd ..
        /app/bin/location_map --create --output /app/ichnaea/content/static/tiles/
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
    *)
        echo "Usage: $0 {scheduler|web|worker|shell}"
        exit 1
esac
