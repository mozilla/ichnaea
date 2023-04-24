#!/bin/bash
set -e

# Check that the database is running
MAX_ATTEMPTS=6
ATTEMPT=1
until python ichnaea/scripts/db.py check
do
    if ((ATTEMPT==MAX_ATTEMPTS))
    then
        echo "Database connection failed."
        exit 1
    else
        echo "Database is not yet ready. Trying again in 5 seconds."
        sleep 5
        ATTEMPT=$((ATTEMPT+1))
    fi
done
