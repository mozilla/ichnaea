#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Usage: docker/regenerate_requirements.sh [--verify]
#
# Turns requirements/*.in into requirements/*.txt, with hashes
#
# --verify exits with an error if anything changed. This is used to
# ensure a PR's .txt files are generated from the .in rather than
# edited directly.
#
# This should be called from inside a container.

set -euo pipefail
set -o xtrace
IFS=$'\n\t'

REQS=(
  shared
  docs
  prod
  dev
)
VERIFY=0
export CUSTOM_COMPILE_COMMAND="make reqs-regen"

cd /app

VERIFY_PARAM=${1:-}
VERIFY_DIR=
if [[ "$VERIFY_PARAM" == "--verify" ]]; then
    VERIFY=1
    VERIFY_DIR=$(mktemp -d)
    for REQ in "${REQS[@]}"; do
        cp requirements/${REQ}.txt ${VERIFY_DIR}/${REQ}.txt.orig
    done
fi

compile() {
    REQ_PATH=$1
    echo ">>> pip-compile ${REQ_PATH}"
    pip-compile --quiet --generate-hashes ${REQ_PATH}
}

for REQ in "${REQS[@]}"; do
    compile requirements/${REQ}.in
done

if [[ $VERIFY -eq 1 ]]; then
    PASS=1
    for REQ in "${REQS[@]}"; do
        echo ">>> Checking for changes in requirements/${REQ}.txt"
        set +e
        diff ${VERIFY_DIR}/${REQ}.txt.orig requirements/${REQ}.txt
        HAS_DIFF=$?
        set -e
        if [[ $HAS_DIFF -ne 0 ]]; then
            PASS=0;
        fi
        rm ${VERIFY_DIR}/${REQ}.txt.orig
    done
    rmdir ${VERIFY_DIR}
    if [[ $PASS -eq 0 ]]; then
        echo "*** ERROR: Running pip-compile changed the output"
        exit 1
    else
        echo "*** SUCCESS: Running pip-compile did not change the output"
    fi
fi
