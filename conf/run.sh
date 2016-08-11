#!/bin/sh

cd $(dirname $0)
case "$1" in
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
        bin/alembic $2 $3 $4 $5 $6 $7 $8 $9
        ;;
    shell)
        echo "Opening shell"
        cd ..
        exec /bin/bash
        ;;
    docs)
        echo "Updating docs"
        cd ..
        make -f docker.make docs
        ;;
    test)
        echo "Running Tests"
        cd ..
        make -f docker.make test $2 $3 $4 $5 $6 $7 $8 $9
        ;;
    *)
        echo "Usage: $0 {scheduler|web|worker|alembic|shell|docs|test}"
        exit 1
esac
