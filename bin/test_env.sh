#!/bin/bash

# Script that sets up the docker environment to run the tests in and runs the
# tests.

# Pass --shell to run a shell in the test container.

# Failures should cause setup to fail
set -v -e -x

# Set PS4 so it's easier to differentiate between this script and run_tests.sh
# running
PS4="+ (test_env.sh): "

DC="$(which docker-compose)"
ICHNAEA_UID=${ICHNAEA_UID:-"10001"}
ICHNAEA_GID=${ICHNAEA_GID:-"10001"}
ICHNAEA_DOCKER_DB_ENGINE=${ICHNAEA_DOCKER_DB_ENGINE:-"mysql_5_7"}

# Use the same image we use for building docker images because it's cached.
# Otherwise this doesn't make any difference.
BASEIMAGENAME="python:3.11.3-slim"
TESTIMAGE="local/ichnaea_app"

# Start services in background (this is idempotent)
echo "Starting services needed by tests in the background..."
${DC} up -d db redis

# If we're running a shell, then we start up a test container with . mounted
# to /app.
if [ "$1" == "--shell" ]; then
    echo "Running shell..."

    docker run \
        --rm \
        --user "${ICHNAEA_UID}" \
        --volume "$(pwd)":/app \
        --workdir /app \
        --network ichnaea_default \
        --link ichnaea_db_1 \
        --link ichnaea_redis_1 \
        --env-file ./docker/config/local_dev.env \
        --env-file ./docker/config/test.env \
        --tty \
        --interactive \
        --entrypoint="" \
        "${TESTIMAGE}" /bin/bash
    exit $?
fi

# Create a data container to hold the repo directory contents and copy the
# contents into it--reuse if possible
if [ "$(docker container ls --all | grep ichnaea-repo)" == "" ]; then
    echo "Creating ichnaea-repo container..."
    docker create \
           -v /app \
           --user "${ICHNAEA_UID}" \
           --name ichnaea-repo \
           "${BASEIMAGENAME}" /bin/true
fi

echo "Copying contents..."

# Wipe whatever might be in there from past runs and verify files are gone
docker run \
       --user root \
       --volumes-from ichnaea-repo \
       --workdir /app \
       --entrypoint="" \
       "${TESTIMAGE}" sh -c "rm -rf /app/* && ls -l /app/"

# Copy the repo root into /app
docker cp . ichnaea-repo:/app

# Fix file permissions in data container
docker run \
       --user root \
       --volumes-from ichnaea-repo \
       --workdir /app \
       --entrypoint="" \
       "${TESTIMAGE}" chown -R "${ICHNAEA_UID}:${ICHNAEA_GID}" /app

# Check that database server is ready for tests
docker run \
    --rm \
    --user "${ICHNAEA_UID}" \
    --volumes-from ichnaea-repo \
    --workdir /app \
    --network ichnaea_default \
    --link ichnaea_db_1 \
    --link ichnaea_redis_1 \
    --env-file ./docker/config/local_dev.env \
    --tty \
    --interactive \
    --entrypoint= \
    "${TESTIMAGE}" /app/docker/run_check_db.sh

# Run tests in that environment and then remove the container
echo "Running tests..."
docker run \
    --rm \
    --user "${ICHNAEA_UID}" \
    --volumes-from ichnaea-repo \
    --workdir /app \
    --network ichnaea_default \
    --link ichnaea_db_1 \
    --link ichnaea_redis_1 \
    --env-file ./docker/config/local_dev.env \
    --env-file ./docker/config/test.env \
    --tty \
    --interactive \
    --entrypoint= \
    "${TESTIMAGE}" /app/docker/run_tests.sh "$@"

echo "Done!"
