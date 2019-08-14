#!/bin/sh
set -e

cd "$(dirname "$0")"
SERVICE=$1
shift

case "${SERVICE}" in
    web)
        echo "Starting Web Server"
        exec ./run_web.sh
        ;;
    scheduler)
        echo "Starting Celery Scheduler"
        exec ./run_scheduler.sh
        ;;
    worker)
        echo "Starting Celery Worker"
        exec ./run_worker.sh
        ;;
    map)
        echo "Creating datamaps image tiles."
        cd ..
        exec ./docker/run_map.sh
        ;;
    local_map)
        echo "Creating datamaps image tiles."
        cd ..
        exec ./docker/run_local_map.sh
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
